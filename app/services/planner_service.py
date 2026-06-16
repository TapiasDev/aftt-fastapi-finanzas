from copy import deepcopy
from uuid import uuid4

from app.core.exceptions import AppError
from app.repositories.expense_recurrences_repository import ExpenseRecurrencesRepository
from app.repositories.month_periods_repository import MonthPeriodsRepository
from app.schemas.planner import FortnightPeriodResponse, MonthDetailResponse, YearDataResponse
from app.utils.dates import utc_now


class PlannerService:
    def __init__(self) -> None:
        self.month_periods_repository = MonthPeriodsRepository()
        self.expense_recurrences_repository = ExpenseRecurrencesRepository()

    async def get_available_years(self, user_id: str) -> list[int]:
        await self._ensure_year_data(user_id, utc_now().year)
        years = await self.month_periods_repository.list_available_years(user_id)
        return sorted(years)

    async def get_year(self, user_id: str, year: int) -> YearDataResponse:
        months = await self._ensure_year_data(user_id, year)
        return YearDataResponse(selectedYear=year, months=[self._to_month_summary(item) for item in months])

    async def get_month(self, user_id: str, year: int, month_number: int) -> MonthDetailResponse:
        await self._ensure_year_data(user_id, year)
        month_document = await self.month_periods_repository.find_month(user_id, year, month_number)

        if not month_document:
            raise AppError(f"Month {month_number} for year {year} is not available.", 404)

        return self._to_month_detail(month_document)

    async def save_fortnight_income(self, user_id: str, fortnight_id: str, income_amount: float) -> FortnightPeriodResponse:
        month_document = await self.month_periods_repository.find_month_by_fortnight_id(user_id, fortnight_id)

        if not month_document:
            raise AppError(f"Fortnight {fortnight_id} was not found.", 404)

        if month_document["status"] == "Closed":
            raise AppError("Income cannot be updated for a closed month.", 409)

        mutable_month = deepcopy(month_document)
        target_fortnight = next(item for item in mutable_month["fortnights"] if item["id"] == fortnight_id)
        target_fortnight["incomeAmount"] = income_amount

        await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)

        return FortnightPeriodResponse(**target_fortnight)

    async def create_expense(self, user_id: str, payload: dict) -> MonthDetailResponse:
        recurrence_mode = payload.get("recurrence", {}).get("mode", "none")
        month_document = await self.month_periods_repository.find_month_by_fortnight_id(user_id, payload["fortnightPeriodId"])

        if not month_document:
            raise AppError(f"Fortnight {payload['fortnightPeriodId']} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)

        selected_fortnight = next(item for item in mutable_month["fortnights"] if item["id"] == payload["fortnightPeriodId"])
        self._validate_expense_payload(mutable_month, selected_fortnight, payload)

        recurrence_id = str(uuid4()) if recurrence_mode in {"future_once", "future_twice"} else None

        expenses_to_add = self._build_current_month_expenses(
            mutable_month,
            selected_fortnight,
            payload,
            recurrence_mode,
            recurrence_id,
        )

        mutable_month["expenses"].extend(expenses_to_add)
        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)

        if recurrence_id is not None:
            recurrence_document = self._build_recurrence_document(
                user_id,
                mutable_month,
                selected_fortnight,
                payload,
                recurrence_mode,
                recurrence_id,
            )
            await self.expense_recurrences_repository.create_recurrence(recurrence_document)
            await self._apply_recurrence_to_existing_future_months(user_id, mutable_month, recurrence_document)

        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def update_expense(self, user_id: str, expense_id: str, payload: dict) -> MonthDetailResponse:
        month_document = await self.month_periods_repository.find_month_by_expense_id(user_id, expense_id)

        if not month_document:
            raise AppError(f"Expense {expense_id} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)

        expense = next(item for item in mutable_month["expenses"] if item["id"] == expense_id)
        apply_scope = (payload.get("applyScope") or {}).get("scope", "current")

        if expense.get("recurrenceId") and apply_scope != "current":
            return await self._update_recurring_expense(user_id, mutable_month, expense, payload, apply_scope)

        fortnight = next(item for item in mutable_month["fortnights"] if item["id"] == expense["fortnightPeriodId"])
        self._validate_expense_payload(mutable_month, fortnight, payload)

        expense["name"] = payload["name"].strip()
        expense["description"] = payload.get("description", "").strip()
        expense["amount"] = payload["amount"]
        expense["estimatedPaymentDate"] = payload["estimatedPaymentDate"]

        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)
        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def delete_expense(self, user_id: str, expense_id: str, payload: dict) -> MonthDetailResponse:
        month_document = await self.month_periods_repository.find_month_by_expense_id(user_id, expense_id)

        if not month_document:
            raise AppError(f"Expense {expense_id} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)
        expense = next(item for item in mutable_month["expenses"] if item["id"] == expense_id)
        apply_scope = (payload.get("applyScope") or {}).get("scope", "current")

        if expense.get("recurrenceId") and apply_scope != "current":
            return await self._delete_recurring_expense(user_id, mutable_month, expense, apply_scope)

        mutable_month["expenses"] = [item for item in mutable_month["expenses"] if item["id"] != expense_id]
        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)
        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def toggle_expense_status(self, user_id: str, expense_id: str, is_paid: bool) -> MonthDetailResponse:
        month_document = await self.month_periods_repository.find_month_by_expense_id(user_id, expense_id)

        if not month_document:
            raise AppError(f"Expense {expense_id} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)

        expense = next(item for item in mutable_month["expenses"] if item["id"] == expense_id)
        expense["status"] = "Paid" if is_paid else "Pending"
        expense["paidAt"] = utc_now().isoformat() if is_paid else None

        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)
        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def close_month(self, user_id: str, month_id: str, confirm_close: bool) -> MonthDetailResponse:
        if not confirm_close:
            raise AppError("Closing a month requires confirmation.", 400)

        month_document = await self.month_periods_repository.find_month_by_id(user_id, month_id)

        if not month_document:
            raise AppError(f"Month {month_id} was not found.", 404)

        mutable_month = deepcopy(month_document)

        if mutable_month["status"] == "Closed":
            raise AppError("Only open months can be closed.", 409)

        mutable_month["status"] = "Closed"
        mutable_month["closedAt"] = utc_now().isoformat()

        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)
        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def _ensure_year_data(self, user_id: str, year: int) -> list[dict]:
        existing_months = await self.month_periods_repository.list_year_months(user_id, year)

        if existing_months:
            return existing_months

        created_months = await self.month_periods_repository.ensure_year_data(user_id, year)
        recurrences = await self.expense_recurrences_repository.list_active_for_user(user_id)

        for month_document in created_months:
            month_with_expenses = deepcopy(month_document)
            for recurrence in recurrences:
                if not self._recurrence_applies_to_month(recurrence, month_with_expenses["year"], month_with_expenses["monthNumber"]):
                    continue

                month_with_expenses["expenses"].extend(self._build_recurring_expenses_for_month(month_with_expenses, recurrence))

            await self.month_periods_repository.replace_month(user_id, month_with_expenses["id"], month_with_expenses)

        return await self.month_periods_repository.list_year_months(user_id, year)

    async def _apply_recurrence_to_existing_future_months(self, user_id: str, source_month: dict, recurrence: dict) -> None:
        future_months = await self.month_periods_repository.list_months_from_year(user_id, source_month["year"])

        for month_document in future_months:
            if (month_document["year"], month_document["monthNumber"]) <= (
                source_month["year"],
                source_month["monthNumber"],
            ):
                continue

            mutable_month = deepcopy(month_document)
            new_expenses = self._build_recurring_expenses_for_month(mutable_month, recurrence)

            if not new_expenses:
                continue

            mutable_month["expenses"].extend(new_expenses)
            await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)

    async def _update_recurring_expense(
        self,
        user_id: str,
        current_month: dict,
        current_expense: dict,
        payload: dict,
        apply_scope: str,
    ) -> MonthDetailResponse:
        recurrence = await self.expense_recurrences_repository.find_by_id(current_expense["recurrenceId"])

        if not recurrence:
            raise AppError("Recurring rule was not found.", 404)

        new_anchor_date = payload["estimatedPaymentDate"]
        new_fortnight = self._resolve_fortnight_by_date(current_month, new_anchor_date)
        self._validate_expense_payload(current_month, new_fortnight, payload)

        if recurrence["mode"] == "future_once":
            recurrence_updates = {
                "name": payload["name"].strip(),
                "description": payload.get("description", "").strip(),
                "amount": payload["amount"],
                "anchorFortnightType": new_fortnight["type"],
                "dayOffsetWithinFortnight": self._get_day_offset_within_fortnight(new_anchor_date, new_fortnight),
            }
        else:
            recurrence_updates = {
                "name": payload["name"].strip(),
                "description": payload.get("description", "").strip(),
                "amount": payload["amount"],
                "dayOffsetWithinFortnight": self._get_day_offset_within_fortnight(new_anchor_date, new_fortnight),
            }

        await self.expense_recurrences_repository.update_recurrence(recurrence["id"], recurrence_updates)
        future_months = await self.month_periods_repository.list_months_from_year(user_id, current_month["year"])
        comparison_mode = ">=" if apply_scope == "current_and_future" else ">"

        for month_document in future_months:
            mutable_month = deepcopy(month_document)
            updated = False
            for expense in mutable_month["expenses"]:
                if expense.get("recurrenceId") != recurrence["id"]:
                    continue
                if not self._matches_scope_by_date(expense["estimatedPaymentDate"], current_expense["estimatedPaymentDate"], comparison_mode):
                    continue

                target_fortnight = self._resolve_fortnight_for_recurring_update(mutable_month, recurrence, expense, recurrence_updates)
                expense["fortnightPeriodId"] = target_fortnight["id"]
                expense["name"] = recurrence_updates["name"]
                expense["description"] = recurrence_updates["description"]
                expense["amount"] = recurrence_updates["amount"]
                expense["estimatedPaymentDate"] = self._build_estimated_date_for_fortnight(
                    mutable_month,
                    target_fortnight,
                    recurrence_updates["dayOffsetWithinFortnight"],
                )
                updated = True

            if updated:
                await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)

        refreshed_month = await self.month_periods_repository.find_month_by_id(user_id, current_month["id"])
        return self._to_month_detail_or_error(refreshed_month, current_month["id"])

    async def _delete_recurring_expense(
        self,
        user_id: str,
        current_month: dict,
        current_expense: dict,
        apply_scope: str,
    ) -> MonthDetailResponse:
        recurrence_id = current_expense["recurrenceId"]
        await self.expense_recurrences_repository.deactivate_recurrence(recurrence_id)
        future_months = await self.month_periods_repository.list_months_from_year(user_id, current_month["year"])
        comparison_mode = ">=" if apply_scope == "current_and_future" else ">"

        for month_document in future_months:
            mutable_month = deepcopy(month_document)
            original_count = len(mutable_month["expenses"])
            mutable_month["expenses"] = [
                expense
                for expense in mutable_month["expenses"]
                if not (
                    expense.get("recurrenceId") == recurrence_id
                    and self._matches_scope_by_date(
                        expense["estimatedPaymentDate"],
                        current_expense["estimatedPaymentDate"],
                        comparison_mode,
                    )
                )
            ]

            if len(mutable_month["expenses"]) != original_count:
                await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)

        refreshed_month = await self.month_periods_repository.find_month_by_id(user_id, current_month["id"])
        return self._to_month_detail_or_error(refreshed_month, current_month["id"])

    def _build_current_month_expenses(
        self,
        month_document: dict,
        selected_fortnight: dict,
        payload: dict,
        recurrence_mode: str,
        recurrence_id: str | None,
    ) -> list[dict]:
        expenses = [self._create_expense_document(selected_fortnight, payload, recurrence_id, False)]

        if recurrence_mode in {"monthly_twice", "future_twice"}:
            counterpart_fortnight = self._get_counterpart_fortnight(month_document, selected_fortnight["type"])
            counterpart_payload = {
                **payload,
                "fortnightPeriodId": counterpart_fortnight["id"],
                "estimatedPaymentDate": self._build_estimated_date_for_fortnight(
                    month_document,
                    counterpart_fortnight,
                    self._get_day_offset_within_fortnight(payload["estimatedPaymentDate"], selected_fortnight),
                ),
            }
            expenses.append(self._create_expense_document(counterpart_fortnight, counterpart_payload, recurrence_id, False))

        return expenses

    def _build_recurrence_document(self, user_id: str, month_document: dict, selected_fortnight: dict, payload: dict, recurrence_mode: str, recurrence_id: str) -> dict:
        return {
            "id": recurrence_id,
            "userId": user_id,
            "name": payload["name"].strip(),
            "description": payload.get("description", "").strip(),
            "amount": payload["amount"],
            "mode": recurrence_mode,
            "anchorFortnightType": selected_fortnight["type"],
            "dayOffsetWithinFortnight": self._get_day_offset_within_fortnight(payload["estimatedPaymentDate"], selected_fortnight),
            "startYear": month_document["year"],
            "startMonth": month_document["monthNumber"],
            "isActive": True,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }

    def _build_recurring_expenses_for_month(self, month_document: dict, recurrence: dict) -> list[dict]:
        expenses: list[dict] = []
        existing_keys = {
            (expense.get("recurrenceId"), expense.get("fortnightPeriodId"), expense.get("estimatedPaymentDate"))
            for expense in month_document["expenses"]
        }

        if recurrence["mode"] == "future_once":
            target_fortnight = next(item for item in month_document["fortnights"] if item["type"] == recurrence["anchorFortnightType"])
            estimated_date = self._build_estimated_date_for_fortnight(
                month_document,
                target_fortnight,
                recurrence["dayOffsetWithinFortnight"],
            )
            if (recurrence["id"], target_fortnight["id"], estimated_date) not in existing_keys:
                expenses.append(
                    self._create_expense_document(
                        target_fortnight,
                        {
                            "name": recurrence["name"],
                            "description": recurrence["description"],
                            "amount": recurrence["amount"],
                            "estimatedPaymentDate": estimated_date,
                        },
                        recurrence["id"],
                        True,
                    )
                )
        else:
            for fortnight in month_document["fortnights"]:
                estimated_date = self._build_estimated_date_for_fortnight(
                    month_document,
                    fortnight,
                    recurrence["dayOffsetWithinFortnight"],
                )
                if (recurrence["id"], fortnight["id"], estimated_date) in existing_keys:
                    continue
                expenses.append(
                    self._create_expense_document(
                        fortnight,
                        {
                            "name": recurrence["name"],
                            "description": recurrence["description"],
                            "amount": recurrence["amount"],
                            "estimatedPaymentDate": estimated_date,
                        },
                        recurrence["id"],
                        True,
                    )
                )

        return expenses

    @staticmethod
    def _recurrence_applies_to_month(recurrence: dict, year: int, month: int) -> bool:
        return (year, month) >= (recurrence["startYear"], recurrence["startMonth"])

    @staticmethod
    def _matches_scope_by_date(date_value: str, anchor_date: str, comparison_mode: str) -> bool:
        return date_value >= anchor_date if comparison_mode == ">=" else date_value > anchor_date

    @staticmethod
    def _get_counterpart_fortnight(month_document: dict, selected_fortnight_type: str) -> dict:
        target_type = "Second" if selected_fortnight_type == "First" else "First"
        return next(item for item in month_document["fortnights"] if item["type"] == target_type)

    @staticmethod
    def _create_expense_document(fortnight: dict, payload: dict, recurrence_id: str | None, is_auto_generated: bool) -> dict:
        return {
            "id": str(uuid4()),
            "fortnightPeriodId": fortnight["id"],
            "name": payload["name"].strip(),
            "description": payload.get("description", "").strip(),
            "amount": payload["amount"],
            "estimatedPaymentDate": payload["estimatedPaymentDate"],
            "status": "Pending",
            "paidAt": None,
            "recurrenceId": recurrence_id,
            "isAutoGenerated": is_auto_generated,
        }

    @staticmethod
    def _get_day_offset_within_fortnight(estimated_payment_date: str, fortnight: dict) -> int:
        day = int(estimated_payment_date[-2:])
        return day - int(fortnight["startDate"][-2:])

    @staticmethod
    def _build_estimated_date_for_fortnight(month_document: dict, fortnight: dict, offset: int) -> str:
        start_day = int(fortnight["startDate"][-2:])
        end_day = int(fortnight["endDate"][-2:])
        computed_day = min(start_day + offset, end_day)
        return f"{month_document['year']}-{month_document['monthNumber']:02d}-{computed_day:02d}"

    @staticmethod
    def _resolve_fortnight_by_date(month_document: dict, estimated_payment_date: str) -> dict:
        day = int(estimated_payment_date[-2:])
        for fortnight in month_document["fortnights"]:
            start_day = int(fortnight["startDate"][-2:])
            end_day = int(fortnight["endDate"][-2:])
            if start_day <= day <= end_day:
                return fortnight
        raise AppError("Expense date must belong to one of the month fortnights.", 400)

    def _resolve_fortnight_for_recurring_update(self, month_document: dict, recurrence: dict, expense: dict, recurrence_updates: dict) -> dict:
        if recurrence["mode"] == "future_twice":
            return next(item for item in month_document["fortnights"] if item["id"] == expense["fortnightPeriodId"])

        return next(item for item in month_document["fortnights"] if item["type"] == recurrence_updates["anchorFortnightType"])

    @staticmethod
    def _ensure_month_is_open(month_document: dict) -> None:
        if month_document["status"] == "Closed":
            raise AppError("Operation is not allowed for a closed month.", 409)

    @staticmethod
    def _validate_expense_payload(month_document: dict, fortnight: dict, payload: dict) -> None:
        if not payload["name"].strip():
            raise AppError("Expense name is required.", 400)

        if payload["amount"] <= 0:
            raise AppError("Expense amount must be greater than zero.", 400)

        estimated_payment_date = payload["estimatedPaymentDate"]
        year, month, day = map(int, estimated_payment_date.split("-"))
        expected_month = f"{month_document['year']}-{month_document['monthNumber']:02d}"

        if year != month_document["year"] or month != month_document["monthNumber"]:
            raise AppError(
                f"Expense date must belong to the selected month ({expected_month}). Received {estimated_payment_date}.",
                400,
            )

        fortnight_start_day = int(fortnight["startDate"][-2:])
        fortnight_end_day = int(fortnight["endDate"][-2:])

        if day < fortnight_start_day or day > fortnight_end_day:
            raise AppError(
                f"Expense date must belong to the selected fortnight range ({fortnight['startDate']} to {fortnight['endDate']}). Received {estimated_payment_date}.",
                400,
            )

    @staticmethod
    def _to_month_summary(month_document: dict) -> dict:
        return {
            "id": month_document["id"],
            "year": month_document["year"],
            "monthNumber": month_document["monthNumber"],
            "monthName": month_document["monthName"],
            "status": month_document["status"],
            "closedAt": month_document["closedAt"],
        }

    @classmethod
    def _to_month_detail(cls, month_document: dict) -> MonthDetailResponse:
        return MonthDetailResponse(
            **cls._to_month_summary(month_document),
            fortnights=month_document["fortnights"],
            expenses=month_document["expenses"],
        )

    @classmethod
    def _to_month_detail_or_error(cls, month_document: dict | None, month_id: str) -> MonthDetailResponse:
        if not month_document:
            raise AppError(f"Month {month_id} was not found after update.", 404)

        return cls._to_month_detail(month_document)

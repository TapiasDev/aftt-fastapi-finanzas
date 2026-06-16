from copy import deepcopy
from uuid import uuid4

from app.core.exceptions import AppError
from app.repositories.month_periods_repository import MonthPeriodsRepository
from app.schemas.planner import FortnightPeriodResponse, MonthDetailResponse, YearDataResponse
from app.utils.dates import utc_now


class PlannerService:
    def __init__(self) -> None:
        self.month_periods_repository = MonthPeriodsRepository()

    async def get_available_years(self, user_id: str) -> list[int]:
        await self.month_periods_repository.ensure_default_data(user_id)
        years = await self.month_periods_repository.list_available_years(user_id)
        return sorted(years)

    async def get_year(self, user_id: str, year: int) -> YearDataResponse:
        await self.month_periods_repository.ensure_default_data(user_id)
        months = await self.month_periods_repository.list_year_months(user_id, year)

        if not months:
            raise AppError(f"Year {year} is not available.", 404)

        return YearDataResponse(selectedYear=year, months=[self._to_month_summary(item) for item in months])

    async def get_month(self, user_id: str, year: int, month_number: int) -> MonthDetailResponse:
        await self.month_periods_repository.ensure_default_data(user_id)
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
        month_document = await self.month_periods_repository.find_month_by_fortnight_id(user_id, payload["fortnightPeriodId"])

        if not month_document:
            raise AppError(f"Fortnight {payload['fortnightPeriodId']} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)

        fortnight = next(item for item in mutable_month["fortnights"] if item["id"] == payload["fortnightPeriodId"])
        self._validate_expense_payload(mutable_month, fortnight, payload)

        mutable_month["expenses"].append(
            {
                "id": str(uuid4()),
                "fortnightPeriodId": payload["fortnightPeriodId"],
                "name": payload["name"].strip(),
                "description": payload.get("description", "").strip(),
                "amount": payload["amount"],
                "estimatedPaymentDate": payload["estimatedPaymentDate"],
                "status": "Pending",
                "paidAt": None,
            }
        )

        updated_month = await self.month_periods_repository.replace_month(user_id, mutable_month["id"], mutable_month)
        return self._to_month_detail_or_error(updated_month, mutable_month["id"])

    async def update_expense(self, user_id: str, expense_id: str, payload: dict) -> MonthDetailResponse:
        month_document = await self.month_periods_repository.find_month_by_expense_id(user_id, expense_id)

        if not month_document:
            raise AppError(f"Expense {expense_id} was not found.", 404)

        mutable_month = deepcopy(month_document)
        self._ensure_month_is_open(mutable_month)

        expense = next(item for item in mutable_month["expenses"] if item["id"] == expense_id)
        fortnight = next(item for item in mutable_month["fortnights"] if item["id"] == expense["fortnightPeriodId"])
        self._validate_expense_payload(mutable_month, fortnight, payload)

        expense["name"] = payload["name"].strip()
        expense["description"] = payload.get("description", "").strip()
        expense["amount"] = payload["amount"]
        expense["estimatedPaymentDate"] = payload["estimatedPaymentDate"]

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

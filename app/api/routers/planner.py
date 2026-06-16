from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_session
from app.schemas.auth import AuthSessionResponse
from app.schemas.planner import (
    CloseMonthRequest,
    CreateExpenseRequest,
    DeleteExpenseRequest,
    FortnightPeriodResponse,
    MonthDetailResponse,
    SaveFortnightIncomeRequest,
    ToggleExpenseStatusRequest,
    UpdateExpenseRequest,
    YearDataResponse,
)
from app.services.planner_service import PlannerService

router = APIRouter(prefix="/planner", tags=["Planner"])

PLANNER_ERROR_RESPONSES = {
    400: {"description": "Validation or business rule error."},
    401: {"description": "No authenticated session."},
    403: {"description": "User is authenticated but not active yet."},
    404: {"description": "Requested financial resource was not found."},
    409: {"description": "Operation conflicts with the current planner state."},
}


def get_planner_service() -> PlannerService:
    return PlannerService()


@router.get(
    "/years",
    response_model=list[int],
    summary="List available years",
    description="Returns the available years for the authenticated active user.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def get_available_years(
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> list[int]:
    return await planner_service.get_available_years(session.user.id)


@router.get(
    "/years/{year}",
    response_model=YearDataResponse,
    summary="Get year data",
    description="Returns the selected year and its 12 month summaries for the authenticated user.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def get_year(
    year: int,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> YearDataResponse:
    return await planner_service.get_year(session.user.id, year)


@router.get(
    "/years/{year}/months/{month}",
    response_model=MonthDetailResponse,
    summary="Get month detail",
    description="Returns a month aggregate including fortnights and expenses.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def get_month(
    year: int,
    month: int,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.get_month(session.user.id, year, month)


@router.patch(
    "/fortnights/{fortnight_id}/income",
    response_model=FortnightPeriodResponse,
    summary="Save fortnight income",
    description="Updates the income amount for the selected fortnight if the month is open.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def save_fortnight_income(
    fortnight_id: str,
    payload: SaveFortnightIncomeRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> FortnightPeriodResponse:
    return await planner_service.save_fortnight_income(session.user.id, fortnight_id, payload.incomeAmount)


@router.post(
    "/expenses",
    response_model=MonthDetailResponse,
    summary="Create expense",
    description="Creates a pending expense in the selected fortnight and returns the updated month.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def create_expense(
    payload: CreateExpenseRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.create_expense(session.user.id, payload.model_dump())


@router.patch(
    "/expenses/{expense_id}/status",
    response_model=MonthDetailResponse,
    summary="Toggle expense payment status",
    description="Marks an expense as paid or pending and returns the updated month.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def toggle_expense_status(
    expense_id: str,
    payload: ToggleExpenseStatusRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.toggle_expense_status(session.user.id, expense_id, payload.isPaid)


@router.put(
    "/expenses/{expense_id}",
    response_model=MonthDetailResponse,
    summary="Update expense",
    description="Edits an existing expense and returns the updated month aggregate.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def update_expense(
    expense_id: str,
    payload: UpdateExpenseRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.update_expense(session.user.id, expense_id, payload.model_dump())


@router.delete(
    "/expenses/{expense_id}",
    response_model=MonthDetailResponse,
    summary="Delete expense",
    description="Deletes an expense and optionally affects future recurring instances.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def delete_expense(
    expense_id: str,
    payload: DeleteExpenseRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.delete_expense(session.user.id, expense_id, payload.model_dump())


@router.patch(
    "/months/{month_id}/close",
    response_model=MonthDetailResponse,
    summary="Close month",
    description="Closes an open month and returns the updated month in readonly mode.",
    responses=PLANNER_ERROR_RESPONSES,
)
async def close_month(
    month_id: str,
    payload: CloseMonthRequest,
    session: AuthSessionResponse = Depends(get_current_active_session),
    planner_service: PlannerService = Depends(get_planner_service),
) -> MonthDetailResponse:
    return await planner_service.close_month(session.user.id, month_id, payload.confirmClose)

from pydantic import BaseModel, Field


class FortnightPeriodResponse(BaseModel):
    id: str
    monthPeriodId: str
    type: str
    startDate: str
    endDate: str
    incomeAmount: float | int


class ExpenseResponse(BaseModel):
    id: str
    fortnightPeriodId: str
    name: str
    description: str
    amount: float | int
    estimatedPaymentDate: str
    status: str
    paidAt: str | None


class MonthSummaryResponse(BaseModel):
    id: str
    year: int
    monthNumber: int
    monthName: str
    status: str
    closedAt: str | None


class YearDataResponse(BaseModel):
    selectedYear: int
    months: list[MonthSummaryResponse]


class MonthDetailResponse(MonthSummaryResponse):
    fortnights: list[FortnightPeriodResponse]
    expenses: list[ExpenseResponse]


class SaveFortnightIncomeRequest(BaseModel):
    incomeAmount: float = Field(ge=0)


class CreateExpenseRequest(BaseModel):
    fortnightPeriodId: str
    name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    estimatedPaymentDate: str
    description: str = ""


class ToggleExpenseStatusRequest(BaseModel):
    isPaid: bool


class UpdateExpenseRequest(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    estimatedPaymentDate: str
    description: str = ""


class CloseMonthRequest(BaseModel):
    confirmClose: bool

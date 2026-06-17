from pydantic import BaseModel


class MonthPeriodDocument(BaseModel):
    id: str
    userId: str
    year: int
    monthNumber: int
    monthName: str
    fortnights: list[dict]
    expenses: list[dict]

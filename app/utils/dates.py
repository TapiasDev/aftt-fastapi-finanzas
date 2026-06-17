from calendar import month_name
from datetime import UTC, date, datetime
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_month_name(month_number: int) -> str:
    return month_name[month_number]


def create_month_aggregate(user_id: str, year: int, month_number: int) -> dict:
    month_id = str(uuid4())
    days_in_month = (date(year + (month_number // 12), (month_number % 12) + 1, 1) - date(year, month_number, 1)).days
    created_at = utc_now()
    first_fortnight_id = str(uuid4())
    second_fortnight_id = str(uuid4())

    return {
        "id": month_id,
        "userId": user_id,
        "year": year,
        "monthNumber": month_number,
        "monthName": get_month_name(month_number),
        "fortnights": [
            {
                "id": first_fortnight_id,
                "monthPeriodId": month_id,
                "type": "First",
                "startDate": f"{year}-{month_number:02d}-01",
                "endDate": f"{year}-{month_number:02d}-15",
                "incomeAmount": 0,
            },
            {
                "id": second_fortnight_id,
                "monthPeriodId": month_id,
                "type": "Second",
                "startDate": f"{year}-{month_number:02d}-16",
                "endDate": f"{year}-{month_number:02d}-{days_in_month:02d}",
                "incomeAmount": 0,
            },
        ],
        "expenses": [],
        "createdAt": created_at,
        "updatedAt": created_at,
    }

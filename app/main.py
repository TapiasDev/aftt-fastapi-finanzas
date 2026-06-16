import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers.auth import router as auth_router
from app.api.routers.planner import router as planner_router
from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.core.exceptions import AppError
from app.repositories.month_periods_repository import MonthPeriodsRepository
from app.repositories.sessions_repository import SessionsRepository
from app.repositories.users_repository import UsersRepository

logger = logging.getLogger("uvicorn.error")

ASCII_BANNER = r"""
========================================
    ███████╗██╗███╗   ██╗ █████╗ ███╗   ██╗███████╗ █████╗ ███████╗     █████╗ ██████╗ ██╗     █████╗ ███████╗████████╗████████╗
    ██╔════╝██║████╗  ██║██╔══██╗████╗  ██║╚══███╔╝██╔══██╗██╔════╝    ██╔══██╗██╔══██╗██║    ██╔══██╗██╔════╝╚══██╔══╝╚══██╔══╝
    █████╗  ██║██╔██╗ ██║███████║██╔██╗ ██║  ███╔╝ ███████║███████╗    ███████║██████╔╝██║    ███████║█████╗     ██║      ██║   
    ██╔══╝  ██║██║╚██╗██║██╔══██║██║╚██╗██║ ███╔╝  ██╔══██║╚════██║    ██╔══██║██╔═══╝ ██║    ██╔══██║██╔══╝     ██║      ██║   
    ██║     ██║██║ ╚████║██║  ██║██║ ╚████║███████╗██║  ██║███████║    ██║  ██║██║     ██║    ██║  ██║██║        ██║      ██║   
    ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝     ╚═╝    ╚═╝  ╚═╝╚═╝        ╚═╝      ╚═╝                                                                                                                           
========================================
""".strip("\n")


@asynccontextmanager
async def lifespan(_: FastAPI):
    is_ci = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("ENVIRONMENT") == "ci"

    if not is_ci:
        await connect_to_mongo()
        await UsersRepository().ensure_indexes()
        await SessionsRepository().ensure_indexes()
        await MonthPeriodsRepository().ensure_indexes()

    logger.info("\n%s", ASCII_BANNER)
    logger.info(
        "\n".join(
            [
                "========================================",
                "Estado: API INICIADA CORRECTAMENTE",
                f"Fecha UTC: {datetime.now(UTC).isoformat()}",
                f"Entorno: {os.getenv('APP_ENV', 'development')}",
                f"Despliegue: {os.getenv('ENVIRONMENT', 'local')}",
                f"Base de datos: {os.getenv('MONGO_DB_NAME', 'finanzas_aftt')}",
                "========================================",
            ]
        )
    )

    yield

    if not is_ci:
        await close_mongo_connection()


settings = get_settings()

openapi_tags = [
    {
        "name": "Root",
        "description": "Basic service health and root endpoints.",
    },
    {
        "name": "Auth",
        "description": "Authentication, first access password change and session lifecycle.",
    },
    {
        "name": "Planner",
        "description": "Private financial planner operations for the authenticated active user.",
    },
]

app = FastAPI(
    title="Expense Planner API",
    description=(
        "Backend API for Expense Planner with FastAPI, MongoDB and cookie-based sessions.\n\n"
        "Main flow:\n"
        "1. Login with email and password.\n"
        "2. If user status is `New`, force initial password change.\n"
        "3. Access private planner data only when the user is `Active`."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=openapi_tags,
    swagger_ui_parameters={
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "displayRequestDuration": True,
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.get(
    "/",
    tags=["Root"],
    summary="API root",
    description="Basic root endpoint to confirm the API is running.",
)
async def read_root() -> dict:
    return {
        "status": "active",
        "message": "Expense Planner API is running.",
    }


@app.get(
    "/health",
    tags=["Root"],
    summary="Health check",
    description="Simple health endpoint for local checks and container probes.",
)
async def healthcheck() -> dict:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(planner_router)

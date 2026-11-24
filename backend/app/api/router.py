"""Register implemented endpoints only."""

from fastapi import APIRouter, Depends

from app.api.rate_limits import (
    RATE_LIMIT_RESPONSES,
    limit_ai_requests,
    limit_upload_requests,
)
from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.settings import router as settings_router
from app.api.routes.upload import create_upload_router
from app.api.routes.upload_attempts import router as upload_attempts_router
from app.api.routes.workspaces import router as workspaces_router
from app.parsers.balance_sheet import parse_balance_sheet
from app.parsers.bank_statement import parse_bank_statement

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(
    ai_router,
    dependencies=[Depends(limit_ai_requests)],
    responses=RATE_LIMIT_RESPONSES,
)
api_router.include_router(workspaces_router)
api_router.include_router(dashboard_router)
api_router.include_router(upload_attempts_router)
api_router.include_router(
    create_upload_router(parse_bank_statement, balance_parser=parse_balance_sheet),
    dependencies=[Depends(limit_upload_requests)],
    responses=RATE_LIMIT_RESPONSES,
)

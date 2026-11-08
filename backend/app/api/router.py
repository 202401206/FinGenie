"""Register implemented endpoints only."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.upload import create_upload_router
from app.api.routes.workspaces import router as workspaces_router
from app.parsers.bank_statement import parse_bank_statement

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(create_upload_router(parse_bank_statement))

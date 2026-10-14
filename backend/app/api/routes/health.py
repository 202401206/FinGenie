"""Public liveness endpoint; does not check external services."""

from fastapi import APIRouter

from app.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse()

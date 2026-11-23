"""Apply expensive-request limits after the caller's identity is verified."""

from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.rate_limits import (
    RateLimitCapacityError,
    RequestGroup,
    RequestRateLimiter,
)
from app.core.security import require_user
from app.schemas.rate_limit_responses import RateLimitErrorResponse
from app.schemas.responses import CurrentUser

_initialization_lock = Lock()

RATE_LIMIT_RESPONSES = {
    429: {
        "model": RateLimitErrorResponse,
        "description": "This user's request allowance is exhausted.",
        "headers": {
            "Retry-After": {
                "description": "Seconds until this request group can be retried.",
                "schema": {"type": "integer", "minimum": 1},
            }
        },
    },
}


def get_rate_limiter(
    request: Request, config: Annotated[Settings, Depends(get_settings)]
) -> RequestRateLimiter:
    # ASGI test clients may omit lifespan; each app still gets its own counter.
    with _initialization_lock:
        if not hasattr(request.app.state, "rate_limiter"):
            request.app.state.rate_limiter = RequestRateLimiter(
                max_buckets=config.rate_limit_max_buckets
            )
        return request.app.state.rate_limiter


def enforce_limit(
    user: CurrentUser,
    group: RequestGroup,
    config: Settings,
    limiter: RequestRateLimiter,
) -> None:
    limit = (
        config.rate_limit_ai_requests
        if group == "ai"
        else config.rate_limit_upload_requests
    )
    try:
        retry_after = limiter.consume(
            user.id, group, limit=limit, window_seconds=config.rate_limit_window_seconds
        )
    except RateLimitCapacityError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "rate_limit_unavailable",
                "message": "Request limits are temporarily unavailable. Please retry later.",
            },
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    if retry_after:
        label = "AI" if group == "ai" else "upload"
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limit_exceeded",
                "message": f"Too many {label} requests. Please retry later.",
            },
            headers={"Retry-After": str(retry_after)},
        )


async def limit_ai_requests(
    user: Annotated[CurrentUser, Depends(require_user)],
    config: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RequestRateLimiter, Depends(get_rate_limiter)],
) -> None:
    enforce_limit(user, "ai", config, limiter)


async def limit_upload_requests(
    user: Annotated[CurrentUser, Depends(require_user)],
    config: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RequestRateLimiter, Depends(get_rate_limiter)],
) -> None:
    enforce_limit(user, "upload", config, limiter)

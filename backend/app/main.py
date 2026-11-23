"""FastAPI entry point. Run from backend/ with python -m uvicorn app.main:app."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.rate_limits import RequestRateLimiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.rate_limiter = RequestRateLimiter(
        max_buckets=settings.rate_limit_max_buckets
    )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["Retry-After"],
)
app.include_router(api_router, prefix="/api")

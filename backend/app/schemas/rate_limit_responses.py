"""Safe errors returned by the application's request limits."""

from typing import Literal

from pydantic import BaseModel


class RateLimitDetail(BaseModel):
    code: Literal["rate_limit_exceeded", "rate_limit_unavailable"]
    message: str


class RateLimitErrorResponse(BaseModel):
    detail: RateLimitDetail

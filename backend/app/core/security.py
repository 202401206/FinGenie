"""Verify bearer tokens with Supabase Auth, without trusting decoded JWT claims."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.responses import CurrentUser

bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "unauthorized", "message": "A valid access token is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )


def auth_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "auth_unavailable",
            "message": "Authentication is unavailable.",
        },
    )


def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is None or not credentials.credentials.strip():
        raise unauthorized()
    return credentials.credentials


async def get_auth_client(
    config: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[httpx.AsyncClient]:
    if config.supabase_url is None or config.supabase_publishable_key is None:
        raise auth_unavailable()
    # No global session, cookies, user token, secret key or service-role client.
    async with httpx.AsyncClient(
        base_url=str(config.supabase_url).rstrip("/"),
        headers={"apikey": config.supabase_publishable_key.get_secret_value()},
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        yield client


async def require_user(
    token: Annotated[str, Depends(require_bearer)],
    client: Annotated[httpx.AsyncClient, Depends(get_auth_client)],
) -> CurrentUser:
    """Auth validates the signature/expiry; return only its verified user UUID."""
    try:
        response = await client.get(
            "/auth/v1/user", headers={"Authorization": f"Bearer {token}"}
        )
    except httpx.RequestError:
        raise auth_unavailable() from None

    if response.status_code in (400, 401, 403):
        raise unauthorized()
    if response.status_code != 200:
        raise auth_unavailable()
    try:
        return CurrentUser.model_validate(response.json())
    except (ValueError, ValidationError):
        # Never return Auth's response body, tokens, email or upstream error text.
        raise auth_unavailable() from None

"""A small authenticated endpoint for checking the frontend's access token."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import require_user
from app.schemas.responses import CurrentUser

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=CurrentUser)
async def get_me(user: Annotated[CurrentUser, Depends(require_user)]) -> CurrentUser:
    return user

"""Read the dashboard of a saved document owned by the current user."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from app.api.workspace_dependencies import Repository, read_owned_document
from app.schemas.dashboard_responses import WorkspaceDashboardResponse
from app.schemas.error_responses import ErrorResponse
from app.services.workspace_dashboard import build_workspace_dashboard

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "/{workspace_id}/dashboard",
    response_model=WorkspaceDashboardResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required."},
        404: {"model": ErrorResponse, "description": "Workspace not found."},
        409: {"model": ErrorResponse, "description": "Parsed document is not ready."},
        503: {"model": ErrorResponse, "description": "Dashboard data is unavailable."},
    },
)
async def get_workspace_dashboard(
    workspace_id: UUID, repository: Repository
) -> Response:
    context = await read_owned_document(workspace_id, repository)
    try:
        payload = build_workspace_dashboard(context)
        return Response(content=payload.to_wire_json(), media_type="application/json")
    except (ValueError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "dashboard_unavailable",
                "message": "Dashboard data could not be confirmed.",
            },
        ) from None

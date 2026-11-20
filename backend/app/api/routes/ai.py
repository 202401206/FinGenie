"""FastAPI routes for AI Summary and Conversational Assistant."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.ai.chatbot import AIValidationError, chat_with_workspace
from app.ai.providers.groq_provider import (
    GroqAPIError,
    GroqConfigurationError,
    GroqError,
)
from app.ai.summary import generate_summary
from app.api.workspace_dependencies import Repository, read_owned_document
from app.schemas.common import DocumentType
from app.schemas.requests import ChatRequest
from app.schemas.responses import ChatResponse, SummaryResponse
from app.services.workspace_analysis import build_workspace_analysis

router = APIRouter(prefix="/workspaces", tags=["ai"])

SUMMARY_METRICS = {
    DocumentType.BANK_STATEMENT: {
        "total_credit",
        "total_debit",
        "net_cash_flow",
        "closing_balance",
    },
    DocumentType.BALANCE_SHEET: {
        "balance_difference",
        "working_capital",
        "current_ratio",
    },
}


async def get_ready_workspace_data(
    workspace_id: UUID, repository: Repository
) -> dict[str, Any]:
    context = await read_owned_document(workspace_id, repository)
    analysis = build_workspace_analysis(context, include_bank_balances=True)
    available = {
        metric.key for metric in analysis.metrics if metric.status == "available"
    }
    if (
        analysis.reliability != "valid"
        or not analysis.currency
        or not SUMMARY_METRICS[analysis.document_type] <= available
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "analysis_not_ready",
                "message": "The workspace needs complete, reliable results before using AI.",
            },
        )
    document = context.parsed_json
    # Include the fields of the verified document type for AI tool dispatch.
    return document.model_dump(mode="python", include=set(type(document).model_fields))


def _ai_validation_failed() -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "code": "ai_validation_failed",
            "message": "Numeric verification failed.",
        },
    )


def _handle_provider_error(exc: GroqError) -> HTTPException:
    """Translates provider exceptions into contract-compliant FastAPI HTTPExceptions.

    Ensures no raw API keys, upstream response bodies, or private financial content
    leak into client errors.
    """
    if isinstance(exc, GroqConfigurationError):
        return HTTPException(
            status_code=503,
            detail={
                "code": "provider_unavailable",
                "message": "AI service is not configured. Please contact support.",
            },
        )
    if isinstance(exc, GroqAPIError):
        if exc.status_code == 429:
            return HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limit_exceeded",
                    "message": "AI rate limit reached. Please retry in a few moments.",
                },
            )
        if exc.status_code in (503, 504):
            return HTTPException(
                status_code=503,
                detail={
                    "code": "provider_unavailable",
                    "message": "AI service is temporarily unavailable. Please retry later.",
                },
            )
        return HTTPException(
            status_code=502,
            detail={
                "code": "ai_provider_error",
                "message": "Upstream AI service encountered an error.",
            },
        )
    return HTTPException(
        status_code=502,
        detail={
            "code": "ai_provider_error",
            "message": "AI service failed unexpectedly.",
        },
    )


@router.post("/{workspace_id}/summary", response_model=SummaryResponse)
async def get_summary_endpoint(
    workspace_id: UUID,
    repository: Repository,
) -> SummaryResponse:
    """Generate an executive financial summary for the specified workspace."""
    data = await get_ready_workspace_data(workspace_id, repository)
    try:
        return await generate_summary(data)
    except AIValidationError:
        raise _ai_validation_failed() from None
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_workspace_data",
                "message": "The workspace cannot be summarized.",
            },
        ) from None
    except GroqError as exc:
        raise _handle_provider_error(exc) from exc


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def chat_endpoint(
    workspace_id: UUID,
    request: ChatRequest,
    repository: Repository,
) -> ChatResponse:
    """Ask a question about the workspace financial data using tool calling."""
    data = await get_ready_workspace_data(workspace_id, repository)
    try:
        return await chat_with_workspace(request.message, data)
    except AIValidationError:
        raise _ai_validation_failed() from None
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_chat_request", "message": str(exc)},
        ) from exc
    except GroqError as exc:
        raise _handle_provider_error(exc) from exc

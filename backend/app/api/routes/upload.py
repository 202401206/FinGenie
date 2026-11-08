"""Upload router factory. Mount only with the real reviewed bank parser."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.routing import APIRoute
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from app.db.dependencies import get_parsed_document_repository, get_workspace_repository
from app.db.repositories.parsed_documents import ParsedDocumentRepository
from app.db.repositories.workspaces import WorkspaceRepository
from app.schemas.upload_responses import UploadResponse
from app.services.source_dependencies import (
    SourceUploadAccess,
    get_source_upload_access,
    get_upload_recovery_service,
)
from app.services.upload import BankParser, UploadProcessingError, UploadService
from app.services.upload_recovery import UploadRecoveryService
from app.services.upload_validation import (
    DEFAULT_POLICY,
    UploadPolicy,
    UploadValidationError,
)

BODY_LIMIT_MESSAGE = "Upload request exceeds the supported size."


def create_upload_router(
    parser: BankParser, *, policy: UploadPolicy = DEFAULT_POLICY
) -> APIRouter:
    # Auth dependencies run before manual multipart parsing. Limit the entire
    # multipart body too, because file spooling precedes the bounded helper read.
    class BoundedUploadRoute(APIRoute):
        async def handle(self, scope, receive, send):
            consumed = 0

            async def bounded_receive():
                nonlocal consumed
                message = await receive()
                if message["type"] == "http.request":
                    consumed += len(message.get("body", b""))
                    if consumed > policy.max_bytes + 64 * 1024:
                        # Starlette's multipart parser catches this and closes its
                        # temporary files. The handler maps its safe detail to 413.
                        raise MultiPartException(BODY_LIMIT_MESSAGE)
                return message

            await super().handle(scope, bounded_receive, send)

    router = APIRouter(tags=["upload"], route_class=BoundedUploadRoute)

    @router.post(
        "/upload",
        response_model=UploadResponse,
        status_code=201,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["user_type", "document_type", "file"],
                            "properties": {
                                "user_type": {
                                    "type": "string",
                                    "enum": ["personal", "business"],
                                },
                                "document_type": {
                                    "type": "string",
                                    "enum": ["bank_statement"],
                                },
                                "file": {"type": "string", "format": "binary"},
                            },
                        }
                    }
                },
            },
        },
    )
    async def upload(
        request: Request,
        access: Annotated[SourceUploadAccess, Depends(get_source_upload_access)],
        save: Annotated[
            ParsedDocumentRepository, Depends(get_parsed_document_repository)
        ],
        recovery: Annotated[
            UploadRecoveryService, Depends(get_upload_recovery_service)
        ],
        workspaces: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    ) -> UploadResponse:
        service = UploadService(
            parser, access, save, recovery, workspaces, policy=policy
        )
        try:
            async with request.form(
                max_files=1, max_fields=2, max_part_size=64 * 1024
            ) as form:
                # Reject duplicates, owner fields and unexpected file/form fields.
                if sorted(form.keys()) != ["document_type", "file", "user_type"] or any(
                    len(form.getlist(key)) != 1 for key in form
                ):
                    raise HTTPException(
                        422,
                        detail={
                            "code": "invalid_upload_fields",
                            "message": "Exactly user_type, document_type and file are required.",
                        },
                    )
                file = form["file"]
                if (
                    not isinstance(file, UploadFile)
                    or not isinstance(form["user_type"], str)
                    or not isinstance(form["document_type"], str)
                ):
                    raise HTTPException(
                        422,
                        detail={
                            "code": "invalid_upload_fields",
                            "message": "Upload fields have invalid types.",
                        },
                    )
                return await service.process(
                    file,
                    user_type=form["user_type"],
                    document_type=form["document_type"],
                )
        except (UploadValidationError, UploadProcessingError) as error:
            headers = (
                {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
            )
            raise HTTPException(
                error.status_code,
                detail={"code": error.code, "message": str(error)},
                headers=headers,
            ) from None
        except StarletteHTTPException as error:
            if error.detail == BODY_LIMIT_MESSAGE:
                raise HTTPException(
                    413,
                    detail={"code": "file_too_large", "message": BODY_LIMIT_MESSAGE},
                ) from None
            if error.status_code == 400:
                raise HTTPException(
                    422,
                    detail={
                        "code": "invalid_upload_fields",
                        "message": "The multipart upload is invalid.",
                    },
                ) from None
            raise

    return router

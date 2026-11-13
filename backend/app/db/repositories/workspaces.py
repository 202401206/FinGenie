"""Focused, user-scoped reads using the existing Supabase Data API and RLS."""

import re
from decimal import Decimal
from typing import TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel, SecretStr, ValidationError

from app.db.errors import (
    DatabaseUnauthorized,
    DatabaseUnavailable,
    UnsupportedDocumentType,
    WorkspaceNotFound,
)
from app.db.models import (
    DocumentMetadata,
    Page,
    TransactionRecord,
    WorkspaceDetails,
    WorkspaceRecord,
)
from app.schemas.common import DocumentType

WORKSPACE_COLUMNS = "id,name,user_type,document_type,created_at"
DOCUMENT_COLUMNS = "id,status,original_filename,currency,period_start,period_end"
TRANSACTION_COLUMNS = "id,document_id,date,description,debit,credit,balance,source_row"
Record = TypeVar("Record", bound=BaseModel)


class WorkspaceRepository:
    def __init__(
        self, client: httpx.AsyncClient, user_id: UUID, access_token: str
    ) -> None:
        # The dependency supplies a verified user, a request-local client and the
        # original token. Never mutate client defaults or use an elevated key.
        self._client = client
        self._user_id = user_id
        self._access_token = SecretStr(access_token)

    async def list_workspaces(
        self, *, limit: int = 50, offset: int = 0
    ) -> Page[WorkspaceRecord]:
        self._validate_pagination(limit, offset)
        response = await self._get(
            "workspaces",
            {
                "select": WORKSPACE_COLUMNS,
                "user_id": f"eq.{self._user_id}",
                "order": "created_at.desc,id.desc",
                "limit": str(limit),
                "offset": str(offset),
            },
            count=True,
        )
        return self._page(response, WorkspaceRecord, limit, offset)

    async def get_workspace(self, workspace_id: UUID) -> WorkspaceDetails:
        response = await self._get(
            "workspaces",
            {
                "select": WORKSPACE_COLUMNS,
                "id": f"eq.{workspace_id}",
                "user_id": f"eq.{self._user_id}",
                "limit": "1",
            },
        )
        workspaces = self._records(response, WorkspaceRecord)
        if not workspaces:
            raise WorkspaceNotFound()
        if len(workspaces) != 1 or workspaces[0].id != workspace_id:
            raise DatabaseUnavailable()

        # Resolve the owned parent before querying any of its children. RLS also
        # applies to every request, including if ownership changes between reads.
        response = await self._get(
            "documents",
            {"select": DOCUMENT_COLUMNS, "workspace_id": f"eq.{workspace_id}"},
        )
        documents = self._records(response, DocumentMetadata)
        if len(documents) > 1:  # V1 enforces one document per workspace.
            raise DatabaseUnavailable()
        return WorkspaceDetails(workspace=workspaces[0], documents=documents)

    async def list_transactions(
        self, workspace_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Page[TransactionRecord]:
        self._validate_pagination(limit, offset)
        details = await self.get_workspace(workspace_id)
        if details.workspace.document_type != DocumentType.BANK_STATEMENT:
            raise UnsupportedDocumentType()
        if not details.documents:
            return Page(items=[], limit=limit, offset=offset, total=0)

        document_id = details.documents[0].id
        response = await self._get(
            "transactions",
            {
                "select": TRANSACTION_COLUMNS,
                "document_id": f"eq.{document_id}",
                "order": "source_row.asc,id.asc",
                "limit": str(limit),
                "offset": str(offset),
            },
            count=True,
        )
        page = self._page(response, TransactionRecord, limit, offset)
        if any(item.document_id != document_id for item in page.items):
            raise DatabaseUnavailable()
        return page

    async def _get(
        self, table: str, params: dict[str, str], *, count: bool = False
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._access_token.get_secret_value()}",
            "Accept": "application/json",
        }
        if count:
            headers["Prefer"] = "count=exact"
        try:
            response = await self._client.get(
                f"/rest/v1/{table}", params=params, headers=headers
            )
        except httpx.RequestError:
            raise DatabaseUnavailable() from None
        if response.status_code == 401:
            raise DatabaseUnauthorized()
        # PostgREST can return 416 for an offset beyond the last row. The page
        # reader accepts only its documented range error with an exact total.
        if response.status_code not in (200, 206) and not (
            count and response.status_code == 416
        ):
            raise DatabaseUnavailable()
        return response

    @staticmethod
    def _records(response: httpx.Response, model: type[Record]) -> list[Record]:
        try:
            # Decode numbers directly as Decimal, never through binary floats.
            rows = response.json(parse_float=Decimal)
            if not isinstance(rows, list):
                raise ValueError()
            return [model.model_validate(row) for row in rows]
        except (ValueError, ValidationError):
            raise DatabaseUnavailable() from None

    @classmethod
    def _page(
        cls, response: httpx.Response, model: type[Record], limit: int, offset: int
    ) -> Page[Record]:
        match = re.fullmatch(
            r"(?:\d+-\d+|\*)/(\d+)", response.headers.get("Content-Range", "")
        )
        if match is None:
            raise DatabaseUnavailable()
        total = int(match[1])
        if response.status_code == 416:
            try:
                error = response.json()
                if (
                    not isinstance(error, dict)
                    or error.get("code") != "PGRST103"
                    or offset < total
                ):
                    raise ValueError()
            except ValueError:
                raise DatabaseUnavailable() from None
            return Page(items=[], limit=limit, offset=offset, total=total)
        items = cls._records(response, model)
        if len(items) > limit or (items and offset + len(items) > total):
            raise DatabaseUnavailable()
        return Page(items=items, limit=limit, offset=offset, total=total)

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        if type(limit) is not int or type(offset) is not int:
            raise ValueError("Pagination values must be integers.")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Limit must be 1-100 and offset must be nonnegative.")

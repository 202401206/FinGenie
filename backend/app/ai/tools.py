"""Tool registry, schemas, and execution engine for deterministic financial tools."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.schemas.responses import SourceRefModel


@dataclass
class SourceRef:
    """Audit reference pointing back to source file, sheet, rows, and JSON paths."""

    document_id: str
    sheet_name: str | None
    source_rows: list[int]
    field_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "sheet_name": self.sheet_name,
            "source_rows": self.source_rows,
            "field_paths": self.field_paths,
        }


def merge_source_refs(tool_results: list["ToolResult"]) -> list[SourceRefModel]:
    """Merge source rows and field paths across multiple tool results by document and sheet."""
    groups: dict[tuple[str, str | None], tuple[set[int], list[str]]] = {}

    for tr in tool_results:
        for ref in tr.source_refs:
            key = (ref.document_id, ref.sheet_name)
            if key not in groups:
                groups[key] = (set(), [])
            groups[key][0].update(ref.source_rows)
            for path in ref.field_paths:
                if path not in groups[key][1]:
                    groups[key][1].append(path)

    return [
        SourceRefModel(
            document_id=doc_id,
            sheet_name=sheet,
            source_rows=sorted(list(rows)),
            field_paths=paths,
        )
        for (doc_id, sheet), (rows, paths) in groups.items()
    ]


@dataclass
class ToolResult:
    """Standardized output returned by every deterministic calculation tool."""

    name: str
    value: Decimal | float | int | None
    unit: str
    calculation_id: str
    status: Literal["available", "unavailable"] = "available"
    reason: str | None = None
    source_refs: list[SourceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": float(self.value)
            if isinstance(self.value, Decimal)
            else self.value,
            "unit": self.unit,
            "calculation_id": self.calculation_id,
            "status": self.status,
            "reason": self.reason,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
        }


# --- Tool Schemas for Groq Function Calling ---
FINANCIAL_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "bank_total_credit",
            "description": "Calculates the total credits (all incoming money / deposits) for the statement period.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bank_total_debit",
            "description": "Calculates the total debits (all outgoing money / expenses / withdrawals) for the statement period.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bank_net_cash_flow",
            "description": "Calculates net cash flow (total credits minus total debits) for the statement period.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bank_closing_balance",
            "description": "Retrieves the closing balance at the end of the bank statement period.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "balance_sheet_working_capital",
            "description": "Calculates working capital (current assets minus current liabilities) in base currency.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "balance_sheet_current_ratio",
            "description": "Calculates current ratio (current assets divided by current liabilities). Evaluates short-term liquidity.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "balance_sheet_verify_reconciliation",
            "description": "Verifies that Assets = Liabilities + Equity. Returns balance difference.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


class ToolExecutionError(Exception):
    """Raised when an unrecognized tool is requested or execution fails."""


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    workspace_data: dict[str, Any],
) -> ToolResult:
    """Executes a financial calculation tool deterministically on workspace data."""
    if "transactions" in workspace_data:
        return _execute_bank_tool(tool_name, arguments, workspace_data)
    if "assets" in workspace_data:
        return _execute_balance_sheet_tool(tool_name, arguments, workspace_data)

    raise ToolExecutionError(
        f"Unsupported or unrecognized workspace data format for tool '{tool_name}'."
    )


def _get_document_meta(data: dict[str, Any]) -> tuple[str, str | None]:
    source_meta = data.get("source_metadata", {})
    doc_id = source_meta.get("document_id", "default-doc-id")
    sheet_name = source_meta.get("sheet_name")
    return doc_id, sheet_name


def _execute_bank_tool(
    name: str,
    _arguments: dict[str, Any],
    data: dict[str, Any],
) -> ToolResult:
    doc_id, sheet_name = _get_document_meta(data)
    currency = data.get("currency", "INR")
    transactions = data.get("transactions", [])

    if name == "bank_total_credit":
        total = Decimal("0")
        source_rows: list[int] = []
        field_paths: list[str] = []
        for i, tx in enumerate(transactions):
            credit = Decimal(str(tx.get("credit", 0)))
            if credit > 0:
                total += credit
                source_rows.append(tx.get("source_row", i + 1))
                field_paths.append(f"transactions[{i}].credit")

        return ToolResult(
            name=name,
            value=total,
            unit=currency,
            calculation_id="bank.total_credit.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=source_rows,
                    field_paths=field_paths,
                )
            ],
        )

    if name == "bank_total_debit":
        total = Decimal("0")
        source_rows = []
        field_paths = []
        for i, tx in enumerate(transactions):
            debit = Decimal(str(tx.get("debit", 0)))
            if debit > 0:
                total += debit
                source_rows.append(tx.get("source_row", i + 1))
                field_paths.append(f"transactions[{i}].debit")

        return ToolResult(
            name=name,
            value=total,
            unit=currency,
            calculation_id="bank.total_debit.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=source_rows,
                    field_paths=field_paths,
                )
            ],
        )

    if name == "bank_net_cash_flow":
        credits = Decimal("0")
        debits = Decimal("0")
        source_rows = []
        field_paths = []
        for i, tx in enumerate(transactions):
            cr = Decimal(str(tx.get("credit", 0)))
            dr = Decimal(str(tx.get("debit", 0)))
            if cr > 0:
                credits += cr
                source_rows.append(tx.get("source_row", i + 1))
                field_paths.append(f"transactions[{i}].credit")
            if dr > 0:
                debits += dr
                source_rows.append(tx.get("source_row", i + 1))
                field_paths.append(f"transactions[{i}].debit")

        net = credits - debits
        return ToolResult(
            name=name,
            value=net,
            unit=currency,
            calculation_id="bank.net_cash_flow.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=source_rows,
                    field_paths=field_paths,
                )
            ],
        )

    if name == "bank_closing_balance":
        closing = Decimal(str(data.get("closing_balance", 0)))
        closing_row = (
            data.get("source_locations", {})
            .get("closing_balance", {})
            .get("source_row", 0)
        )
        return ToolResult(
            name=name,
            value=closing,
            unit=currency,
            calculation_id="bank.closing_balance.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=[closing_row] if closing_row else [],
                    field_paths=["closing_balance"],
                )
            ],
        )

    raise ToolExecutionError(f"Unknown bank statement tool: '{name}'.")


def _execute_balance_sheet_tool(
    name: str,
    _arguments: dict[str, Any],
    data: dict[str, Any],
) -> ToolResult:
    doc_id, sheet_name = _get_document_meta(data)
    currency = data.get("currency", "INR")
    scale = Decimal(str(data.get("unit_scale", 1)))

    assets = data.get("assets", {})
    liabilities = data.get("liabilities", {})
    equity = data.get("equity", {})

    curr_assets = sum(
        Decimal(str(item.get("value", 0))) for item in assets.get("current", [])
    )
    curr_liab = sum(
        Decimal(str(item.get("value", 0))) for item in liabilities.get("current", [])
    )

    if name == "balance_sheet_working_capital":
        working_capital = (curr_assets - curr_liab) * scale
        bs_rows = [
            item.get("source_row", 0)
            for item in assets.get("current", []) + liabilities.get("current", [])
            if item.get("source_row", 0) > 0
        ]
        return ToolResult(
            name=name,
            value=working_capital,
            unit=currency,
            calculation_id="balance_sheet.working_capital.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=bs_rows,
                    field_paths=["assets.current", "liabilities.current"],
                )
            ],
        )

    if name == "balance_sheet_current_ratio":
        if curr_liab == 0:
            return ToolResult(
                name=name,
                value=None,
                unit="ratio",
                calculation_id="balance_sheet.current_ratio.v1",
                status="unavailable",
                reason="Current liabilities are zero; cannot divide by zero.",
            )

        ratio = round(curr_assets / curr_liab, 2)
        cr_rows = [
            item.get("source_row", 0)
            for item in assets.get("current", []) + liabilities.get("current", [])
            if item.get("source_row", 0) > 0
        ]
        return ToolResult(
            name=name,
            value=ratio,
            unit="ratio",
            calculation_id="balance_sheet.current_ratio.v1",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=cr_rows,
                    field_paths=["assets.current", "liabilities.current"],
                )
            ],
        )

    if name == "balance_sheet_verify_reconciliation":
        total_assets = Decimal(str(assets.get("total", 0)))
        total_liab = Decimal(str(liabilities.get("total", 0)))
        total_eq = Decimal(str(equity.get("total", 0)))
        diff = total_assets - (total_liab + total_eq)

        recon_rows = [
            r
            for r in [
                data.get("source_locations", {})
                .get("assets.total", {})
                .get("source_row", 0),
                data.get("source_locations", {})
                .get("liabilities.total", {})
                .get("source_row", 0),
                data.get("source_locations", {})
                .get("equity.total", {})
                .get("source_row", 0),
            ]
            if r > 0
        ]

        return ToolResult(
            name=name,
            value=diff * scale,
            unit=currency,
            calculation_id="balance_sheet.balance_difference.v1",
            status="available" if diff == 0 else "unavailable",
            reason=None
            if diff == 0
            else "Balance sheet does not reconcile: Assets != Liabilities + Equity.",
            source_refs=[
                SourceRef(
                    document_id=doc_id,
                    sheet_name=sheet_name,
                    source_rows=recon_rows,
                    field_paths=["assets.total", "liabilities.total", "equity.total"],
                )
            ],
        )

    raise ToolExecutionError(f"Unknown balance sheet tool: '{name}'.")

"""Analysis of validated saved documents using the existing KPI functions."""

from app.analysis.balance_sheet_kpis import analyze_balance_sheet
from app.analysis.bank_kpis import analyze_bank_statement
from app.db.parsed_read_models import ParsedBalanceSheet, ParsedDocumentContext
from app.schemas.analysis_responses import WorkspaceAnalysisResponse


def build_workspace_analysis(
    context: ParsedDocumentContext,
    *,
    include_bank_balances: bool = False,
) -> WorkspaceAnalysisResponse:
    statement = context.parsed_json
    data = statement.model_dump(mode="python")
    workspace_id = str(context.workspace.id)

    if isinstance(statement, ParsedBalanceSheet):
        result = analyze_balance_sheet(data, workspace_id, include_current_ratio=True)
        warnings = result["warnings"]
        metadata_reason = None
        if statement.currency is None or statement.unit_scale is None:
            metadata_reason = "Confirm the balance sheet currency and unit scale."

        # These two KPIs sum classified current items. An empty section or
        # unresolved line cannot establish a complete current-assets/liabilities sum.
        # The parser retains prior-period values for reference alongside current rows.
        current_items = statement.assets.current + statement.liabilities.current
        incomplete_current = (
            not statement.assets.current
            or not statement.liabilities.current
            or any(
                item.get("reason") != "prior_period_value"
                for item in statement.unmapped
            )
            or any(
                item.value is None or not item.canonical_field for item in current_items
            )
        )
        for metric in result["metrics"]:
            if (
                metric["key"] == "balance_difference"
                and metric["value"] is not None
                and statement.unit_scale is not None
            ):
                # The calculator returns this difference in reported units.
                # Public monetary metrics use base currency.
                metric["value"] *= statement.unit_scale
            reason = metadata_reason
            if (
                reason is None
                and incomplete_current
                and metric["key"] in {"working_capital", "current_ratio"}
            ):
                reason = "Current asset or liability classifications or amounts are incomplete."
            if reason:
                metric.update(value=None, status="unavailable", reason=reason)
                if reason not in warnings:
                    warnings.append(reason)

        if metadata_reason or (incomplete_current and result["reliability"] == "valid"):
            result["reliability"] = "insufficient_data"
    else:
        result = analyze_bank_statement(
            data, workspace_id, include_balance_metrics=include_bank_balances
        )
        for metric in result["metrics"]:
            if metric["unit"] is None:
                metric["unit"] = "unknown"

    return WorkspaceAnalysisResponse.model_validate(result)

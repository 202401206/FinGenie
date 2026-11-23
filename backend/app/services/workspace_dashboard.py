"""Build a public dashboard from an already verified owned document."""

from decimal import Decimal, localcontext

from app.analysis.dashboard_metrics import (
    balance_dashboard_metrics,
    bank_dashboard_metrics,
)
from app.db.parsed_read_models import ParsedBalanceSheet, ParsedDocumentContext
from app.schemas.analysis_responses import AnalysisMetric
from app.schemas.dashboard_responses import (
    DashboardMetadata,
    WorkspaceDashboardResponse,
)
from app.services.workspace_analysis import build_workspace_analysis


def _calculation_precision(context: ParsedDocumentContext) -> int:
    # Existing KPI functions use the current Decimal context. Allow the full saved
    # exponent range before combining them with the dashboard's exact sums.
    statement = context.parsed_json
    if isinstance(statement, ParsedBalanceSheet):
        items = statement.assets.current + statement.assets.non_current
        items += statement.liabilities.current + statement.liabilities.non_current
        amounts = [item.value for item in items if item.value is not None]
        amounts += [
            section.total
            for section in (statement.assets, statement.liabilities, statement.equity)
            if section.total is not None
        ]
    else:
        amounts = [
            value
            for row in statement.transactions
            for value in (row.credit, row.debit, row.balance)
        ]
        amounts += [
            value
            for value in (statement.opening_balance, statement.closing_balance)
            if value is not None
        ]
    amounts = [Decimal(value) for value in amounts]
    if not amounts:
        return 38
    return max(
        38,
        max(value.adjusted() for value in amounts)
        - min(value.as_tuple().exponent for value in amounts)
        + len(str(len(amounts)))
        + 16,
    )


def build_workspace_dashboard(
    context: ParsedDocumentContext,
) -> WorkspaceDashboardResponse:
    statement = context.parsed_json
    with localcontext() as decimal_context:
        decimal_context.prec = _calculation_precision(context)
        analysis = build_workspace_analysis(context, include_bank_balances=True)
        if isinstance(statement, ParsedBalanceSheet):
            extra = balance_dashboard_metrics(statement)
            metadata = DashboardMetadata(
                company=statement.company,
                currency=statement.currency,
                period_start=None,
                period_end=None,
                reporting_date=statement.reporting_date,
                unit_scale=statement.unit_scale,
            )
        else:
            extra = bank_dashboard_metrics(statement)
            metadata = DashboardMetadata(
                company=None,
                currency=statement.currency,
                period_start=statement.period_start,
                period_end=statement.period_end,
                reporting_date=None,
                unit_scale=None,
            )
        analysis.metrics.extend(
            AnalysisMetric.model_validate(item) for item in extra["metrics"]
        )
        analysis.warnings = list(dict.fromkeys(analysis.warnings + extra["warnings"]))
        return WorkspaceDashboardResponse(
            workspace_id=context.workspace.id,
            document_id=context.document_id,
            document_type=context.workspace.document_type,
            metadata=metadata,
            analysis=analysis,
            charts=extra["charts"],
            largest_inflows=extra["largest_inflows"],
            largest_outflows=extra["largest_outflows"],
        )

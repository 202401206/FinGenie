"""Analysis module for FinGenie financial statement processing."""

from app.analysis.balance_sheet_kpis import (
    analyze_balance_sheet,
    calculate_balance_difference,
    calculate_current_ratio,
    calculate_working_capital,
    serialize_analysis_result,
)
from app.analysis.bank_kpis import (
    analyze_bank_statement,
    calculate_closing_balance,
    calculate_net_cash_flow,
    calculate_opening_balance,
    calculate_total_credit,
    calculate_total_debit,
)

__all__ = [
    "calculate_working_capital",
    "calculate_current_ratio",
    "calculate_balance_difference",
    "analyze_balance_sheet",
    "serialize_analysis_result",
    "analyze_bank_statement",
    "calculate_closing_balance",
    "calculate_net_cash_flow",
    "calculate_opening_balance",
    "calculate_total_credit",
    "calculate_total_debit",
]

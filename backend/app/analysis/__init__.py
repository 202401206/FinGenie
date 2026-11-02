"""Analysis module for FinGenie financial statement processing."""

from app.analysis.balance_sheet_kpis import (
    analyze_balance_sheet,
    calculate_balance_difference,
    calculate_current_ratio,
    calculate_working_capital,
    serialize_analysis_result,
)

try:
    from app.analysis.bank_kpis import (
        calculate_bank_analysis,
        calculate_net_cash_flow,
        calculate_total_credit,
        calculate_total_debit,
        get_closing_balance,
        get_opening_balance,
    )

    __all__ = [
        "calculate_working_capital",
        "calculate_current_ratio",
        "calculate_balance_difference",
        "analyze_balance_sheet",
        "serialize_analysis_result",
        "calculate_bank_analysis",
        "calculate_net_cash_flow",
        "calculate_total_credit",
        "calculate_total_debit",
        "get_closing_balance",
        "get_opening_balance",
    ]
except ImportError:
    __all__ = [
        "calculate_working_capital",
        "calculate_current_ratio",
        "calculate_balance_difference",
        "analyze_balance_sheet",
        "serialize_analysis_result",
    ]

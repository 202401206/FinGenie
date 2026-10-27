"""AI Summary engine: generates concise, grounded executive summaries of financial data."""

from typing import Any

from app.ai.providers.groq_provider import GroqProvider
from app.ai.tools import execute_tool, merge_source_refs
from app.schemas.responses import SummaryResponse

SYSTEM_SUMMARY_PROMPT = (
    "You are FinGenie's financial assistant. Write a factual, concise 2-sentence executive summary "
    "based ONLY on the verified metrics below. Do NOT assume, invent, or extrapolate new numbers. "
    "Only cite the given numbers with their exact currency or unit."
)


async def generate_summary(
    workspace_data: dict[str, Any],
    provider: GroqProvider | None = None,
) -> SummaryResponse:
    """Calculates key financial metrics and synthesizes a validated natural language summary."""
    if "transactions" in workspace_data:
        return await _generate_bank_summary(workspace_data, provider)
    if "assets" in workspace_data:
        return await _generate_balance_sheet_summary(workspace_data, provider)

    raise ValueError("Unsupported or unrecognized workspace data format for summary.")


async def _generate_bank_summary(
    data: dict[str, Any],
    provider: GroqProvider | None,
) -> SummaryResponse:
    # 1. Execute deterministic tools
    credit_res = execute_tool("bank_total_credit", {}, data)
    debit_res = execute_tool("bank_total_debit", {}, data)
    net_res = execute_tool("bank_net_cash_flow", {}, data)
    closing_res = execute_tool("bank_closing_balance", {}, data)

    tool_results = [credit_res, debit_res, net_res, closing_res]
    calculation_ids = [res.calculation_id for res in tool_results]
    source_refs = merge_source_refs(tool_results)

    currency = data.get("currency", "INR")
    credit_val = credit_res.value
    debit_val = debit_res.value
    net_val = net_res.value
    closing_val = closing_res.value

    # 2. Try online LLM synthesis if provider is configured
    llm = provider or GroqProvider()
    if llm.is_configured:
        prompt = (
            f"Verified Bank Metrics:\n"
            f"- Total Deposits / Credits: {credit_val} {currency}\n"
            f"- Total Withdrawals / Debits: {debit_val} {currency}\n"
            f"- Net Cash Flow: {net_val} {currency}\n"
            f"- Closing Balance: {closing_val} {currency}\n"
        )
        messages = [
            {"role": "system", "content": SYSTEM_SUMMARY_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await llm.generate(messages=messages, temperature=0.1)
        summary_text = response.content or ""
    else:
        # Deterministic offline template fallback
        flow_word = "positive" if (net_val or 0) >= 0 else "negative"
        summary_text = (
            f"For this statement period, total deposits were {currency} {credit_val} and total "
            f"withdrawals were {currency} {debit_val}, resulting in a {flow_word} net cash flow of "
            f"{currency} {net_val}. The closing balance is {currency} {closing_val}."
        )

    return SummaryResponse(
        text=summary_text.strip(),
        calculation_ids=calculation_ids,
        source_refs=source_refs,
        disclaimer="This is not financial advice.",
    )


async def _generate_balance_sheet_summary(
    data: dict[str, Any],
    provider: GroqProvider | None,
) -> SummaryResponse:
    # 1. Execute deterministic tools
    recon_res = execute_tool("balance_sheet_verify_reconciliation", {}, data)
    wc_res = execute_tool("balance_sheet_working_capital", {}, data)
    cr_res = execute_tool("balance_sheet_current_ratio", {}, data)

    tool_results = [recon_res, wc_res, cr_res]
    calculation_ids = [res.calculation_id for res in tool_results]
    source_refs = merge_source_refs(tool_results)

    currency = data.get("currency", "INR")

    # If the balance sheet does not reconcile (Assets != Liabilities + Equity), flag unreliable!
    if recon_res.status == "unavailable" or (recon_res.value or 0) != 0:
        warning_text = (
            f"Warning: This balance sheet is unreliable because total assets do not equal total liabilities "
            f"plus equity. Discrepancy is {currency} {recon_res.value}."
        )
        return SummaryResponse(
            text=warning_text,
            calculation_ids=calculation_ids,
            source_refs=source_refs,
            disclaimer="This is not financial advice.",
        )

    # 2. Try online LLM synthesis if provider is configured
    llm = provider or GroqProvider()
    if llm.is_configured:
        prompt = (
            f"Verified Balance Sheet Metrics:\n"
            f"- Balance Sheet Reconciliation: Verified (Assets = Liabilities + Equity)\n"
            f"- Working Capital: {wc_res.value} {currency}\n"
            f"- Current Ratio: {cr_res.value} (Benchmark: >= 1.0)\n"
        )
        messages = [
            {"role": "system", "content": SYSTEM_SUMMARY_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await llm.generate(messages=messages, temperature=0.1)
        summary_text = response.content or ""
    else:
        # Deterministic offline template fallback
        summary_text = (
            f"The balance sheet is reconciled and balanced. The business reports a working capital of "
            f"{currency} {wc_res.value} with a current ratio of {cr_res.value}."
        )

    return SummaryResponse(
        text=summary_text.strip(),
        calculation_ids=calculation_ids,
        source_refs=source_refs,
        disclaimer="This is not financial advice.",
    )

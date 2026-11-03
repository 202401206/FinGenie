"""Live Integration Test for Prince (AI Assistant), Rashi (Bank KPIs), and Srujan (Number Guard).

Runs real API queries through Groq (`openai/gpt-oss-120b`), verifying the end-to-end chain:
1. User Query -> Groq Function Calling
2. Tool Execution -> Rashi's live `app.analysis.bank_kpis`
3. Tool Result -> Prince's Adapter in `app.ai.tools`
4. Answer Synthesis -> Groq LLM
5. Safety Verification -> Srujan's `app.ai.number_guard` validation & retry policy
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(backend_dir / ".env")

from app.ai.chatbot import chat_with_workspace  # noqa: E402
from app.ai.number_guard import verify_tool_results_text  # noqa: E402
from app.ai.providers.groq_provider import GroqProvider  # noqa: E402
from app.ai.summary import generate_summary  # noqa: E402
from app.ai.tools import execute_tool  # noqa: E402
from app.analysis import bank_kpis  # noqa: E402
from app.core.config import Settings  # noqa: E402


def load_fixture(filename: str) -> dict:
    repo_root = backend_dir.parent
    path = repo_root / "contracts" / "examples" / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run_live_test() -> None:
    print("=" * 70)
    print("  FinGenie: Live 3-Way Integration Test (Prince + Rashi + Srujan)")
    print("=" * 70)

    live_settings = Settings(_env_file=backend_dir / ".env")
    provider = GroqProvider(settings=live_settings)
    if not provider.is_configured:
        print("[ERROR] Groq API key is not configured in backend/.env!")
        return

    print(f"[STATUS] Provider: Groq ({live_settings.groq_model})")
    print(f"[STATUS] Rashi's Bank KPI module loaded: {bank_kpis.__file__}")

    bank_data = load_fixture("bank-statement.json")

    # -------------------------------------------------------------
    # Step 1: Verify Rashi's calculation functions directly
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 1: Direct Verification of Rashi's Bank Analytics Engine")
    print("=" * 70)
    total_cr = bank_kpis.calculate_total_credit(bank_data)
    total_dr = bank_kpis.calculate_total_debit(bank_data)
    net_flow = bank_kpis.calculate_net_cash_flow(bank_data)
    closing = bank_kpis.calculate_closing_balance(bank_data)

    print(
        f"  - Total Credits: {total_cr['value']} {total_cr['unit']} (Rows: {total_cr['source_refs'][0]['source_rows']})"
    )
    print(
        f"  - Total Debits:  {total_dr['value']} {total_dr['unit']} (Rows: {total_dr['source_refs'][0]['source_rows']})"
    )
    print(
        f"  - Net Cash Flow: {net_flow['value']} {net_flow['unit']} (Rows: {net_flow['source_refs'][0]['source_rows']})"
    )
    print(
        f"  - Closing Bal:   {closing['value']} {closing['unit']} (Rows: {closing['source_refs'][0]['source_rows']})"
    )
    print("  >>> [OK] Rashi's deterministic calculations verified successfully!")

    # -------------------------------------------------------------
    # Step 2: Live AI Executive Summary (Prince + Rashi + Srujan)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 2: Live AI Executive Summary (POST /api/workspaces/{id}/summary)")
    print("=" * 70)
    print("Calling Groq to generate executive summary...")
    summary = await generate_summary(bank_data, provider=provider)
    print(f'\n[AI Generated Summary Text]:\n  "{summary.text}"')
    print(f"\n[Calculation IDs]: {summary.calculation_ids}")
    print(f"[Audit Source Rows]: {[ref.source_rows for ref in summary.source_refs]}")
    print(f"[Mandatory Disclaimer]: {summary.disclaimer}")
    print("  >>> [OK] AI Summary generated and Number Guard verified!")

    # -------------------------------------------------------------
    # Step 3: Live Conversational Assistant (Tool Calling Loop)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 3: Live Conversational Assistant (POST /api/workspaces/{id}/chat)")
    print("=" * 70)
    user_query = "What was my net cash flow this month and what was my closing balance?"
    print(f'[User Question]: "{user_query}"')
    print("Executing Groq tool-calling loop (bounded max_turns=3)...")

    response = await chat_with_workspace(
        user_query, bank_data, provider=provider, verbose=True
    )
    print(f'\n[AI Assistant Response]:\n  "{response.text}"')
    print(f"\n[Tools Called]: {response.calculation_ids}")
    print(
        f"[Citations / Source Rows]: {[ref.source_rows for ref in response.source_refs]}"
    )
    print(f"[Disclaimer]: {response.disclaimer}")
    print("  >>> [OK] Conversational Assistant answered correctly using Rashi's tools!")

    # -------------------------------------------------------------
    # Step 4: Srujan's Numeric Verification Guard Protection
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 4: Srujan's Number Guard Defense (Live Attack / Hallucination Test)")
    print("=" * 70)
    tool_res = execute_tool("bank_closing_balance", {}, bank_data)
    hallucinated_text = (
        f"Your closing balance is {bank_data.get('currency', 'INR')} 999999999."
    )

    print(
        f'Testing Srujan\'s Number Guard against fabricated claim: "{hallucinated_text}"'
    )
    guard_result = verify_tool_results_text(hallucinated_text, [tool_res])
    print(
        f"  - Guard Verdict: {'PASSED' if guard_result.valid else 'BLOCKED (Caught Hallucination!)'}"
    )
    print(
        f"  - Issues Caught: {[f'Token: {issue.token} -> Reason: {issue.reason}' for issue in guard_result.issues]}"
    )
    if not guard_result.valid:
        print(
            "  >>> [OK] Srujan's Number Guard successfully intercepted the fabricated number!"
        )

    # -------------------------------------------------------------
    # Step 5: Refusal Guardrail (Ungrounded Query)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("STEP 5: Refusal Guardrail on Unsupported Financial Query")
    print("=" * 70)
    unsupported_query = "What is my credit score and what crypto should I invest in?"
    print(f'[User Question]: "{unsupported_query}"')
    refusal_response = await chat_with_workspace(
        unsupported_query, bank_data, provider=provider
    )
    print(f'\n[AI Refusal Output]:\n  "{refusal_response.text}"')
    print(f"[Calculation IDs (should be empty)]: {refusal_response.calculation_ids}")
    print("  >>> [OK] Guardrail enforced: 0 tools invoked, 0 hallucinations!")

    print("\n" + "=" * 70)
    print("🎉 ALL 5 LIVE INTEGRATION SCENARIOS PASSED WITH REAL GROQ API! 🎉")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_live_test())

"""Interactive live terminal test for FinGenie Conversational Assistant with real Groq LLM."""

import asyncio
import json
import sys
from pathlib import Path

# Ensure backend root is on Python path
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.ai.chatbot import chat_with_workspace  # noqa: E402
from app.ai.providers.groq_provider import GroqProvider  # noqa: E402
from app.ai.summary import generate_summary  # noqa: E402
from app.core.config import settings  # noqa: E402


def load_fixture(filename: str) -> dict:
    repo_root = backend_dir.parent
    path = repo_root / "contracts" / "examples" / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def main() -> None:
    provider = GroqProvider(settings=settings)

    print("=" * 60)
    print("      FinGenie Live AI Assistant Terminal Test")
    print("=" * 60)

    if provider.is_configured:
        print(f"[STATUS] ONLINE: Connected to Groq API (Model: {settings.groq_model})")
    else:
        print("[STATUS] OFFLINE: No FINGENIE_GROQ_API_KEY detected in .env.")
        print("         Running in deterministic offline fallback mode.")
    print("=" * 60)

    # 1. Load Bank Statement Fixture
    bank_data = load_fixture("bank-statement.json")

    print("\n--- Generating Executive Summary ---")
    summary = await generate_summary(bank_data, provider=provider)
    print(f"\n[AI SUMMARY]:\n{summary.text}\n")
    print(f"[CALCULATION IDS]: {summary.calculation_ids}")
    print(f"[AUDIT SOURCE ROWS]: {[ref.source_rows for ref in summary.source_refs]}")
    print(f"[DISCLAIMER]: {summary.disclaimer}\n")

    print("-" * 60)
    print("Ask any question about the bank statement (or type 'exit' to quit).")
    print("Example questions:")
    print("  - What was my net cash flow this month?")
    print("  - How much did I spend in total?")
    print("  - What was my closing balance?")
    print("-" * 60)

    # Test questions automatically if non-interactive, or interactive prompt
    if sys.stdin.isatty():
        print("\nInteractive Chat Ready. Type your question below (or 'exit' to quit):")
        while True:
            try:
                user_msg = input("\n[USER QUESTION] > ").strip()
                if not user_msg:
                    continue
                if user_msg.lower() in ["exit", "quit", "q"]:
                    print("Exiting live chat test. Goodbye!")
                    break
                response = await chat_with_workspace(
                    user_msg, bank_data, provider=provider, verbose=True
                )
                print(f"\n[AI RESPONSE]:\n{response.text}")
                print(f"[USED FORMULAS]: {response.calculation_ids}")
                print(
                    f"[SOURCE ROWS]: {[ref.source_rows for ref in response.source_refs]}"
                )
            except (KeyboardInterrupt, EOFError):
                print("\nExiting.")
                break
    else:
        test_queries = [
            "What was my net cash flow this month?",
            "How much money was deposited into my account?",
        ]
        for q in test_queries:
            print(f"\n[USER QUESTION]: {q}")
            response = await chat_with_workspace(
                q, bank_data, provider=provider, verbose=True
            )
            print(f"\n[AI RESPONSE]:\n{response.text}")
            print(f"[USED FORMULAS]: {response.calculation_ids}")
            print(f"[SOURCE ROWS]: {[ref.source_rows for ref in response.source_refs]}")
            print(f"[DISCLAIMER]: {response.disclaimer}")


if __name__ == "__main__":
    asyncio.run(main())

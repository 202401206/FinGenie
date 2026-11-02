"""Numeric verification and bounded retry loop using Srujan's Number Guard."""

from collections.abc import Sequence
from typing import Any

from app.ai.number_guard import verify_tool_results_text
from app.ai.providers.groq_provider import GroqProvider
from app.ai.tools import ToolResult


class AIValidationError(Exception):
    """Raised when generated AI text fails numeric verification against tool outputs."""

    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        self.message = message
        self.issues = issues or []
        super().__init__(message)


async def verify_and_retry_text(
    initial_text: str,
    tool_results: Sequence[ToolResult],
    messages: list[dict[str, Any]],
    llm: GroqProvider,
    max_retries: int = 2,
) -> str:
    """Verifies generated text against tool results with bounded corrective retries.

    If the text contains unverified numbers, re-prompts the model up to max_retries
    times with the exact issue details. If verification still fails, raises AIValidationError.
    """
    current_text = initial_text
    conversation = list(messages)

    for attempt in range(max_retries + 1):
        check = verify_tool_results_text(current_text, tool_results)
        if check.valid:
            return current_text

        if attempt == max_retries:
            issue_summary = "; ".join(f"'{i.token}' ({i.reason})" for i in check.issues)
            raise AIValidationError(
                f"Generated financial response failed numeric verification: {issue_summary}",
                issues=[f"{i.token}: {i.reason}" for i in check.issues],
            )

        issue_details = "; ".join(f"'{i.token}' ({i.reason})" for i in check.issues)
        corrective_prompt = (
            f"SECURITY REJECTION: Your previous response contained unverified numbers or disallowed formatting: "
            f"{issue_details}.\n"
            f"Rewrite your response strictly adhering to these rules:\n"
            f"1. Use ONLY the exact numbers and currency returned by the executed tools.\n"
            f"2. Do not invent, guess, or extrapolate any numbers.\n"
            f"3. Do not include calendar years or dates with numbers (use 'this statement period').\n"
            f"4. Do not use numbered lists (1., 2.); use bullet dashes (-) if needed.\n"
            f"5. Do not use number words (e.g. write 5,000, not 'five thousand')."
        )
        conversation.append({"role": "assistant", "content": current_text})
        conversation.append({"role": "user", "content": corrective_prompt})

        retry_response = await llm.generate(messages=conversation, temperature=0.0)
        current_text = retry_response.content or ""

    return current_text

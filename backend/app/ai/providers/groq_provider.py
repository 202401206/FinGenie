"""Groq LLM provider adapter using Groq's OpenAI-compatible completions API."""

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class GroqError(Exception):
    """Base exception for Groq provider errors."""


class GroqConfigurationError(GroqError):
    """Raised when Groq API key is missing or blank."""


class GroqAPIError(GroqError):
    """Raised when Groq API request fails or returns an error status code."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Groq API error ({status_code}): {message}")


@dataclass
class ToolCall:
    """Represents a tool execution requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class GroqResponse:
    """Standardized response from the Groq provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""


class GroqProvider:
    """Client for Groq LLM API with native tool calling support."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def is_configured(self) -> bool:
        """Check if Groq API key is available."""
        if not self._settings.groq_api_key:
            return False
        return bool(self._settings.groq_api_key.get_secret_value().strip())

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        timeout: float = 30.0,
    ) -> GroqResponse:
        """Send a completion request to Groq with optional tools."""
        if not self.is_configured:
            raise GroqConfigurationError(
                "Groq API key is not configured. Set FINGENIE_GROQ_API_KEY in .env."
            )

        api_key = self._settings.groq_api_key.get_secret_value()  # type: ignore[union-attr]
        url = f"{self._settings.groq_base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self._settings.groq_model,
            "messages": messages,
            # Financial applications use near-zero temperature for deterministic facts
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Use injected client (for tests) or create an ephemeral async client
        if self._client is not None:
            return await self._execute_request(self._client, url, headers, payload)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._execute_request(client, url, headers, payload)

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> GroqResponse:
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise GroqAPIError(
                status_code=503,
                message=f"Network error contacting Groq API: {exc}",
            ) from exc

        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                if "error" in error_json and "message" in error_json["error"]:
                    error_detail = error_json["error"]["message"]
            except Exception:
                pass
            raise GroqAPIError(
                status_code=response.status_code,
                message=error_detail,
            )

        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")
            model = data.get("model", "")

            tool_calls: list[ToolCall] = []
            if "tool_calls" in message and message["tool_calls"]:
                for raw_call in message["tool_calls"]:
                    func = raw_call.get("function", {})
                    raw_args = func.get("arguments", "{}")
                    try:
                        parsed_args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )
                    except json.JSONDecodeError:
                        parsed_args = {}

                    tool_calls.append(
                        ToolCall(
                            id=raw_call.get("id", ""),
                            name=func.get("name", ""),
                            arguments=parsed_args,
                        )
                    )

            return GroqResponse(
                content=message.get("content"),
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                model=model,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise GroqAPIError(
                status_code=502,
                message=f"Malformed response format from Groq: {exc}",
            ) from exc

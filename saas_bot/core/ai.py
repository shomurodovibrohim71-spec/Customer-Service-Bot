"""Claude API wrapper, shared across tenants."""
from __future__ import annotations

import logging
from typing import Any

import anthropic

from config.settings import (
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
)

logger = logging.getLogger(__name__)


class AIClient:
    """Thin async wrapper around the Anthropic SDK.

    A single client is reused across all tenants; tenant differentiation happens
    via the system prompt and conversation history passed in per request.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model or ANTHROPIC_MODEL
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY is empty; AI replies will fail")
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def reply(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        max_tokens: int = AI_MAX_TOKENS,
        temperature: float = AI_TEMPERATURE,
    ) -> str:
        """Send a single user turn to Claude and return the assistant text.

        Raises anthropic.APIError on failure; callers should catch and surface a
        friendly fallback to end users.
        """
        messages: list[dict[str, Any]] = list(history) + [
            {"role": "user", "content": user_message}
        ]
        response = await self._client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip() or "..."

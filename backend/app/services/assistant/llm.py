"""Pluggable LLM providers for the SQL Learning Assistant.

The provider is chosen by the ASSISTANT_PROVIDER env var and API keys live only in server-side
environment variables — the frontend never sees them. Add a provider by implementing `LLMProvider`
and registering it in PROVIDERS.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger("assistant.llm")


class AssistantUnavailable(Exception):
    """The AI layer cannot answer (not configured, rate limited, provider error). Message is user-facing Thai."""


@dataclass
class LLMResult:
    text: str
    data: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    meta: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    def available(self) -> bool: ...

    def complete(self, system: str, messages: list[dict], *, json_schema: dict | None = None,
                 effort: str = "low", max_tokens: int = 4000) -> LLMResult: ...


class NullProvider:
    """Used when no AI provider is configured — the rule-based assistant keeps working."""
    name = "none"
    model = ""

    def available(self) -> bool:
        return False

    def complete(self, system, messages, *, json_schema=None, effort="low", max_tokens=4000) -> LLMResult:
        raise AssistantUnavailable("ยังไม่ได้ตั้งค่า AI provider บนเซิร์ฟเวอร์ — ใช้งานผู้ช่วยแบบวิเคราะห์อัตโนมัติ (rules) ได้ตามปกติ")


class AnthropicProvider:
    """Claude via the official `anthropic` SDK."""
    name = "anthropic"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("ASSISTANT_MODEL", "claude-opus-5-5")
        self._client = None

    def available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(timeout=90.0, max_retries=2)
        return self._client

    def complete(self, system: str, messages: list[dict], *, json_schema: dict | None = None,
                 effort: str = "low", max_tokens: int = 4000) -> LLMResult:
        import anthropic
        output_config: dict[str, Any] = {"effort": effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        try:
            resp = self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                output_config=output_config,
                # on a safety-classifier decline, the API re-runs the request on Anthropic's recommended
                # fallback model inside the same call instead of returning a refusal
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise AssistantUnavailable("AI ถูกใช้งานหนักชั่วคราว กรุณาลองใหม่ในอีกสักครู่") from e
        except anthropic.AuthenticationError as e:
            log.error("anthropic authentication failed — check ANTHROPIC_API_KEY")
            raise AssistantUnavailable("ตั้งค่า AI provider บนเซิร์ฟเวอร์ไม่ถูกต้อง (แจ้งผู้ดูแลระบบ)") from e
        except anthropic.APIStatusError as e:
            log.error("anthropic API error %s request_id=%s", e.status_code, getattr(e, "request_id", None))
            raise AssistantUnavailable("AI ขัดข้องชั่วคราว กรุณาลองใหม่") from e
        except anthropic.APIConnectionError as e:
            raise AssistantUnavailable("เชื่อมต่อ AI provider ไม่ได้ กรุณาลองใหม่") from e

        if resp.stop_reason == "refusal":
            raise AssistantUnavailable("AI ไม่สามารถตอบคำขอนี้ได้ ลองถามใหม่ให้เกี่ยวกับ SQL โดยตรง")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        data = None
        if json_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise AssistantUnavailable("AI ตอบกลับในรูปแบบที่ไม่ถูกต้อง กรุณาลองใหม่") from e
        if resp.stop_reason == "max_tokens" and json_schema is None:
            text += "\n\n_(คำตอบถูกตัดเพราะยาวเกินกำหนด)_"
        return LLMResult(text=text, data=data, input_tokens=resp.usage.input_tokens or 0,
                         output_tokens=resp.usage.output_tokens or 0, meta={"model": resp.model})


PROVIDERS: dict[str, type] = {"anthropic": AnthropicProvider, "none": NullProvider}
_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """ASSISTANT_PROVIDER = anthropic | none | auto (default: anthropic if its credentials are set)."""
    global _provider
    if _provider is None:
        choice = os.getenv("ASSISTANT_PROVIDER", "auto").lower()
        if choice == "auto":
            choice = "anthropic" if AnthropicProvider().available() else "none"
        cls = PROVIDERS.get(choice, NullProvider)
        _provider = cls()
        log.info("assistant provider: %s %s", _provider.name, getattr(_provider, "model", ""))
    return _provider


def set_provider(p: LLMProvider | None) -> None:
    """Override (tests, admin hot-swap)."""
    global _provider
    _provider = p

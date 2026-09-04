import logging
import json
import re
import urllib.error
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from config import settings
from models import DebugSession
from services.diagnosis_service import DiagnosisContext, build_context, build_master_prompt

logger = logging.getLogger("raze.ai_router")


def format_provider_error(error: Exception) -> str:
    """Return a short provider-safe error description for backend logs."""
    error_type = type(error).__name__
    if isinstance(error, urllib.error.HTTPError):
        body = ""
        try:
            body = error.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        message = ""
        try:
            payload = json.loads(body)
            detail = payload.get("error", payload)
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("detail") or detail.get("code") or ""
            elif isinstance(detail, str):
                message = detail
        except (TypeError, ValueError, json.JSONDecodeError):
            message = body
        message = re.sub(r"bearer\s+[^\s,;]+", "Bearer [redacted]", message, flags=re.IGNORECASE)
        message = re.sub(r"(api[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1[redacted]", message, flags=re.IGNORECASE)
        message = re.sub(r"\s+", " ", message).strip()[:240]
        return f"HTTP {error.code} - {message or 'no response details'} ({error_type})"
    return f"{error_type}: {str(error).strip()[:240] or 'no details'}"


@dataclass
class ProviderResult:
    success: bool
    provider: str
    data: Optional[dict] = None
    error: Optional[str] = None


class AIProvider:
    name = "provider"

    def is_configured(self) -> bool:
        raise NotImplementedError

    async def generate(self, prompt: str) -> ProviderResult:
        raise NotImplementedError


async def route(session: DebugSession, task: str, schema: str) -> ProviderResult:
    context = build_context(session)
    prompt = build_master_prompt(context, f"{task}\nJSON schema: {schema}")
    from services.gemini_service import GeminiProvider
    from services.openrouter_service import OpenRouterProvider
    from services.groq_service import GroqProvider

    providers: list[AIProvider] = [GeminiProvider(), OpenRouterProvider(), GroqProvider()]
    logger.info(
        "[AI Router] Configuration: Gemini key=%s model=%s; OpenRouter key=%s model=%s; Groq key=%s model=%s",
        bool(settings.GEMINI_API_KEY), settings.GEMINI_MODEL,
        bool(settings.OPENROUTER_API_KEY), settings.OPENROUTER_MODEL or "(unset)",
        bool(settings.GROQ_API_KEY), settings.GROQ_MODEL or "(unset)",
    )
    for provider in providers:
        if not provider.is_configured():
            logger.info("[AI Router] %s skipped: no API key", provider.name)
            continue
        logger.info("[AI Router] Trying %s", provider.name)
        try:
            result = await provider.generate(prompt)
        except Exception as error:
            result = ProviderResult(False, provider.name, error=format_provider_error(error))
            logger.warning("[AI Router] %s failed: %s", provider.name, result.error)
        if result.success:
            logger.info("[AI Router] %s succeeded", provider.name)
            session.diagnosis_provider = result.provider
            return result
        logger.warning("[AI Router] %s failed: %s", provider.name, result.error or "invalid response")

    logger.warning("[AI Router] Using deterministic fallback")
    session.diagnosis_provider = "local"
    return ProviderResult(False, "local", error="all_providers_failed")

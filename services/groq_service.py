import asyncio
import json
import urllib.error
import urllib.request

from config import settings
from services.ai_router import AIProvider, ProviderResult, format_provider_error


class GroqProvider(AIProvider):
    name = "groq"

    def is_configured(self) -> bool:
        return bool(settings.GROQ_API_KEY and settings.GROQ_MODEL)

    async def generate(self, prompt: str) -> ProviderResult:
        return await asyncio.wait_for(asyncio.to_thread(self._request, prompt), settings.AI_REQUEST_TIMEOUT)

    def _request(self, prompt: str) -> ProviderResult:
        payload = json.dumps({"model": settings.GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}}).encode()
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "RAZE-Debug-Mentor/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.AI_REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode())
            content = data["choices"][0]["message"]["content"]
            return ProviderResult(True, self.name, json.loads(content))
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as error:
            return ProviderResult(False, self.name, error=format_provider_error(error))

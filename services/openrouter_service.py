import asyncio
import json
import urllib.error
import urllib.request

from config import settings
from services.ai_router import AIProvider, ProviderResult, format_provider_error


class OpenRouterProvider(AIProvider):
    name = "openrouter"

    def is_configured(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_MODEL)

    async def generate(self, prompt: str) -> ProviderResult:
        return await asyncio.wait_for(asyncio.to_thread(self._request, prompt), settings.AI_REQUEST_TIMEOUT)

    def _request(self, prompt: str) -> ProviderResult:
        payload = json.dumps({"model": settings.OPENROUTER_MODEL, "messages": [{"role": "user", "content": prompt}]}).encode()
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "HTTP-Referer": "https://github.com/bilal-dev-0x/RAZE-Debug-Mentor",
                "X-Title": "RAZE Debug Mentor",
                "User-Agent": "RAZE-Debug-Mentor/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.AI_REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode())
            content = data["choices"][0]["message"]["content"]
            return ProviderResult(True, self.name, json.loads(_strip_fences(content)))
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as error:
            return ProviderResult(False, self.name, error=format_provider_error(error))


def _strip_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    return content.strip()

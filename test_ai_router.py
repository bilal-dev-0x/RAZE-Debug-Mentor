import unittest
from unittest.mock import patch

from models import DebugSession
from services.ai_router import ProviderResult, route


class FakeProvider:
    calls = []
    responses = {}

    def __init__(self, name):
        self.name = name

    def is_configured(self):
        return self.responses.get(self.name, {}).get("configured", True)

    async def generate(self, prompt):
        self.calls.append((self.name, prompt))
        response = self.responses.get(self.name, {})
        if response.get("success"):
            return ProviderResult(True, self.name, {"value": self.name})
        return ProviderResult(False, self.name, error="simulated_failure")


class AIRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeProvider.calls = []
        FakeProvider.responses = {
            "gemini": {"configured": True, "success": False},
            "openrouter": {"configured": True, "success": False},
            "groq": {"configured": True, "success": False},
        }

    def patches(self):
        return patch.multiple(
            "services.gemini_service", GeminiProvider=lambda: FakeProvider("gemini"),
        ), patch.multiple(
            "services.openrouter_service", OpenRouterProvider=lambda: FakeProvider("openrouter"),
        ), patch.multiple(
            "services.groq_service", GroqProvider=lambda: FakeProvider("groq"),
        )

    async def test_gemini_success_stops_chain(self):
        FakeProvider.responses["gemini"]["success"] = True
        with self.patches()[0], self.patches()[1], self.patches()[2]:
            result = await route(DebugSession(submitted_code="print(1)"), "observe", "{}")
        self.assertTrue(result.success)
        self.assertEqual([name for name, _ in FakeProvider.calls], ["gemini"])

    async def test_failover_is_sequential_and_preserves_prompt(self):
        FakeProvider.responses["groq"]["success"] = True
        with self.patches()[0], self.patches()[1], self.patches()[2]:
            result = await route(DebugSession(submitted_code="x = 1\nprint(x)"), "observe", "{}")
        self.assertTrue(result.success)
        self.assertEqual([name for name, _ in FakeProvider.calls], ["gemini", "openrouter", "groq"])
        self.assertEqual(FakeProvider.calls[0][1], FakeProvider.calls[1][1])
        self.assertEqual(FakeProvider.calls[1][1], FakeProvider.calls[2][1])

    async def test_missing_provider_is_skipped(self):
        FakeProvider.responses["gemini"]["configured"] = False
        FakeProvider.responses["openrouter"]["success"] = True
        with self.patches()[0], self.patches()[1], self.patches()[2]:
            result = await route(DebugSession(submitted_code="print(1)"), "observe", "{}")
        self.assertTrue(result.success)
        self.assertEqual([name for name, _ in FakeProvider.calls], ["openrouter"])

    async def test_all_providers_use_local_fallback_marker(self):
        with self.patches()[0], self.patches()[1], self.patches()[2]:
            result = await route(DebugSession(submitted_code="print(1)"), "observe", "{}")
        self.assertFalse(result.success)
        self.assertEqual(result.provider, "local")
        self.assertEqual([name for name, _ in FakeProvider.calls], ["gemini", "openrouter", "groq"])


if __name__ == "__main__":
    unittest.main()

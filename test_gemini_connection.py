import asyncio
import sys
from config import settings
from services.gemini_service import GeminiService
from models import DebugSession, StartSessionRequest
from services.debug_engine import debug_engine

async def verify():
    print("==================================================")
    print("      RAZE CONFIGURATION & GEMINI TEST SUITE      ")
    print("==================================================")

    # 1. Check dotenv path and existence
    print(f"1. .env Path: {settings.DOTENV_PATH}")
    print(f"2. .env Exists: {settings.DOTENV_EXISTS}")

    # 2. Check API key status (WITHOUT printing the key)
    print(f"3. Key Present: {bool(settings.GEMINI_API_KEY)}")
    print(f"4. Key Source: {settings.KEY_SOURCE}")
    print(f"5. Configured Model: {settings.GEMINI_MODEL}")

    assert settings.DOTENV_EXISTS is True, ".env must exist"
    assert bool(settings.GEMINI_API_KEY) is True, "GEMINI_API_KEY must be loaded"

    # 3. Test direct Gemini API call
    print("\n--- Testing Live Gemini API Call ---")
    session = DebugSession(
        language="python",
        submitted_code="def double(n):\n    return n + 2\nprint(double(5))",
        expected_result="10",
        actual_result="7"
    )

    try:
        obs, q1, fallback = await GeminiService.generate_observation_and_q1(session)
        print(f"API Call Succeeded!")
        print(f"Used Deterministic Fallback: {fallback}")
        print(f"AI Observation:\n{obs}\n")
        print(f"AI Question 1:\n{q1}\n")

        assert fallback is False, "Expected live Gemini response, but got fallback!"
        print(">>> LIVE GEMINI CONNECTION TEST PASSED! <<<")

    except Exception as e:
        print(f"FAILED: {e}")
        classified = GeminiService.classify_error(e)
        print(f"Classified Error Category: {classified['category']}")
        print(f"Classified Error Message: {classified['message']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify())


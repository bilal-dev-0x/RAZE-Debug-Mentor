import asyncio
import json
import re
from typing import Any, Dict, Tuple

from config import settings
from models import DebugSession, FinalSolution
from services.ai_router import AIProvider, ProviderResult, format_provider_error, route
from services.deterministic import DeterministicAnalyzer


class GeminiProvider(AIProvider):
    name = "gemini"

    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    async def generate(self, prompt: str) -> ProviderResult:
        try:
            text = await asyncio.wait_for(asyncio.to_thread(self._request, prompt), settings.AI_REQUEST_TIMEOUT)
            return ProviderResult(True, self.name, _clean_json(text))
        except Exception as error:
            return ProviderResult(False, self.name, error=format_provider_error(error))

    def _request(self, prompt: str) -> str:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
        if not response or not response.text:
            raise ValueError("Gemini returned an empty response")
        return response.text


class GeminiService:
    """Compatibility facade retained for existing callers and tests."""

    @classmethod
    def is_configured(cls) -> bool:
        return GeminiProvider().is_configured()

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {"key_present": cls.is_configured(), "key_source": settings.KEY_SOURCE, "dotenv_path": str(settings.DOTENV_PATH), "dotenv_exists": settings.DOTENV_EXISTS, "model": settings.GEMINI_MODEL}

    @classmethod
    def classify_error(cls, error: Exception) -> Dict[str, str]:
        text = str(error).lower()
        if "429" in text or "quota" in text or "resource_exhausted" in text:
            return {"category": "rate_limit", "message": "Gemini rate limit"}
        if "timeout" in text:
            return {"category": "timeout", "message": "Gemini request timed out"}
        return {"category": "provider_error", "message": "Gemini request failed"}

    @classmethod
    async def generate_observation_and_q1(cls, session: DebugSession) -> Tuple[str, str, bool]:
        result = await route(session, "Stage 1: provide a concise grounded observation and one diagnostic question.", '{"observation": "...", "question_1": "..."}')
        if result.success and result.data and result.data.get("observation") and result.data.get("question_1"):
            session.ai_unavailable_notice = None
            return result.data["observation"].strip(), result.data["question_1"].strip(), False
        deterministic = DeterministicAnalyzer.analyze_session(session)
        if deterministic:
            return deterministic[0], deterministic[1], True
        session.ai_unavailable_notice = "AI synthesis temporarily unavailable; using local diagnostic analysis."
        return session.ai_unavailable_notice, "What line or behavior do you suspect first from the execution evidence?", True

    @classmethod
    async def generate_q2(cls, session: DebugSession) -> Tuple[str, bool]:
        result = await route(session, "Stage 2: ask exactly one final diagnostic question based on the observation and user's first answer.", '{"question_2": "..."}')
        if result.success and result.data and result.data.get("question_2"):
            return result.data["question_2"].strip(), False
        deterministic = DeterministicAnalyzer.analyze_session(session)
        return (deterministic[2], True) if deterministic else ("What does the execution evidence imply about the next step in this program?", True)

    @classmethod
    async def generate_final_solution(cls, session: DebugSession) -> Tuple[FinalSolution, bool]:
        result = await route(session, "Stage 3: stop asking questions and provide the complete diagnosis and corrected version of the user's program.", '{"what_i_found": "...", "whats_happening": "...", "root_cause": "...", "corrected_code": "...", "why_fix_works": "...", "lesson": "..."}')
        if result.success and result.data:
            try:
                solution = FinalSolution(**result.data)
                if _is_relevant(session, solution):
                    return solution, False
            except (TypeError, ValueError):
                pass
        deterministic = DeterministicAnalyzer.analyze_session(session)
        if deterministic:
            return deterministic[3], True
        session.ai_unavailable_notice = "AI synthesis temporarily unavailable; using local diagnostic analysis."
        return FinalSolution(
            what_i_found="No deterministic root-cause pattern was identified from the submitted evidence.",
            whats_happening="The execution output remains available in the console for inspection.",
            root_cause="Unresolved from available evidence",
            corrected_code=session.submitted_code,
            why_fix_works="No safe code change can be proposed without stronger evidence.",
            lesson="Use the traceback and expected-versus-actual output to narrow the failing behavior.",
        ), True


def _clean_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text.strip())
    return json.loads((match.group(1) if match else text).strip())


def _is_relevant(session: DebugSession, solution: FinalSolution) -> bool:
    identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", session.submitted_code))
    return not identifiers or any(identifier in solution.corrected_code for identifier in identifiers)

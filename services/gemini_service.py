import asyncio
import json
import logging
import re
from typing import Optional, Tuple, Dict, Any
from config import settings
from models import DebugSession, FinalSolution
from prompts.system_prompts import (
    build_observation_and_q1_prompt,
    build_q2_prompt,
    build_final_solution_prompt
)
from services.deterministic import DeterministicAnalyzer

logger = logging.getLogger("raze.gemini")

# Known working fallback models if user-specified model returns 404
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.8-flash"]

class GeminiService:
    """
    Handles communication with Google Gemini via google-genai SDK.
    Features:
    - Precise error classification (key missing, key invalid, API/model, network, SDK).
    - Model auto-fallback for deprecated/misspelled model names.
    - Grounding & sanity validation.
    - Safe deterministic analysis fallback on the user's actual code.
    """

    @classmethod
    def is_configured(cls) -> bool:
        return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "key_present": cls.is_configured(),
            "key_source": settings.KEY_SOURCE,
            "dotenv_path": str(settings.DOTENV_PATH),
            "dotenv_exists": settings.DOTENV_EXISTS,
            "model": settings.GEMINI_MODEL
        }

    @classmethod
    def _get_client(cls):
        from google import genai
        return genai.Client(api_key=settings.GEMINI_API_KEY)

    @classmethod
    def classify_error(cls, e: Exception) -> Dict[str, str]:
        """
        Classifies errors into explicit categories according to engineering specification.
        Never converts all errors into 'no GEMINI_API_KEY set'.
        """
        if not cls.is_configured():
            return {
                "category": "key_missing",
                "message": "No GEMINI_API_KEY found in environment or .env file."
            }

        err_str = str(e)
        err_type = type(e).__name__

        if isinstance(e, (ImportError, ModuleNotFoundError)):
            return {
                "category": "sdk_import_error",
                "message": f"Google GenAI SDK import failure: {err_str}"
            }

        # Check for invalid key / permission denied
        if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str or "403" in err_str:
            return {
                "category": "key_invalid",
                "message": "GEMINI_API_KEY is present but was rejected by Google AI Studio (Invalid Key / 403 Forbidden)."
            }

        # Check for model not found / unsupported
        if "404" in err_str or "NOT_FOUND" in err_str or "not supported for generateContent" in err_str:
            return {
                "category": "api_model_error",
                "message": f"Gemini Model Error: Specified model '{settings.GEMINI_MODEL}' is not available or not supported (404 Not Found)."
            }

        # Check for quota exceeded
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            return {
                "category": "api_quota_error",
                "message": "Gemini API Quota Exceeded (429 Resource Exhausted). Please check your rate limits."
            }

        # Check for network error
        if "ConnectError" in err_type or "Timeout" in err_type or "connection" in err_str.lower():
            return {
                "category": "network_error",
                "message": f"Network error connecting to Google Gemini API: {err_type}."
            }

        return {
            "category": "api_error",
            "message": f"Gemini API error ({err_type}): {err_str[:160]}"
        }

    @classmethod
    def _clean_json_response(cls, text: str) -> dict:
        text = text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            text = fence_match.group(1).strip()
        return json.loads(text)

    @classmethod
    async def _execute_generate(cls, prompt: str) -> str:
        """
        Executes generate_content with automatic fallback if the configured model returns 404.
        """
        client = cls._get_client()
        models_to_try = [settings.GEMINI_MODEL]
        for fb in FALLBACK_MODELS:
            if fb not in models_to_try:
                models_to_try.append(fb)

        last_error = None
        for model in models_to_try:
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=prompt
                )
                if response and response.text:
                    if model != settings.GEMINI_MODEL:
                        logger.info(f"Model '{settings.GEMINI_MODEL}' was unavailable; succeeded with fallback '{model}'.")
                    return response.text
            except Exception as e:
                last_error = e
                classified = cls.classify_error(e)
                # Only retry alternate models on 404 model errors
                if classified["category"] == "api_model_error":
                    logger.warning(f"Model '{model}' failed (404/Not Found). Trying next fallback model...")
                    continue
                # For auth, network, or other errors, do not loop through models
                raise e

        raise last_error

    @classmethod
    async def generate_observation_and_q1(cls, session: DebugSession) -> Tuple[str, str, bool]:
        """
        Returns (observation, question_1, used_deterministic_fallback)
        """
        if not cls.is_configured():
            session.ai_unavailable_notice = "No GEMINI_API_KEY configured."
            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                obs, q1, _, _ = deterministic
                return obs, q1, True
            return (
                "AI diagnosis is currently offline (no GEMINI_API_KEY configured). "
                "Execution results are displayed in the console. Add your key to .env for in-depth mentoring.",
                "Based on the execution output above, what line or behavior do you suspect first?",
                True
            )

        prompt = build_observation_and_q1_prompt(session)
        try:
            raw_text = await cls._execute_generate(prompt)
            data = cls._clean_json_response(raw_text)
            obs = data.get("observation", "").strip()
            q1 = data.get("question_1", "").strip()

            if not obs or not q1:
                raise ValueError("Incomplete observation/question returned by AI.")

            session.ai_unavailable_notice = None
            return obs, q1, False

        except Exception as e:
            classified = cls.classify_error(e)
            session.ai_unavailable_notice = classified["message"]
            logger.warning(f"Gemini call failed ({classified['category']}): {classified['message']}. Attempting deterministic fallback.")

            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                obs, q1, _, _ = deterministic
                return obs, q1, True

            return (
                f"Notice: {classified['message']} "
                f"Raw execution results for your code are available in the console.",
                "Review the runtime output in the console. What do you observe about the line or variable referenced?",
                True
            )

    @classmethod
    async def generate_q2(cls, session: DebugSession) -> Tuple[str, bool]:
        """
        Returns (question_2, used_deterministic_fallback)
        """
        if not cls.is_configured():
            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                _, _, q2, _ = deterministic
                return q2, True
            return "Looking closer at your logic, what should happen immediately before that point?", True

        prompt = build_q2_prompt(session)
        try:
            raw_text = await cls._execute_generate(prompt)
            data = cls._clean_json_response(raw_text)
            q2 = data.get("question_2", "").strip()
            if not q2:
                raise ValueError("Incomplete Q2 generated by AI.")
            return q2, False

        except Exception as e:
            classified = cls.classify_error(e)
            session.ai_unavailable_notice = classified["message"]
            logger.warning(f"Gemini Q2 call failed ({classified['category']}): {classified['message']}.")

            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                _, _, q2, _ = deterministic
                return q2, True
            return "Given your observation, how does that step affect the next line in your program?", True

    @classmethod
    async def generate_final_solution(cls, session: DebugSession) -> Tuple[FinalSolution, bool]:
        """
        Generates the 5-part final response + lesson.
        Validates relevance against the user's submitted code.
        """
        if not cls.is_configured():
            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                _, _, _, solution = deterministic
                return solution, True

            return FinalSolution(
                what_i_found="Automated AI diagnosis is offline because no valid GEMINI_API_KEY is configured.",
                whats_happening="Your code ran in Python and the results are displayed in the execution console.",
                root_cause="Diagnostic AI Offline (No API Key)",
                corrected_code=session.submitted_code,
                why_fix_works="Add GEMINI_API_KEY to your .env file to enable deep AI corrections.",
                lesson="Always check execution tracebacks when automated mentoring is offline."
            ), True

        prompt = build_final_solution_prompt(session)
        try:
            raw_text = await cls._execute_generate(prompt)
            data = cls._clean_json_response(raw_text)

            solution = FinalSolution(
                what_i_found=data.get("what_i_found", "").strip(),
                whats_happening=data.get("whats_happening", "").strip(),
                root_cause=data.get("root_cause", "").strip(),
                corrected_code=data.get("corrected_code", "").strip(),
                why_fix_works=data.get("why_fix_works", "").strip(),
                lesson=data.get("lesson", "").strip()
            )

            # Sanity validation
            is_valid = cls._validate_solution_relevance(session, solution)
            if not is_valid:
                logger.warning("AI output failed relevance validation (code mismatch). Falling back to deterministic analyzer.")
                deterministic = DeterministicAnalyzer.analyze_session(session)
                if deterministic:
                    _, _, _, det_solution = deterministic
                    return det_solution, True

            return solution, False

        except Exception as e:
            classified = cls.classify_error(e)
            session.ai_unavailable_notice = classified["message"]
            logger.warning(f"Gemini final solution failed ({classified['category']}): {classified['message']}.")

            deterministic = DeterministicAnalyzer.analyze_session(session)
            if deterministic:
                _, _, _, det_solution = deterministic
                return det_solution, True

            return FinalSolution(
                what_i_found=f"AI synthesis unavailable: {classified['message']}",
                whats_happening="The runtime execution details are available in your console to assist in pinpointing the error.",
                root_cause=f"AI Unavailable ({classified['category']})",
                corrected_code=session.submitted_code,
                why_fix_works="Review the line indicated in the execution traceback to resolve the issue.",
                lesson="Tracebacks always pinpoint the exact line where execution failed."
            ), True

    @classmethod
    def _validate_solution_relevance(cls, session: DebugSession, solution: FinalSolution) -> bool:
        user_code = session.submitted_code
        user_identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", user_code))
        keywords = {
            "def", "class", "return", "for", "while", "if", "elif", "else",
            "import", "from", "as", "in", "is", "not", "and", "or", "print",
            "None", "True", "False", "try", "except", "finally", "with"
        }
        user_identifiers = user_identifiers - keywords

        if not user_identifiers:
            return True

        corrected = solution.corrected_code
        found_count = sum(1 for ident in user_identifiers if ident in corrected)

        if found_count == 0 and len(user_identifiers) >= 2:
            logger.warning(f"Validation failed: None of {user_identifiers} found in corrected code.")
            return False

        return True

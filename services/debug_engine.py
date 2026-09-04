import time
import uuid
import logging
from typing import Dict, Optional
from config import settings
from models import (
    DebugSession,
    SessionStage,
    StartSessionRequest,
    ExecutionResult
)
from services.code_runner import CodeRunner
from services.gemini_service import GeminiService

logger = logging.getLogger("raze.engine")

class DebugEngine:
    """
    State machine managing session isolation and progression.
    Enforces the STOP RULE (stops asking questions after Q2).
    """

    def __init__(self):
        # In-memory dictionary of sessions keyed strictly by session_id (UUID)
        self._sessions: Dict[str, DebugSession] = {}

    def _cleanup_expired_sessions(self):
        """Removes sessions older than SESSION_TTL_MINUTES."""
        now = time.time()
        ttl_seconds = settings.SESSION_TTL_MINUTES * 60
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.updated_at > ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

    async def start_session(self, req: StartSessionRequest) -> DebugSession:
        self._cleanup_expired_sessions()

        session_id = str(uuid.uuid4())
        session = DebugSession(
            session_id=session_id,
            language=req.language.lower().strip(),
            submitted_code=req.code,
            error_message=req.error_message.strip() if req.error_message else None,
            expected_result=req.expected_result.strip() if req.expected_result else None,
            actual_result=req.actual_result.strip() if req.actual_result else None,
            stage=SessionStage.INITIAL
        )

        # 1. Execute code if runnable
        exec_res = await CodeRunner.run_code(session.language, session.submitted_code)
        session.execution_result = exec_res

        # 2. Generate Initial Observation + Question 1
        obs, q1, used_fallback = await GeminiService.generate_observation_and_q1(session)
        session.observation = obs
        session.question_1 = q1
        session.used_deterministic_fallback = used_fallback
        session.stage = SessionStage.WAITING_ANSWER_1
        session.updated_at = time.time()

        # Save in isolated session registry
        self._sessions[session_id] = session
        return session

    async def submit_answer(self, session_id: str, answer: str) -> DebugSession:
        self._cleanup_expired_sessions()
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Session '{session_id}' not found or has expired.")

        answer = answer.strip()

        if session.stage == SessionStage.WAITING_ANSWER_1:
            session.answer_1 = answer
            # Generate Q2
            q2, used_fallback = await GeminiService.generate_q2(session)
            session.question_2 = q2
            if used_fallback:
                session.used_deterministic_fallback = True
            session.stage = SessionStage.WAITING_ANSWER_2
            session.updated_at = time.time()
            return session

        elif session.stage == SessionStage.WAITING_ANSWER_2:
            session.answer_2 = answer
            # STOP RULE: Move immediately to final solution! No Q3!
            solution, used_fallback = await GeminiService.generate_final_solution(session)
            session.final_solution = solution
            if used_fallback:
                session.used_deterministic_fallback = True
            session.stage = SessionStage.COMPLETED
            session.updated_at = time.time()
            return session

        elif session.stage == SessionStage.COMPLETED:
            # Already completed; return current state
            return session

        else:
            raise ValueError(f"Session is in unexpected stage: {session.stage}")

    def get_session(self, session_id: str) -> Optional[DebugSession]:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

# Global engine instance managing per-session state
debug_engine = DebugEngine()


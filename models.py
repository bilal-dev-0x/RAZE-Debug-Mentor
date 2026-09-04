from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import time
import uuid

class SessionStage(str, Enum):
    INITIAL = "initial"
    WAITING_ANSWER_1 = "waiting_answer_1"
    WAITING_ANSWER_2 = "waiting_answer_2"
    COMPLETED = "completed"

class ExecutionResult(BaseModel):
    executed: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = 0
    timed_out: bool = False
    error_type: Optional[str] = None
    error_line: Optional[int] = None
    error_details: Optional[str] = None
    runner_message: Optional[str] = None

class FinalSolution(BaseModel):
    what_i_found: str = Field(description="01 - What I Found: clear root cause referring directly to user code")
    whats_happening: str = Field(description="02 - What's Happening: runtime step-by-step mechanism")
    root_cause: str = Field(description="03 - Root Cause: actual programming concept name")
    corrected_code: str = Field(description="04 - Corrected Code: modified version of user's actual program")
    why_fix_works: str = Field(description="05 - Why This Fix Works: explanation of why fix resolves the bug")
    lesson: str = Field(description="★ Lesson: concise debugging/programming principle")

class DebugSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "python"
    submitted_code: str
    error_message: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    execution_result: Optional[ExecutionResult] = None
    stage: SessionStage = SessionStage.INITIAL
    observation: Optional[str] = None
    question_1: Optional[str] = None
    answer_1: Optional[str] = None
    question_2: Optional[str] = None
    answer_2: Optional[str] = None
    final_solution: Optional[FinalSolution] = None
    used_deterministic_fallback: bool = False
    ai_unavailable_notice: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

# API Request Models
class StartSessionRequest(BaseModel):
    language: str = "python"
    code: str
    error_message: Optional[str] = ""
    expected_result: Optional[str] = ""
    actual_result: Optional[str] = ""

class SubmitAnswerRequest(BaseModel):
    session_id: str
    answer: str

class RunCodeRequest(BaseModel):
    language: str = "python"
    code: str

# API Response Models
class SessionResponse(BaseModel):
    session_id: str
    language: str
    stage: SessionStage
    submitted_code: str
    execution_result: Optional[ExecutionResult] = None
    observation: Optional[str] = None
    question_1: Optional[str] = None
    answer_1: Optional[str] = None
    question_2: Optional[str] = None
    answer_2: Optional[str] = None
    final_solution: Optional[FinalSolution] = None
    is_completed: bool = False
    used_deterministic_fallback: bool = False
    ai_unavailable_notice: Optional[str] = None


"""Pydantic data models for RAZE Debugging Mentor API."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RunCodeRequest(BaseModel):
    code: str = Field(..., description="Python source code to execute")
    language: str = Field("python", description="Language to execute (only python is supported)")


class RunCodeResponse(BaseModel):
    output: str = Field("", description="Standard output from code execution")
    error: Optional[str] = Field(None, description="Standard error or exception traceback")
    exit_code: int = Field(0, description="Process exit code")
    execution_time_ms: int = Field(0, description="Execution duration in milliseconds")
    timed_out: bool = Field(False, description="Whether execution exceeded timeout")


class StartDebugRequest(BaseModel):
    code: str = Field(..., description="The user's Python source code containing the bug")
    error_message: Optional[str] = Field(None, description="The traceback or exception message if any")
    expected_result: str = Field(..., description="What the user expected to happen")
    actual_result: Optional[str] = Field(None, description="What actually happened, if different from error")


class StartDebugResponse(BaseModel):
    session_id: str
    stage: str = "observation"
    stage_number: int = 1
    stage_title: str = "Observation & Question 1"
    message: str
    observation: Optional[str] = None
    question: Optional[str] = None
    suspicious_lines: List[int] = Field(default_factory=list)
    real_execution: Optional[Dict[str, Any]] = None
    discrepancy_note: Optional[str] = None


class RespondDebugRequest(BaseModel):
    session_id: str
    user_message: str
    stage: str


class StuckDebugRequest(BaseModel):
    session_id: str
    stage: Optional[str] = None


class StageInfo(BaseModel):
    id: str
    number: int
    title: str
    description: str


class DebugStagesResponse(BaseModel):
    stages: List[StageInfo]


class DebugResponse(BaseModel):
    session_id: str
    stage: str
    stage_number: int
    stage_title: str
    message: Optional[str] = None
    suspicious_lines: List[int] = Field(default_factory=list)
    evaluation: Optional[str] = None
    question: Optional[str] = None
    what_i_found: Optional[str] = None
    whats_happening: Optional[str] = None
    hidden_problem: Optional[str] = None
    why_output_changed: Optional[str] = None
    discrepancy_noticed: Optional[str] = None
    corrected_code: Optional[str] = None
    before_snippet: Optional[str] = None
    after_snippet: Optional[str] = None
    why_fix_works: Optional[str] = None
    lesson: Optional[str] = None
    live_execution: Optional[Dict[str, Any]] = None
    is_complete: bool = False
    can_skip_to_solution: bool = False
    hint: Optional[str] = None


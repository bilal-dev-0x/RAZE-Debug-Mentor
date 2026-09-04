import json
from dataclasses import dataclass
from typing import Any

from models import DebugSession


@dataclass(frozen=True)
class DiagnosisContext:
    language: str
    problem: str
    code: str
    error_message: str
    expected_result: str
    actual_result: str
    execution_output: str
    current_stage: str
    mentor_observation: str
    question_1: str
    user_answer_1: str
    question_2: str
    user_answer_2: str
    root_cause_signals: tuple[str, ...]


def build_context(session: DebugSession) -> DiagnosisContext:
    execution = session.execution_result
    output = ""
    if execution:
        output = (
            f"Exit code: {execution.exit_code}\n"
            f"Stdout:\n{execution.stdout or '(none)'}\n"
            f"Stderr:\n{execution.stderr or '(none)'}\n"
            f"Error type: {execution.error_type or 'None'}\n"
            f"Error line: {execution.error_line or 'None'}"
        )

    signals = []
    code = session.submitted_code.lower()
    if ".copy()" in code or "copy(" in code:
        signals.append("copy operation on user data")
    if "tasks=[]" in code or "tasks = []" in code:
        signals.append("mutable default candidate")
    if execution and execution.error_type:
        signals.append(execution.error_type)
    if session.expected_result and session.actual_result and session.expected_result != session.actual_result:
        signals.append("expected and actual output differ")

    return DiagnosisContext(
        language=session.language,
        problem=session.error_message or session.actual_result or "Diagnose the submitted program",
        code=session.submitted_code,
        error_message=session.error_message or "",
        expected_result=session.expected_result or "",
        actual_result=session.actual_result or "",
        execution_output=output,
        current_stage=session.stage.value,
        mentor_observation=session.observation or "",
        question_1=session.question_1 or "",
        user_answer_1=session.answer_1 or "",
        question_2=session.question_2 or "",
        user_answer_2=session.answer_2 or "",
        root_cause_signals=tuple(signals),
    )


def build_master_prompt(context: DiagnosisContext, task: str) -> str:
    payload = {
        "language": context.language,
        "problem": context.problem,
        "code": context.code,
        "error_message": context.error_message,
        "expected_result": context.expected_result,
        "actual_result": context.actual_result,
        "execution_output": context.execution_output,
        "current_stage": context.current_stage,
        "mentor_observation": context.mentor_observation,
        "question_1": context.question_1,
        "user_answer_1": context.user_answer_1,
        "question_2": context.question_2,
        "user_answer_2": context.user_answer_2,
        "root_cause_signals": list(context.root_cause_signals),
    }
    return f"""You are RAZE, a calm evidence-driven debugging mentor. Analyze only the user's current code and execution evidence. Never invent a root cause, never use generic tutorial code, and never treat an AI/provider failure as the user's bug. Preserve the user's actual program in any fix. After question 2, provide the solution rather than another question.

TASK: {task}

SHARED DIAGNOSIS CONTEXT (use every relevant field):
{json.dumps(payload, indent=2)}

Return ONLY valid JSON matching the requested schema."""


def answer_quality(session: DebugSession, answer: str) -> str:
    text = answer.lower().strip()
    if len(text.split()) < 2 or text in {"yes", "i think yes", "maybe", "i don't know", "not sure"}:
        return "vague"
    code = session.submitted_code.lower()
    if ".copy()" in code and ("deepcopy" in text or "shared" in text or "outer" in text):
        return "correct"
    if ("tasks=[]" in code or "tasks = []" in code) and ("created once" in text or "default" in text or "none" in text):
        return "correct"
    return "uncertain"

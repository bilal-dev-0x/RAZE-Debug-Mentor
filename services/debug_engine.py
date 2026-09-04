"""Debug Engine for RAZE's 3-stage senior-developer debugging flow.

Stage sequence (matches STAGE_NAMES in prompts/system_prompts.py and the
StartDebugResponse/DebugResponse contracts in models.py):

  1. observation   -> Observation + Diagnostic Question 1
  2. diagnose_2    -> Evaluation of Answer 1 + Diagnostic Question 2
  3. resolution    -> Complete diagnosis, corrected code, live verification

Each session is stored server-side in an in-memory dict keyed by a unique
session_id. Every read/write goes through that key — nothing here is shared
across sessions, and no session's code, answers, or generated content ever
leaks into another session's state or prompts.
"""

import re
import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple

from prompts.system_prompts import (
    build_observation_prompt,
    build_question_2_prompt,
    build_resolution_prompt,
    build_stuck_hint_prompt,
)
from services.gemini_service import GeminiService
from services.code_runner import run_python_safe, ExecutionResult

logger = logging.getLogger("raze.engine")

STAGE_TITLES = {
    "observation": "Observation & Question 1",
    "diagnose_2": "Diagnostic Question 2",
    "resolution": "Complete Analysis & Solution",
}

_SUSPICIOUS_MARKERS = (
    ".remove(", ".pop(", "del ", ".append(", ".copy(",
    "for ", "while ", "==", "/ ", "//",
)


def detect_suspicious_lines(code: str) -> List[int]:
    """Heuristic pass to seed suspicious-line highlighting before/without AI refinement."""
    lines = code.split("\n")
    suspicious = [
        idx + 1
        for idx, line in enumerate(lines)
        if any(marker in line.strip() for marker in _SUSPICIOUS_MARKERS)
    ]
    return suspicious if suspicious else [min(2, len(lines)) or 1]


# ---------------------------------------------------------------------- #
# Offline (no-Gemini) fallback content generation.
#
# IMPORTANT: this whole section only runs when self.gemini.is_configured()
# is False, or a Gemini call returns nothing usable. It must NEVER assert a
# diagnosis the submitted code doesn't actually support — every fallback
# string below is either (a) grounded in a pattern that was actually found
# via regex in THIS session's code, or (b) an honest, code-agnostic prompt
# that references the user's own expected/actual results instead of
# guessing a specific (possibly wrong) mechanism.
# ---------------------------------------------------------------------- #

def _detect_pattern(code: str) -> Tuple[str, Dict[str, str]]:
    """Best-effort match against a couple of known bug shapes, using only
    what's actually present in the submitted code. Returns (pattern_key, captures).
    pattern_key is 'generic' when nothing matches — never guessed."""

    # Shape 1: mutating a collection while iterating directly over it
    # e.g.  for x in numbers: ... numbers.remove(x)
    for_match = re.search(r'for\s+\w+\s+in\s+([A-Za-z_]\w*)\s*:', code)
    if for_match:
        iterable = for_match.group(1)
        body = code[for_match.end():]
        mutate_pat = (
            rf'\b{re.escape(iterable)}\s*\.\s*(?:remove|pop)\s*\(|'
            rf'del\s+{re.escape(iterable)}\s*\['
        )
        if re.search(mutate_pat, body):
            return "list_mutation_iter", {"iterable": iterable}

    # Shape 2: shallow copy (.copy()) followed by mutation of a nested
    # element reached through the copied name.
    copy_match = re.search(r'([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\s*\.\s*copy\s*\(\s*\)', code)
    if copy_match:
        copy_name, original_name = copy_match.group(1), copy_match.group(2)
        nested_mutate_pat = (
            rf'\b{re.escape(copy_name)}\s*\[[^\]\n]+\]'
            rf'(?:\s*\[[^\]\n]+\])?\s*'
            rf'(?:\.\s*(?:append|remove|pop|update|extend|insert)\s*\(|[\+\-\*/]?=(?!=))'
        )
        if re.search(nested_mutate_pat, code):
            return "shallow_copy_nested", {"copy_name": copy_name, "original_name": original_name}

    return "generic", {}


def _fallback_observation(
    code: str, expected_result: str, real_summary: str, suspicious_lines: List[int]
) -> Tuple[str, str]:
    """Returns (observation_text, question_1_text), grounded in THIS code."""
    pattern, cap = _detect_pattern(code)

    if pattern == "list_mutation_iter":
        it = cap["iterable"]
        observation = (
            f"Look at how you're looping over `{it}`: the loop calls a mutating method "
            f"(`.remove()`/`.pop()`/`del`) directly on `{it}` while still iterating over it. "
            f"Expected: {expected_result}. Actual (real execution): {real_summary}."
        )
        question = (
            f"When you remove an item from `{it}` mid-loop, every item after it shifts one "
            f"position to the left — but the loop's position counter still moves forward by one. "
            f"What do you think happens to the item that just shifted into the position the "
            f"counter is about to skip past?"
        )
        return observation, question

    if pattern == "shallow_copy_nested":
        copy_name, original_name = cap["copy_name"], cap["original_name"]
        observation = (
            f"`{copy_name} = {original_name}.copy()` performs a SHALLOW copy: it duplicates the "
            f"outer dictionary/list itself, but every value stored *inside* it (nested lists, "
            f"nested dicts) is not duplicated — `{copy_name}` and `{original_name}` end up pointing "
            f"at the exact same inner objects. Expected: {expected_result}. "
            f"Actual (real execution): {real_summary}."
        )
        question = (
            f"If `{copy_name}` and `{original_name}` share references to the same nested list/dict "
            f"objects, what happens to `{original_name}` when you mutate something inside "
            f"`{copy_name}` (e.g. `.append()` on a nested list, rather than reassigning `{copy_name}` itself)?"
        )
        return observation, question

    # Generic, honest fallback — makes no claim about a mechanism it hasn't verified.
    line_ref = f"line {suspicious_lines[0]}" if suspicious_lines else "the code above"
    observation = (
        f"Here's what actually happens when this code runs: {real_summary}. "
        f"You expected: {expected_result}. I want to work through the gap with you rather than "
        f"guess at a mechanism I can't yet confirm — {line_ref} looks like a reasonable place to start."
    )
    question = (
        f"Walk through {line_ref} by hand: what value do you expect each variable involved to "
        f"hold right before that line executes, and what do you think it actually holds immediately after?"
    )
    return observation, question


def _fallback_eval_and_q2(code: str, answer_1: str) -> Tuple[str, str]:
    """Returns (evaluation_of_answer_1, question_2), grounded in THIS code.
    Never claims the user's answer was right or wrong — we have no AI here to judge that."""
    pattern, cap = _detect_pattern(code)

    ack = "Thanks for walking through that — here's one more angle on it."

    if pattern == "list_mutation_iter":
        it = cap["iterable"]
        question = (
            f"One more: if you built a brand-new list instead of modifying `{it}` in place "
            f"(for example with a list comprehension), would the loop's position counter still "
            f"have anything to desynchronize against?"
        )
        return ack, question

    if pattern == "shallow_copy_nested":
        copy_name = cap["copy_name"]
        question = (
            f"One more: if `{copy_name}` needs to be a fully independent structure — changes to "
            f"it should never touch the original at any nesting depth — what would you need to do "
            f"differently than calling `.copy()`?"
        )
        return ack, question

    question = (
        "One more: based on what you traced, which specific line do you think is where the "
        "actual behavior first diverges from what you expected?"
    )
    return ack, question


def _real_output_summary(execution: ExecutionResult) -> str:
    if execution.get("error"):
        # The useful part of a Python traceback is the LAST non-empty line
        # (the actual "ExceptionType: message"), not the first ("Traceback
        # (most recent call last):").
        lines = [ln for ln in execution["error"].splitlines() if ln.strip()]
        summary_line = lines[-1] if lines else execution["error"]
        return f"Raised error: {summary_line}"
    return execution.get("output") or "No output printed"


def _detect_discrepancy(user_reported_actual: Optional[str], real_summary: str) -> Optional[str]:
    reported = (user_reported_actual or "").strip()
    if not reported or reported.lower() == "none":
        return None
    if reported.lower() in real_summary.lower() or real_summary.lower() in reported.lower():
        return None
    return (
        f'There is an inconsistency between your reported Actual Result ("{reported}") '
        f'and what this code actually produces when executed ("{real_summary}").'
    )


def _is_skip_signal(user_text: str) -> bool:
    """True when the user's message is really an 'I'm stuck / show me the
    solution' request rather than an actual diagnostic answer. This is what
    the frontend's 'skip to solution' button sends through /api/debug/respond,
    and it must never be evaluated as if it were a correct (or incorrect)
    answer to the diagnostic question."""
    t = (user_text or "").strip().lower()
    if not t:
        return False
    return any(sig in t for sig in ("stuck", "skip", "show me the solution", "full explanation"))


def _fallback_resolution(session: "DebugSession", user_text: str) -> Dict[str, Any]:
    """Builds the complete resolution payload without Gemini, grounded in
    whatever pattern actually matches THIS session's code."""
    pattern, cap = _detect_pattern(session.code)
    skipped = _is_skip_signal(user_text)

    evaluation = (
        "No problem — let's skip straight to the full walkthrough."
        if skipped
        else "Thanks for working through that with me — here's the complete picture."
    )

    if pattern == "list_mutation_iter":
        it = cap["iterable"]
        what_i_found = (
            f"The bug is that `{it}` is mutated (via `.remove()`/`.pop()`/`del`) while a `for` "
            f"loop is actively iterating over it. Removing an item shifts every later item one "
            f"position to the left, but the loop's internal position counter keeps advancing by "
            f"one regardless — so the item that just slid into the current position gets skipped."
        )
        whats_happening = (
            f"1. The loop starts at position 0 of `{it}`.\n"
            f"2. When a match is found, the mutating call removes it, shifting every later item left by one.\n"
            f"3. The loop's counter still advances to the next position, skipping over the item "
            f"that just moved into the position that was already visited."
        )
        hidden_problem = (
            f"`{it}` is a mutable sequence. Removing an element resizes it immediately and shifts "
            f"every later index down by one, but Python's iterator has no way to know that — it "
            f"just keeps counting positions forward."
        )
        corrected_code = (
            f"{it} = [item for item in {it} if <your-keep-condition-here>]\n"
            f"# Build a NEW list instead of mutating {it} while iterating over it directly."
        )
        before_snippet = f"for x in {it}:\n    if <condition>:\n        {it}.remove(x)  # mutates while iterating"
        after_snippet = f"{it} = [x for x in {it} if not <condition>]  # builds a new list instead"
        why_fix_works = (
            f"A comprehension builds an entirely new list; the original `{it}` is never mutated "
            f"mid-traversal, so there's no shifting index to desynchronize against."
        )
        lesson = "Never mutate a collection's size while directly iterating over it — build a new one instead."

    elif pattern == "shallow_copy_nested":
        copy_name, original_name = cap["copy_name"], cap["original_name"]
        what_i_found = (
            f"`{copy_name} = {original_name}.copy()` is a SHALLOW copy. It creates a new outer "
            f"container, but every nested value inside it (lists, dicts) is still the SAME object "
            f"shared with `{original_name}` — nothing nested was actually duplicated."
        )
        whats_happening = (
            f"1. `{copy_name} = {original_name}.copy()` creates a new outer dict/list.\n"
            f"2. Each value inside it is copied BY REFERENCE, not by value — nested lists/dicts "
            f"still point at the exact same objects as in `{original_name}`.\n"
            f"3. Mutating a nested value through `{copy_name}` (e.g. `.append()`) changes that "
            f"shared object, so `{original_name}` appears to change too."
        )
        hidden_problem = (
            "`.copy()` (and `dict(x)` / `list(x)`) only ever copies one level deep. Anything "
            "mutable nested inside — lists, dicts, custom objects — is shared by reference "
            "between the original and the copy."
        )
        corrected_code = (
            "from copy import deepcopy\n\n"
            f"{copy_name} = deepcopy({original_name})\n"
            f"# deepcopy recursively duplicates every nested object, so {copy_name} and "
            f"{original_name} no longer share any nested references."
        )
        before_snippet = f"{copy_name} = {original_name}.copy()  # shallow — nested objects are shared"
        after_snippet = f"from copy import deepcopy\n{copy_name} = deepcopy({original_name})  # fully independent"
        why_fix_works = (
            "deepcopy() recursively duplicates every nested mutable object instead of just the "
            "outer container, so the two structures share no references at any depth."
        )
        lesson = "`.copy()` is shallow. Use `copy.deepcopy()` when nested mutable data must be fully independent."

    else:
        # No known pattern matched — be honest rather than inventing a fix.
        what_i_found = (
            "I wasn't able to confidently pin down a single root cause without a configured AI "
            "model — the pattern in this code doesn't match one of the cases I can verify "
            "heuristically. Rather than guess, here's what I can tell you for certain from "
            "actually running your code."
        )
        whats_happening = (
            f"Real execution result: {_real_output_summary(session.real_execution)}\n"
            f"Expected: {session.expected_result}"
        )
        hidden_problem = (
            "To get a precise, code-specific explanation and fix here, configure GEMINI_API_KEY "
            "so RAZE can reason about this specific program instead of falling back to heuristics."
        )
        corrected_code = (
            "# No AI model is configured, so I can't safely generate a corrected version of your\n"
            "# code without risking giving you a fix for the wrong problem.\n"
            "# Your original submitted code is unchanged below — the suspicious lines are marked.\n\n"
            + session.code
        )
        before_snippet = "# See suspicious line markers in the code viewer above."
        after_snippet = "# Configure GEMINI_API_KEY for a targeted, code-specific fix."
        why_fix_works = "N/A — no fix was generated without a configured AI model."
        lesson = "Trace the flagged lines by hand: print each variable right before and after they run."

    return {
        "evaluation": evaluation,
        "what_i_found": what_i_found,
        "whats_happening": whats_happening,
        "hidden_problem": hidden_problem,
        "why_output_changed": (
            f"{_real_output_summary(session.real_execution)} — compared to what you expected "
            f"({session.expected_result})."
        ),
        "discrepancy_noticed": session.discrepancy_note,
        "corrected_code": corrected_code,
        "before_snippet": before_snippet,
        "after_snippet": after_snippet,
        "why_fix_works": why_fix_works,
        "lesson": lesson,
    }


class DebugSession:
    """Holds all state for exactly one debugging conversation. Never shared."""

    def __init__(
        self,
        session_id: str,
        code: str,
        error_message: Optional[str],
        expected_result: str,
        actual_result: Optional[str],
        suspicious_lines: List[int],
        real_execution: ExecutionResult,
        observation: str,
        question_1: str,
        discrepancy_note: Optional[str],
    ):
        self.session_id = session_id
        self.code = code
        self.error_message = error_message
        self.expected_result = expected_result
        self.actual_result = actual_result
        self.current_stage = "observation"
        self.stage_number = 1
        self.suspicious_lines = suspicious_lines
        self.real_execution = real_execution
        self.observation = observation
        self.question_1 = question_1
        self.answer_1: Optional[str] = None
        self.eval_1: Optional[str] = None
        self.question_2: Optional[str] = None
        self.answer_2: Optional[str] = None
        self.eval_2: Optional[str] = None
        self.discrepancy_note = discrepancy_note
        self.created_at = time.time()
        self.last_activity = time.time()


class DebugEngine:
    def __init__(self, gemini_service: GeminiService):
        self.gemini = gemini_service
        self.sessions: Dict[str, DebugSession] = {}

    def _get_session(self, session_id: str) -> DebugSession:
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError("Session expired or not found. Please start a new session.")
        session.last_activity = time.time()
        return session

    # ------------------------------------------------------------------ #
    # Stage 1: start_session
    # ------------------------------------------------------------------ #
    def start_session(
        self,
        code: str,
        error_message: Optional[str],
        expected_result: str,
        actual_result: Optional[str],
    ) -> Dict[str, Any]:
        session_id = f"session-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        suspicious_lines = detect_suspicious_lines(code)

        # Ground-truth execution — never trust the user's self-reported output.
        real_execution = run_python_safe(code)
        real_summary = _real_output_summary(real_execution)
        discrepancy_note = _detect_discrepancy(actual_result, real_summary)

        observation = ""
        question_1 = ""

        if self.gemini.is_configured():
            prompt = build_observation_prompt(
                code=code,
                error_message=error_message,
                expected_result=expected_result,
                actual_result=actual_result,
                real_execution_summary=real_summary,
            )
            parsed = self.gemini.generate_json_response(prompt)
            observation = parsed.get("observation") or ""
            question_1 = parsed.get("question") or ""
            ai_lines = parsed.get("suspicious_lines")
            if isinstance(ai_lines, list) and ai_lines:
                suspicious_lines = ai_lines

        if not observation or not question_1:
            fb_observation, fb_question = _fallback_observation(
                code, expected_result, real_summary, suspicious_lines
            )
            observation = observation or fb_observation
            question_1 = question_1 or fb_question

        if discrepancy_note and "inconsistency" not in observation and "discrepancy" not in observation:
            observation = f"{discrepancy_note}\n\n{observation}"

        session = DebugSession(
            session_id=session_id,
            code=code,
            error_message=error_message,
            expected_result=expected_result,
            actual_result=actual_result,
            suspicious_lines=suspicious_lines,
            real_execution=real_execution,
            observation=observation,
            question_1=question_1,
            discrepancy_note=discrepancy_note,
        )
        self.sessions[session_id] = session

        return {
            "session_id": session_id,
            "stage": "observation",
            "stage_number": 1,
            "stage_title": STAGE_TITLES["observation"],
            "observation": observation,
            "question": question_1,
            "message": f"{observation}\n\n{question_1}",
            "suspicious_lines": suspicious_lines,
            "real_execution": real_execution,
            "discrepancy_note": discrepancy_note,
        }

    # ------------------------------------------------------------------ #
    # Stage 1 -> 2, and 2 -> 3
    # ------------------------------------------------------------------ #
    def process_response(self, session_id: str, user_message: str, stage: str) -> Dict[str, Any]:
        session = self._get_session(session_id)
        user_text = (user_message or "").strip()

        # "Jump directly to complete solution" must actually do that, from
        # any stage — not be evaluated as a diagnostic answer.
        if _is_skip_signal(user_text):
            if session.answer_1 is None:
                session.answer_1 = user_text
            return self._advance_to_resolution(session, user_text)

        if session.stage_number == 1 or stage == "observation":
            return self._advance_to_diagnose_2(session, user_text)

        return self._advance_to_resolution(session, user_text)

    def _advance_to_diagnose_2(self, session: DebugSession, user_text: str) -> Dict[str, Any]:
        session.answer_1 = user_text

        eval_1 = ""
        question_2 = ""

        if self.gemini.is_configured():
            prompt = build_question_2_prompt(
                code=session.code,
                expected_result=session.expected_result,
                question_1=session.question_1,
                answer_1=user_text,
            )
            parsed = self.gemini.generate_json_response(prompt)
            eval_1 = parsed.get("evaluation") or ""
            question_2 = parsed.get("question") or ""

        if not eval_1 or not question_2:
            fb_eval, fb_question_2 = _fallback_eval_and_q2(session.code, user_text)
            eval_1 = eval_1 or fb_eval
            question_2 = question_2 or fb_question_2

        session.stage_number = 2
        session.current_stage = "diagnose_2"
        session.eval_1 = eval_1
        session.question_2 = question_2

        return {
            "session_id": session.session_id,
            "stage": "diagnose_2",
            "stage_number": 2,
            "stage_title": STAGE_TITLES["diagnose_2"],
            "evaluation": eval_1,
            "question": question_2,
            "message": f"{eval_1}\n\n{question_2}",
            "suspicious_lines": session.suspicious_lines,
        }

    def _advance_to_resolution(self, session: DebugSession, user_text: str) -> Dict[str, Any]:
        session.answer_2 = user_text
        real_summary = _real_output_summary(session.real_execution)
        skipped = _is_skip_signal(user_text)

        result: Dict[str, Any] = {}
        if self.gemini.is_configured():
            prompt = build_resolution_prompt(
                code=session.code,
                expected_result=session.expected_result,
                actual_result=session.actual_result,
                real_execution_summary=real_summary,
                question_1=session.question_1,
                answer_1=session.answer_1 or "",
                question_2=session.question_2 or "",
                answer_2=user_text,
                user_requested_help=skipped,
            )
            result = self.gemini.generate_json_response(prompt)

        corrected_code = result.get("corrected_code") or ""

        if not corrected_code:
            # Offline fallback — used only when Gemini is unavailable or fails
            # to return a usable solution for THIS session's code. Grounded in
            # whatever pattern actually matches this code; never asserts a
            # mechanism (e.g. loop/index mutation) that isn't really present.
            result = _fallback_resolution(session, user_text)
            corrected_code = result["corrected_code"]

        live_execution = run_python_safe(corrected_code)

        session.stage_number = 3
        session.current_stage = "resolution"
        session.eval_2 = result.get("evaluation") or ""

        return {
            "session_id": session.session_id,
            "stage": "resolution",
            "stage_number": 3,
            "stage_title": STAGE_TITLES["resolution"],
            "is_complete": True,
            "evaluation": result.get("evaluation") or "",
            "what_i_found": result.get("what_i_found") or "",
            "whats_happening": result.get("whats_happening") or "",
            "hidden_problem": result.get("hidden_problem") or "",
            "why_output_changed": result.get("why_output_changed") or "",
            "discrepancy_noticed": result.get("discrepancy_noticed") or session.discrepancy_note or None,
            "corrected_code": corrected_code,
            "before_snippet": result.get("before_snippet") or "",
            "after_snippet": result.get("after_snippet") or "",
            "why_fix_works": result.get("why_fix_works") or "",
            "lesson": result.get("lesson") or "",
            "live_execution": live_execution,
        }

    # ------------------------------------------------------------------ #
    # "I'm Stuck" — hints grounded in THIS session, not a canned example
    # ------------------------------------------------------------------ #
    def process_stuck(self, session_id: str, stage: Optional[str]) -> Dict[str, Any]:
        session = self._get_session(session_id)
        is_stage_1 = session.stage_number == 1 or stage == "observation"
        active_stage = "observation" if is_stage_1 else "diagnose_2"
        active_question = session.question_1 if is_stage_1 else (session.question_2 or session.question_1)

        hint = ""
        message = ""

        if self.gemini.is_configured():
            prompt = build_stuck_hint_prompt(
                code=session.code,
                expected_result=session.expected_result,
                actual_result=session.actual_result,
                stage=active_stage,
                question=active_question or "",
            )
            parsed = self.gemini.generate_json_response(prompt)
            hint = parsed.get("hint") or ""
            message = parsed.get("message") or ""

        if not hint:
            # Fallback only — grounded in this session's own suspicious lines,
            # never a hardcoded example from a different bug.
            line_ref = (
                f"around line {session.suspicious_lines[0]}"
                if session.suspicious_lines
                else "in the section you flagged as suspicious"
            )
            hint = (
                f"Re-read what happens {line_ref} of your code, one step at a time — "
                f"trace what each variable holds right before and right after that line runs, "
                f"and compare it to what you expected ({session.expected_result})."
            )
        if not message:
            message = f"Hint: {hint}"

        return {
            "session_id": session.session_id,
            "stage": active_stage,
            "stage_number": session.stage_number,
            "stage_title": "Mentor Hint",
            "hint": hint,
            "message": message,
            "can_skip_to_solution": True,
        }
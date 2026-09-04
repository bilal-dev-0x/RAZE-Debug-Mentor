import json
from models import DebugSession

SYSTEM_PERSONA = """You are RAZE, an expert Senior Debugging Mentor.
Your role is to guide beginner and intermediate programmers through diagnosing and fixing their bugs.
You act like a calm, encouraging senior developer sitting beside the programmer.

CORE PRINCIPLES:
1. ABSOLUTE GROUNDING: Analyze ONLY the code, error, and evidence provided for the CURRENT session.
2. ZERO STALE CONTEXT: Never reuse examples, variables, or solutions from previous problems or generic tutorials.
3. PRESERVE USER CODE: When suggesting a fix, you must modify the USER'S ACTUAL CODE. Never replace it with unrelated tutorial code (e.g. if user code mentions 'students', fix 'students', never introduce 'numbers = [1, 2, 3, 4, 5]').
4. SINCERITY: If the runtime error clearly states what happened (e.g., NameError on line 5), acknowledge the clear facts calmly. Do not pretend obvious errors are mysterious.
5. NO ENDLESS QUESTIONS: Ask exactly ONE diagnostic question at a time. After Question 2, STOP asking questions and provide the full solution.
"""

def build_observation_and_q1_prompt(session: DebugSession) -> str:
    exec_info = "Not executed"
    if session.execution_result and session.execution_result.executed:
        res = session.execution_result
        exec_info = (
            f"Exit Code: {res.exit_code}\n"
            f"Stdout:\n{res.stdout or '(none)'}\n"
            f"Stderr:\n{res.stderr or '(none)'}\n"
            f"Error Type: {res.error_type or 'None'}\n"
            f"Error Line: {res.error_line or 'None'}\n"
            f"Error Details: {res.error_details or 'None'}"
        )

    user_error = session.error_message or "(None provided by user)"
    expected = session.expected_result or "(None provided)"
    actual = session.actual_result or "(None provided)"

    prompt = f"""{SYSTEM_PERSONA}

TASK: STAGE 1 — INITIAL OBSERVATION & DIAGNOSTIC QUESTION 1

CURRENT PROBLEM CONTEXT:
Programming Language: {session.language}

Submitted Code:
```{session.language}
{session.submitted_code}
```

User Reported Error:
{user_error}

User Expected Result:
{expected}

User Actual Observed Result:
{actual}

Live Execution Output:
{exec_info}

INSTRUCTIONS:
1. Provide a concise Initial Observation: what appears suspicious, where behavior diverges, or which line/mechanism is worth investigating. Acknowledge any clear runtime errors. Do not dump the final fixed code yet.
2. Formulate Diagnostic Question 1: Ask ONE focused, useful question that helps the user reason about THIS specific code and its variables.
3. Respond ONLY in valid JSON matching this exact structure:
{{
  "observation": "Your concise, grounded observation here",
  "question_1": "Your specific diagnostic question 1 here"
}}
"""
    return prompt

def build_q2_prompt(session: DebugSession) -> str:
    prompt = f"""{SYSTEM_PERSONA}

TASK: STAGE 2 — DIAGNOSTIC QUESTION 2

CURRENT PROBLEM CONTEXT:
Language: {session.language}
Code:
```{session.language}
{session.submitted_code}
```

Initial Observation:
{session.observation}

Diagnostic Question 1:
{session.question_1}

User's Answer to Question 1:
{session.answer_1}

INSTRUCTIONS:
1. Formulate Diagnostic Question 2: Ask ONE final focused question building directly on the original problem, Question 1, and the user's answer.
2. Guide them toward the root cause without switching to unrelated topics.
3. Respond ONLY in valid JSON matching this exact structure:
{{
  "question_2": "Your final diagnostic question 2 here"
}}
"""
    return prompt

def build_final_solution_prompt(session: DebugSession) -> str:
    exec_info = "Not executed"
    if session.execution_result and session.execution_result.executed:
        res = session.execution_result
        exec_info = f"Exit code: {res.exit_code}\nStdout: {res.stdout}\nStderr: {res.stderr}"

    prompt = f"""{SYSTEM_PERSONA}

TASK: STAGE 3 — FINAL DIAGNOSIS, EXPLANATION & CODE FIX

CURRENT PROBLEM CONTEXT:
Language: {session.language}

Submitted Code:
```{session.language}
{session.submitted_code}
```

Runtime / Error Evidence:
{session.error_message or session.execution_result.stderr if session.execution_result else ''}

Live Execution Details:
{exec_info}

Observation:
{session.observation}

Question 1:
{session.question_1}
User Answer 1:
{session.answer_1}

Question 2:
{session.question_2}
User Answer 2:
{session.answer_2}

CRITICAL RULES FOR RESPONSE:
- Stop asking questions now. Move directly to the full solution.
- The corrected code MUST be the corrected version of the user's submitted program. NEVER replace it with a generic tutorial snippet.
- The 5 sections must be clearly detailed, practical, and grounded.

Respond ONLY in valid JSON matching this exact structure:
{{
  "what_i_found": "01 — What I Found: clear root cause explanation referring directly to user code",
  "whats_happening": "02 — What's Happening: explain the runtime mechanism step-by-step in short, readable paragraphs",
  "root_cause": "03 — Root Cause: concise name of the actual programming concept (e.g. Variable Name Typo, Shallow Copy, Off-by-one)",
  "corrected_code": "04 — Corrected Code: the full corrected version of the user's actual program",
  "why_fix_works": "05 — Why This Fix Works: explain why this fix solves the actual bug",
  "lesson": "★ Lesson: one concise debugging or programming principle relevant to this bug"
}}
"""
    return prompt


import asyncio
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from models import StartSessionRequest, SubmitAnswerRequest
from services.debug_engine import debug_engine
from services.code_runner import CodeRunner
from services.gemini_service import GeminiService
from config import settings

async def run_tests():
    print("==========================================================")
    print("           RAZE AUTOMATED VERIFICATION SUITE              ")
    print("==========================================================\n")

    # -------------------------------------------------------------------------
    # TEST B: Simple NameError (Run this first to verify basic runtime & typo detection)
    # -------------------------------------------------------------------------
    print("--- [TEST B] Simple NameError Verification ---")
    test_b_code = (
        'name = "Bilal"\n'
        'age = 20\n\n'
        'print("Name:", name)\n'
        'print("Age:", ages)\n'
    )

    req_b = StartSessionRequest(
        language="python",
        code=test_b_code,
        error_message="",
        expected_result="Print Name: Bilal and Age: 20",
        actual_result=""
    )

    session_b = await debug_engine.start_session(req_b)
    print(f"Session B ID: {session_b.session_id}")
    print(f"Executed: {session_b.execution_result.executed}")
    print(f"Exit code: {session_b.execution_result.exit_code}")
    print(f"Error Type: {session_b.execution_result.error_type}")
    print(f"Error Line: {session_b.execution_result.error_line}")
    print(f"Observation: {session_b.observation}")
    print(f"Question 1: {session_b.question_1}")

    # Assertions for Test B Stage 1
    assert session_b.execution_result.executed is True, "Test B code was not executed."
    assert "NameError" in (session_b.execution_result.stderr or ""), "NameError was not captured in stderr."
    assert session_b.execution_result.error_type == "NameError", f"Expected NameError, got {session_b.execution_result.error_type}"
    assert "ages" in session_b.observation.lower() or "ages" in session_b.question_1.lower(), "Observation/Q1 did not mention 'ages'."
    assert "numbers" not in session_b.observation.lower(), "Contamination: 'numbers' appeared in Test B observation!"

    # Progress Test B: Answer 1 -> Q2
    session_b = await debug_engine.submit_answer(
        session_b.session_id,
        "I defined age, but typed ages on line 5 by accident."
    )
    print(f"Question 2: {session_b.question_2}")
    assert session_b.question_2 is not None, "Question 2 was not generated."

    # Progress Test B: Answer 2 -> Final Solution (STOP RULE)
    session_b = await debug_engine.submit_answer(
        session_b.session_id,
        "I should change ages to age."
    )
    sol_b = session_b.final_solution
    print("\nFinal Solution B:")
    print(f"01 What I Found: {sol_b.what_i_found}")
    print(f"03 Root Cause: {sol_b.root_cause}")
    print(f"04 Corrected Code:\n{sol_b.corrected_code}")
    print(f"[Lesson]: {sol_b.lesson}")

    assert "age" in sol_b.corrected_code, "Corrected code should contain 'age'."
    assert "ages" not in sol_b.corrected_code or "print(\"Age:\", age)" in sol_b.corrected_code, "Corrected code should fix 'ages' to 'age'."
    assert "numbers = [1, 2, 3, 4, 5]" not in sol_b.corrected_code, "Contamination: generic numbers tutorial code appeared!"
    assert "students" not in sol_b.corrected_code, "Contamination: students appeared in Test B!"
    print(">>> TEST B PASSED SUCCESSFULLY! <<<\n")

    # -------------------------------------------------------------------------
    # TEST A: Shallow Copy + Mutation Bug (students dictionary)
    # -------------------------------------------------------------------------
    print("--- [TEST A] Shallow Copy + Nested Mutation Verification ---")
    test_a_code = '''students = {
    "Ali": {"scores": [85, 92, 78, 105], "bonus": 5},
    "Sara": {"scores": [88, 91, -10, 76], "bonus": 10},
    "Hamza": {"scores": [70, 82, 95, 88], "bonus": 0}
}

processed = students.copy()

for name, data in processed.items():
    scores = data["scores"]

    for score in scores:
        if score < 0 or score > 100:
            scores.remove(score)

    data["scores"] = scores

    average = sum(scores) / len(scores)
    adjusted_average = average + data["bonus"]

    if adjusted_average >= 90:
        grade = "A"
    elif adjusted_average >= 75:
        grade = "B"
    else:
        grade = "C"

    print(
        f"{name}: average={average:.2f}, "
        f"adjusted={adjusted_average:.2f}, grade={grade}"
    )

print("\\nOriginal data:")
print(students)'''

    req_a = StartSessionRequest(
        language="python",
        code=test_a_code,
        error_message="",
        expected_result="Original data should not be changed, and invalid scores filtered.",
        actual_result="Original dictionary is mutated and some scores are skipped."
    )

    session_a = await debug_engine.start_session(req_a)
    print(f"Session A ID: {session_a.session_id}")
    print(f"Observation: {session_a.observation}")
    print(f"Question 1: {session_a.question_1}")

    # Check that it identifies shallow copy or remove/iteration mutation
    obs_and_q1_text = (session_a.observation + " " + session_a.question_1).lower()
    assert ("copy" in obs_and_q1_text or "shallow" in obs_and_q1_text or "remove" in obs_and_q1_text or "mutat" in obs_and_q1_text), \
        f"Observation/Q1 did not mention copy/mutation: {obs_and_q1_text}"
    assert "ages" not in obs_and_q1_text, "Contamination: 'ages' from Test B leaked into Test A!"

    # Progress Test A: Answer 1 -> Q2
    session_a = await debug_engine.submit_answer(
        session_a.session_id,
        "I think students.copy() is only copying the outer dictionary references."
    )
    print(f"Question 2: {session_a.question_2}")

    # Progress Test A: Answer 2 -> Final Solution (STOP RULE)
    session_a = await debug_engine.submit_answer(
        session_a.session_id,
        "Also removing from scores while looping over it shifts indices and skips items."
    )
    sol_a = session_a.final_solution
    print("\nFinal Solution A:")
    print(f"01 What I Found: {sol_a.what_i_found}")
    print(f"03 Root Cause: {sol_a.root_cause}")
    print(f"04 Corrected Code:\n{sol_a.corrected_code}")
    print(f"[Lesson]: {sol_a.lesson}")

    # Assertions for Test A Final Solution
    assert "students" in sol_a.corrected_code, "Corrected code must belong to the user's 'students' code!"
    assert "numbers = [1, 2, 3, 4, 5]" not in sol_a.corrected_code, "Contamination: generic numbers tutorial code appeared!"
    assert ("copy" in sol_a.root_cause.lower() or "shallow" in sol_a.root_cause.lower() or "mutation" in sol_a.root_cause.lower()), \
        f"Root cause did not mention shallow copy or mutation: {sol_a.root_cause}"
    print(">>> TEST A PASSED SUCCESSFULLY! <<<\n")

    # -------------------------------------------------------------------------
    # TEST C: Completely New Session (Context Isolation Verification)
    # -------------------------------------------------------------------------
    print("--- [TEST C] Completely New Session Isolation Verification ---")
    test_c_code = '''def calculate_rectangle_area(width, height):
    return width + height

print("Area 5x10:", calculate_rectangle_area(5, 10))'''

    req_c = StartSessionRequest(
        language="python",
        code=test_c_code,
        error_message="",
        expected_result="50",
        actual_result="15"
    )

    session_c = await debug_engine.start_session(req_c)
    print(f"Session C ID: {session_c.session_id}")
    assert session_c.session_id != session_a.session_id, "Session ID should be unique."
    assert session_c.session_id != session_b.session_id, "Session ID should be unique."

    c_context = (session_c.observation + " " + session_c.question_1).lower()
    print(f"Observation C: {session_c.observation}")
    print(f"Question 1 C: {session_c.question_1}")

    # Verify ZERO leakage from Test A or Test B
    assert "students" not in c_context, "Contamination: 'students' from Test A leaked into Test C!"
    assert "scores" not in c_context, "Contamination: 'scores' from Test A leaked into Test C!"
    assert "ages" not in c_context, "Contamination: 'ages' from Test B leaked into Test C!"
    assert "bilal" not in c_context, "Contamination: 'Bilal' from Test B leaked into Test C!"
    print(">>> TEST C PASSED SUCCESSFULLY (ZERO LEAKAGE)! <<<\n")

    # -------------------------------------------------------------------------
    # TEST D: API Failure & Deterministic Fallback Verification
    # -------------------------------------------------------------------------
    print("--- [TEST D] API Failure & Fallback Safety Verification ---")
    # Temporarily clear GEMINI_API_KEY to simulate service unavailability
    original_key = settings.GEMINI_API_KEY
    try:
        settings.GEMINI_API_KEY = ""
        assert GeminiService.is_configured() is False, "GeminiService should report not configured."

        # Case 1: Deterministically diagnosable bug (NameError)
        req_d1 = StartSessionRequest(
            language="python",
            code='val = 100\nprint(vals)',
            error_message="",
            expected_result="100",
            actual_result=""
        )
        session_d1 = await debug_engine.start_session(req_d1)
        assert session_d1.used_deterministic_fallback is True, "Should use deterministic fallback."
        assert "vals" in session_d1.observation or "vals" in session_d1.question_1, "Deterministic fallback did not diagnose 'vals'."
        assert "val" in session_d1.observation or "val" in session_d1.question_1, "Deterministic fallback did not find 'val'."

        # Progress to final solution under fallback
        session_d1 = await debug_engine.submit_answer(session_d1.session_id, "Typo in vals")
        session_d1 = await debug_engine.submit_answer(session_d1.session_id, "Replace vals with val")
        sol_d1 = session_d1.final_solution
        print(f"Fallback Sol D1: {sol_d1.root_cause}")
        print(f"Corrected Code D1:\n{sol_d1.corrected_code}")
        assert "print(val)" in sol_d1.corrected_code, "Corrected code should fix 'vals' to 'val' directly in user's code."
        assert "numbers = [1, 2, 3, 4, 5]" not in sol_d1.corrected_code, "Fallback must NEVER introduce generic tutorial code!"

        # Case 2: Code with no error and complex logic (cannot be diagnosed deterministically)
        req_d2 = StartSessionRequest(
            language="python",
            code='def mystery_algorithm(n):\n    return n * 2\nprint(mystery_algorithm(5))',
            error_message="",
            expected_result="15",
            actual_result="10"
        )
        session_d2 = await debug_engine.start_session(req_d2)
        print(f"Fallback Obs D2 (Honest message): {session_d2.observation}")
        assert "AI diagnosis is currently offline" in session_d2.observation or "unavailable" in session_d2.observation, \
            "Must honestly report AI is offline when deterministic diagnosis cannot safely match."
        assert "numbers = [1, 2, 3, 4, 5]" not in session_d2.observation, "Never fabricate generic tutorial code!"

        print(">>> TEST D PASSED SUCCESSFULLY (HONEST FALLBACK, ZERO GENERIC CODE)! <<<\n")

    finally:
        settings.GEMINI_API_KEY = original_key

    print("==========================================================")
    print("      ALL REQUIRED VERIFICATION TESTS COMPLETED!         ")
    print("==========================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())

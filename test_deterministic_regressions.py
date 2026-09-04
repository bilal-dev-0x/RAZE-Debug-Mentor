import unittest

from models import DebugSession
from services.deterministic import DeterministicAnalyzer
from services.diagnosis_service import answer_quality


class DeterministicRegressionTests(unittest.TestCase):
    def test_nested_shallow_copy(self):
        code = '''import copy
students = [{"scores": {"math": [80, 90]}}]
backup = students.copy()
def add_bonus(data):
    for student in data:
        student["scores"]["math"][0] += 10
add_bonus(backup)
'''
        result = DeterministicAnalyzer.analyze_session(DebugSession(submitted_code=code))
        self.assertIsNotNone(result)
        self.assertEqual(result[3].root_cause, "Shallow Copying of Nested Data Structures")
        self.assertIn("copy.deepcopy(students)", result[3].corrected_code)

    def test_mutable_default_argument(self):
        code = '''def add_task(task, tasks=[]):
    tasks.append(task)
    return tasks
'''
        result = DeterministicAnalyzer.analyze_session(DebugSession(submitted_code=code))
        self.assertIsNotNone(result)
        self.assertEqual(result[3].root_cause, "Mutable Default Argument")
        self.assertIn("tasks=None", result[3].corrected_code)

    def test_vague_answer_is_not_correct(self):
        session = DebugSession(submitted_code="backup = students.copy()")
        self.assertEqual(answer_quality(session, "i think yes"), "vague")
        self.assertEqual(answer_quality(session, "The nested values remain shared"), "correct")


if __name__ == "__main__":
    unittest.main()

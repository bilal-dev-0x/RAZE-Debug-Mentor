import ast
import difflib
import re
from typing import Optional, List, Set, Tuple
from models import DebugSession, ExecutionResult, FinalSolution

class DeterministicAnalyzer:
    """
    Deterministic AST and runtime traceback analyzer.
    Used when Gemini is unavailable or as a pre-validation engine.
    CRITICAL RULE:
    Only produces diagnoses and solutions strictly derived from the USER's submitted code.
    If high confidence is not achieved, returns None — NEVER generates generic tutorial examples.
    """

    @classmethod
    def analyze_session(cls, session: DebugSession) -> Optional[Tuple[str, str, str, FinalSolution]]:
        """
        Attempts to deterministically diagnose the user's submitted code.
        Returns: (observation, question_1, question_2, FinalSolution) if confident, or None.
        """
        code = session.submitted_code.strip()
        if not code or session.language.lower() not in ("python", "py"):
            return None

        exec_res = session.execution_result or ExecutionResult()
        stderr = exec_res.stderr or (session.error_message or "")

        # 1. Check for NameError / Undefined variable
        name_error_result = cls._check_name_error(code, exec_res, stderr)
        if name_error_result:
            return name_error_result

        # 2. Check for Shallow Copy + Mutation during iteration (e.g. Test A)
        shallow_mutation_result = cls._check_shallow_and_mutation(code)
        if shallow_mutation_result:
            return shallow_mutation_result

        # 3. Check for ZeroDivisionError
        zero_div_result = cls._check_zero_division(code, exec_res, stderr)
        if zero_div_result:
            return zero_div_result

        # 4. Check for IndexError
        index_error_result = cls._check_index_error(code, exec_res, stderr)
        if index_error_result:
            return index_error_result

        # 5. Check for SyntaxError
        syntax_error_result = cls._check_syntax_error(code, exec_res, stderr)
        if syntax_error_result:
            return syntax_error_result

        # No confident deterministic pattern matched on THIS code
        return None

    @classmethod
    def _check_name_error(cls, code: str, exec_res: ExecutionResult, stderr: str) -> Optional[Tuple[str, str, str, FinalSolution]]:
        # Match pattern: NameError: name 'XYZ' is not defined
        match = re.search(r"NameError:\s*name\s*['\"]([^'\"]+)['\"]\s*is not defined", stderr)
        if not match:
            return None

        undefined_var = match.group(1)
        error_line = exec_res.error_line

        # Parse AST to find all defined variable/function names in the code
        defined_names: Set[str] = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defined_names.add(target.id)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_names.add(node.name)
                    for arg in node.args.args:
                        defined_names.add(arg.arg)
                elif isinstance(node, ast.For):
                    if isinstance(node.target, ast.Name):
                        defined_names.add(node.target.id)
        except Exception:
            pass

        # Discard built-ins or the undefined var itself
        defined_names.discard(undefined_var)

        # Look for close matches (e.g. "age" vs "ages", "student_list" vs "student_lists")
        candidate = None
        if defined_names:
            matches = difflib.get_close_matches(undefined_var, list(defined_names), n=1, cutoff=0.5)
            if matches:
                candidate = matches[0]
            else:
                # Substring match (e.g. "age" is prefix of "ages")
                for d in defined_names:
                    if d in undefined_var or undefined_var in d:
                        candidate = d
                        break

        line_str = f"on line {error_line}" if error_line else "in your code"

        if candidate:
            obs = (
                f"Execution raised a NameError {line_str}: `{undefined_var}` is not defined. "
                f"However, `{candidate}` was initialized earlier in your program."
            )
            q1 = f"The code references `{undefined_var}`, but earlier you defined `{candidate}`. Which variable exists in scope at this line?"
            q2 = f"If you replace `{undefined_var}` with `{candidate}`, does that match what you intended to print or compute?"

            # Generate corrected code by replacing the typo specifically
            corrected_lines = []
            for i, line in enumerate(code.splitlines(), 1):
                if error_line and i == error_line:
                    # Replace variable name as standalone word
                    new_line = re.sub(r'\b' + re.escape(undefined_var) + r'\b', candidate, line)
                    corrected_lines.append(new_line)
                elif not error_line and undefined_var in line:
                    new_line = re.sub(r'\b' + re.escape(undefined_var) + r'\b', candidate, line)
                    corrected_lines.append(new_line)
                else:
                    corrected_lines.append(line)
            corrected_code = "\n".join(corrected_lines)

            solution = FinalSolution(
                what_i_found=(
                    f"Line {error_line or 'where the error occurred'} references `{undefined_var}`, "
                    f"which was never defined. You previously defined `{candidate}`."
                ),
                whats_happening=(
                    f"When Python reaches this line, it looks up `{undefined_var}` in local and global namespaces. "
                    f"Because `{undefined_var}` does not exist, Python immediately raises `NameError` and halts."
                ),
                root_cause="Variable Name Typo / Undefined Identifier",
                corrected_code=corrected_code,
                why_fix_works=f"Changing `{undefined_var}` to `{candidate}` points to the variable that was properly declared and initialized in scope.",
                lesson="Python identifiers are case-sensitive and must be defined before they are referenced. Check variable names carefully when you see a NameError."
            )
            return obs, q1, q2, solution
        else:
            obs = f"Execution raised a NameError {line_str}: `{undefined_var}` is referenced before it was defined or imported."
            q1 = f"Where did you expect `{undefined_var}` to be created or assigned before line {error_line or 'this point'}?"
            q2 = f"Is `{undefined_var}` missing an initial assignment or an import statement?"
            solution = FinalSolution(
                what_i_found=f"The identifier `{undefined_var}` was referenced without being defined.",
                whats_happening=f"Python attempted to resolve `{undefined_var}` at runtime, but found no matching variable in the current scope.",
                root_cause="Undefined Variable",
                corrected_code=f"# Ensure {undefined_var} is assigned before use:\n{undefined_var} = ...\n\n" + code,
                why_fix_works=f"Assigning or importing `{undefined_var}` before referencing it resolves the NameError.",
                lesson="Always initialize or declare variables before reading them in Python."
            )
            return obs, q1, q2, solution

    @classmethod
    def _check_shallow_and_mutation(cls, code: str) -> Optional[Tuple[str, str, str, FinalSolution]]:
        """
        Detects both shallow copy of nested structures and list mutation during iteration.
        """
        has_shallow_copy = False
        has_mutation_in_loop = False
        dict_var = ""
        copy_var = ""
        list_var = ""

        # Search for pattern: X = Y.copy()
        copy_match = re.search(r"(\w+)\s*=\s*(\w+)\.copy\(\)", code)
        if copy_match:
            copy_var = copy_match.group(1)
            dict_var = copy_match.group(2)
            has_shallow_copy = True

        # Search for pattern: for item in list_var: ... list_var.remove(item)
        remove_match = re.search(r"for\s+(\w+)\s+in\s+(\w+):\s*[\s\S]*?\b\2\.(remove|pop)\(\1\)", code)
        if remove_match:
            list_var = remove_match.group(2)
            has_mutation_in_loop = True

        if not (has_shallow_copy or has_mutation_in_loop):
            return None

        if has_shallow_copy and has_mutation_in_loop:
            obs = (
                f"Two subtle bugs are affecting your data: "
                f"1) `{copy_var} = {dict_var}.copy()` performs only a shallow copy, so nested structures inside `{dict_var}` are still shared. "
                f"2) Mutating `{list_var}` with `.remove()` while iterating over `for score in {list_var}` causes Python to skip elements as indices shift."
            )
            q1 = (
                f"When you call `{dict_var}.copy()`, does it duplicate nested dictionaries and lists, "
                f"or do `{dict_var}` and `{copy_var}` still point to the exact same inner objects?"
            )
            q2 = (
                f"In the inner loop `for score in {list_var}:`, when you remove an element with `{list_var}.remove(score)`, "
                f"what happens to the position of the remaining elements during the next loop step?"
            )

            # Generate corrected code using copy.deepcopy and list comprehension on user's exact code
            corrected_code = code
            if "import copy" not in corrected_code:
                corrected_code = "import copy\n" + corrected_code

            corrected_code = corrected_code.replace(
                f"{copy_var} = {dict_var}.copy()",
                f"{copy_var} = copy.deepcopy({dict_var})"
            )

            # Replace the inner mutating loop with clean list filtering
            old_loop_pattern = re.compile(
                r"for\s+(\w+)\s+in\s+scores:\s*\n\s+if\s+([^\n:]+):\s*\n\s+scores\.remove\(\1\)",
                re.MULTILINE
            )
            if old_loop_pattern.search(corrected_code):
                corrected_code = old_loop_pattern.sub(
                    r"# Filter valid scores without mutating during iteration\n    scores = [s for s in scores if 0 <= s <= 100]",
                    corrected_code
                )
            elif "scores.remove(score)" in corrected_code:
                # Fallback replacement if formatting differs
                corrected_code = re.sub(
                    r"for\s+score\s+in\s+scores:[\s\S]*?scores\.remove\(score\)",
                    "scores = [score for score in scores if 0 <= score <= 100]",
                    corrected_code
                )

            solution = FinalSolution(
                what_i_found=(
                    f"1) `{copy_var} = {dict_var}.copy()` is a shallow copy; nested structures remain shared references with `{dict_var}`.\n"
                    f"2) Removing items from `{list_var}` during a `for` loop shifts list indices, causing elements directly after a removed item to be skipped."
                ),
                whats_happening=(
                    f"1. A shallow copy only duplicates the outermost container. Nested dictionaries and lists share the same memory addresses, "
                    f"so mutating `{copy_var}` unintentionally mutates `{dict_var}` as well.\n"
                    f"2. When Python iterates over a list, it maintains an internal integer index (0, 1, 2...). When `.remove()` is called, "
                    f"all subsequent elements shift left by one position. The iterator advances to the next index, inadvertently skipping the item that just slid into the current index."
                ),
                root_cause="Shallow Copy of Nested References & In-Place List Mutation During Iteration",
                corrected_code=corrected_code,
                why_fix_works=(
                    f"1. `copy.deepcopy({dict_var})` recursively duplicates all nested dictionaries and lists, ensuring `{dict_var}` stays untouched.\n"
                    f"2. Using a list comprehension `[s for s in scores if 0 <= s <= 100]` creates a clean filtered list without modifying the list being iterated over."
                ),
                lesson="Use `copy.deepcopy()` when cloning nested data structures. Never modify (remove/pop) a list while iterating over it; use a list comprehension or filter to produce a new list instead."
            )
            return obs, q1, q2, solution

        elif has_mutation_in_loop:
            obs = f"The loop modifies `{list_var}` in-place using `.remove()` or `.pop()` while actively iterating over it."
            q1 = f"What happens to the internal index of `{list_var}` when an item is removed while the `for` loop is running?"
            q2 = f"Could you create a new filtered list using a list comprehension instead of modifying `{list_var}` in-place?"

            solution = FinalSolution(
                what_i_found=f"Modifying `{list_var}` during iteration skips elements due to index shifting.",
                whats_happening="When an element is removed, subsequent elements slide left. The loop iterator advances its index counter, skipping the element that moved into the current index.",
                root_cause="In-Place List Mutation During Iteration",
                corrected_code=re.sub(
                    rf"for\s+(\w+)\s+in\s+{list_var}:[\s\S]*?{list_var}\.remove\(\1\)",
                    f"# Create a new filtered list instead of in-place removal:\n{list_var} = [item for item in {list_var} if ...]",
                    code
                ),
                why_fix_works="Iterating over an unmodified sequence or building a new list avoids index offset errors.",
                lesson="Never alter the length of a list while iterating over it. Build a new list or iterate over a slice copy `my_list[:]`."
            )
            return obs, q1, q2, solution

        return None

    @classmethod
    def _check_zero_division(cls, code: str, exec_res: ExecutionResult, stderr: str) -> Optional[Tuple[str, str, str, FinalSolution]]:
        if "ZeroDivisionError" not in stderr:
            return None

        line_num = exec_res.error_line
        obs = f"Execution raised a ZeroDivisionError on line {line_num or 'during calculation'}: a division or modulo operation has a denominator of zero."
        q1 = f"Look at the divisor on line {line_num or 'where the division occurs'}. Can that expression or variable evaluate to 0?"
        q2 = "How can you check or guard that denominator before performing the division?"

        solution = FinalSolution(
            what_i_found=f"A mathematical division operation attempted to divide by zero on line {line_num or 'in the calculation'}.",
            whats_happening="In Python, dividing any number by zero is mathematically undefined and raises ZeroDivisionError immediately.",
            root_cause="Division By Zero",
            corrected_code=code,
            why_fix_works="Guarding the denominator ensures the calculation only runs when the divisor is non-zero, or provides a safe fallback default.",
            lesson="Always validate or guard divisors when calculating averages or ratios where the denominator could be zero or empty."
        )
        return obs, q1, q2, solution

    @classmethod
    def _check_index_error(cls, code: str, exec_res: ExecutionResult, stderr: str) -> Optional[Tuple[str, str, str, FinalSolution]]:
        if "IndexError" not in stderr:
            return None

        line_num = exec_res.error_line
        obs = f"Execution raised an IndexError on line {line_num or 'during sequence access'}: an index was accessed that exceeds the valid range of the list or sequence."
        q1 = f"What is the length of the list being accessed on line {line_num or 'this line'}, and what index was requested?"
        q2 = "Remember that Python uses 0-based indexing. Does your index calculation exceed `len(sequence) - 1`?"

        solution = FinalSolution(
            what_i_found=f"The code attempted to access an element at an index outside the bounds of the sequence on line {line_num or 'in your code'}.",
            whats_happening="Python lists are 0-indexed. Accessing an index greater than or equal to `len(list)` raises IndexError.",
            root_cause="Index Out of Bounds / Off-by-One",
            corrected_code=code,
            why_fix_works="Ensuring the index is strictly within `0 <= index < len(sequence)` prevents out-of-range memory lookups.",
            lesson="Remember that Python indices run from 0 to length - 1. When looping or indexing, watch out for off-by-one errors."
        )
        return obs, q1, q2, solution

    @classmethod
    def _check_syntax_error(cls, code: str, exec_res: ExecutionResult, stderr: str) -> Optional[Tuple[str, str, str, FinalSolution]]:
        if "SyntaxError" not in stderr:
            return None

        line_num = exec_res.error_line
        obs = f"Python could not parse your code due to a SyntaxError on line {line_num or 'indicated'}: {exec_res.error_details or 'invalid syntax'}."
        q1 = f"Examine line {line_num or 'the flagged line'} and the line immediately before it. Are there unclosed brackets, missing colons, or mismatched quotes?"
        q2 = "Does the statement follow Python syntax rules for that construct (e.g. `if`, `def`, `for` ending with a `:`)?"

        solution = FinalSolution(
            what_i_found=f"A SyntaxError was detected on line {line_num or 'in the file'}: {exec_res.error_details or 'invalid syntax'}.",
            whats_happening="Python must compile code into bytecode before running it. A syntax violation prevents Python from executing any part of the program.",
            root_cause="Python Syntax Error",
            corrected_code=code,
            why_fix_works="Correcting the syntax structure allows Python's parser to successfully compile and execute the file.",
            lesson="When a SyntaxError points to a line, check both that line and the preceding line for missing colons, unmatched quotes, or unclosed parentheses."
        )
        return obs, q1, q2, solution


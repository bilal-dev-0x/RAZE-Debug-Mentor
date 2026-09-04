import asyncio
import os
import re
import sys
import tempfile
from typing import Optional
from config import settings
from models import ExecutionResult

class CodeRunner:
    """
    Executes user code in an isolated subprocess with strict timeouts.
    Python is fully runnable; other languages are marked as AI-debugging only for MVP.
    """

    SUPPORTED_RUNNABLE_LANGUAGES = {"python", "py"}

    @classmethod
    def is_runnable(cls, language: str) -> bool:
        return language.lower().strip() in cls.SUPPORTED_RUNNABLE_LANGUAGES

    @classmethod
    async def run_code(cls, language: str, code: str) -> ExecutionResult:
        lang = language.lower().strip()

        if not cls.is_runnable(lang):
            return ExecutionResult(
                executed=False,
                stdout="",
                stderr="",
                exit_code=None,
                runner_message=(
                    f"Live execution is currently supported for Python in this environment. "
                    f"'{language}' is supported for AI debugging and code analysis."
                )
            )

        if not code.strip():
            return ExecutionResult(
                executed=True,
                stdout="",
                stderr="",
                exit_code=0,
                runner_message="No code to execute."
            )

        # Write code to a temporary python file
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8"
            ) as f:
                temp_file = f.name
                f.write(code)

            # Run in isolated subprocess using sys.executable with clean env
            env = {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")
            }

            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.CODE_EXEC_TIMEOUT_SECONDS
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = process.returncode
                timed_out = False

            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                return ExecutionResult(
                    executed=True,
                    stdout="",
                    stderr=f"Execution timed out after {settings.CODE_EXEC_TIMEOUT_SECONDS}s.",
                    exit_code=-1,
                    timed_out=True,
                    runner_message="Execution timed out. Check for infinite loops."
                )

            # Scrub temporary file path from stderr so user sees line numbers relative to their code
            if temp_file and temp_file in stderr:
                stderr = stderr.replace(temp_file, "submission.py")

            # Parse traceback for structured error details
            error_type, error_line, error_details = cls._parse_python_traceback(stderr)

            return ExecutionResult(
                executed=True,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                timed_out=timed_out,
                error_type=error_type,
                error_line=error_line,
                error_details=error_details,
                runner_message="Execution completed." if exit_code == 0 else "Execution completed with errors."
            )

        except Exception as e:
            return ExecutionResult(
                executed=False,
                stdout="",
                stderr=f"Runner internal error: {str(e)}",
                exit_code=-1,
                runner_message="Failed to start runner process."
            )
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    @classmethod
    def _parse_python_traceback(cls, stderr: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Parses standard Python traceback to extract error type, line number, and details.
        """
        if not stderr:
            return None, None, None

        # Look for last line exception pattern like:
        # NameError: name 'ages' is not defined
        # ZeroDivisionError: division by zero
        # SyntaxError: invalid syntax
        lines = [line.strip() for line in stderr.strip().splitlines() if line.strip()]
        if not lines:
            return None, None, None

        error_type = None
        error_details = None
        last_line = lines[-1]

        match_exc = re.match(r"^([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)$", last_line)
        if match_exc:
            error_type = match_exc.group(1)
            error_details = match_exc.group(2)
        elif "SyntaxError" in stderr:
            error_type = "SyntaxError"
            error_details = last_line

        # Extract line number from traceback: File "...", line X
        error_line = None
        line_matches = re.findall(r'line\s+(\d+)', stderr)
        if line_matches:
            try:
                error_line = int(line_matches[-1])
            except ValueError:
                pass

        return error_type, error_line, error_details


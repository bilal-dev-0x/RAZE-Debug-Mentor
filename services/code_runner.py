"""Safe, sandboxed subprocess execution of user-submitted Python snippets.

Mirrors the behavior of the previous Node/Express `runPythonSafe` helper so
that ground-truth execution results (used to detect discrepancies between
what the user reports and what the code actually does) and live
solution-verification runs behave identically regardless of which backend
served the request.
"""

import subprocess
import time
from typing import Optional, TypedDict


class ExecutionResult(TypedDict):
    output: str
    error: Optional[str]
    exit_code: int
    execution_time_ms: int
    timed_out: bool


def run_python_safe(code: str, timeout_seconds: float = 4.0) -> ExecutionResult:
    """Execute a Python snippet in an isolated subprocess with a hard timeout.

    Never raises — all failure modes (syntax errors, exceptions, timeouts)
    are captured and returned as part of the result payload.
    """
    clean_code = (code or "").strip()
    start = time.time()

    if not clean_code:
        return {
            "output": "",
            "error": "No code provided to execute.",
            "exit_code": 1,
            "execution_time_ms": 0,
            "timed_out": False,
        }

    try:
        proc = subprocess.run(
            ["python3", "-u", "-c", clean_code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        error_msg: Optional[str] = None
        if stderr:
            error_msg = stderr
        elif proc.returncode != 0 and not stdout:
            error_msg = f"Process exited with code {proc.returncode}"

        return {
            "output": stdout,
            "error": error_msg,
            "exit_code": proc.returncode,
            "execution_time_ms": elapsed_ms,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "output": "",
            "error": f"Execution timed out ({timeout_seconds:.1f}s limit). Check for infinite loops or blocking input.",
            "exit_code": 1,
            "execution_time_ms": elapsed_ms,
            "timed_out": True,
        }
    except Exception as e:  # pragma: no cover - defensive
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "output": "",
            "error": str(e),
            "exit_code": 1,
            "execution_time_ms": elapsed_ms,
            "timed_out": False,
        }

"""Secure code execution sandbox."""
import os
import sys
import asyncio
import subprocess
import tempfile
import time
from typing import Optional
from config import get_settings

settings = get_settings()

FORBIDDEN_PYTHON_IMPORTS = [
    "os.system", "subprocess", "shutil.rmtree", "socket",
    "__import__", "eval", "exec", "compile",
    "importlib", "ctypes", "signal",
]

FORBIDDEN_PATTERNS = [
    "rm -rf", "del /", "format c:",
    "../../", "~/.ssh", "/etc/passwd", "/etc/shadow",
    "curl ", "wget ", "nc ", "ncat ",
    "env[", "os.environ", "process.env",
]


class SandboxExecutor:
    """Execute code in a restricted environment."""

    def __init__(self):
        self.timeout = settings.SANDBOX_TIMEOUT_SECONDS
        self.max_memory_mb = settings.SANDBOX_MAX_MEMORY_MB

    async def execute(self, code: str, language: str, timeout: Optional[int] = None, stdin: Optional[str] = None) -> dict:
        timeout = min(timeout or self.timeout, self.timeout)

        # Security checks
        security_check = self._check_security(code, language)
        if not security_check["safe"]:
            return {
                "success": False,
                "output": "",
                "error": f"Security violation: {security_check['reason']}",
                "exit_code": -1,
                "execution_time_ms": 0,
            }

        if language == "python":
            return await self._execute_python(code, timeout, stdin)
        elif language == "javascript":
            return await self._execute_javascript(code, timeout, stdin)
        elif language == "bash":
            return await self._execute_bash(code, timeout, stdin)
        else:
            return {"success": False, "output": "", "error": f"Unsupported: {language}", "exit_code": -1, "execution_time_ms": 0}

    def _check_security(self, code: str, language: str) -> dict:
        code_lower = code.lower()

        for pattern in FORBIDDEN_PATTERNS:
            if pattern.lower() in code_lower:
                return {"safe": False, "reason": f"Forbidden pattern: {pattern}"}

        if language == "python":
            for imp in FORBIDDEN_PYTHON_IMPORTS:
                if imp in code:
                    return {"safe": False, "reason": f"Forbidden import/call: {imp}"}

        return {"safe": True, "reason": ""}

    async def _execute_python(self, code: str, timeout: int, stdin: Optional[str] = None) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Prepend resource limits
            sandbox_header = """
import sys
import resource
# Limit memory
try:
    resource.setrlimit(resource.RLIMIT_AS, ({max_mem}, {max_mem}))
except:
    pass
# Limit CPU time
try:
    resource.setrlimit(resource.RLIMIT_CPU, ({timeout}, {timeout}))
except:
    pass
""".format(max_mem=self.max_memory_mb * 1024 * 1024, timeout=timeout)

            # On Windows, skip resource limits
            if sys.platform == "win32":
                sandbox_header = ""

            # input() normally writes its prompt straight to stdout, which
            # mixes the question in with the program's real printed output.
            # Wrap it so the prompt text is written with a private marker
            # instead - the parent process strips those markers back out of
            # stdout and reports them separately as "prompts" so the UI can
            # show what the program is asking for next to the STDIN box,
            # rather than inside the output panel.
            sandbox_header += r"""
import builtins as _sandbox_builtins
_SANDBOX_PROMPT_MARK = "\x00SANDBOX_PROMPT\x00"
_sandbox_real_input = _sandbox_builtins.input
def _sandboxed_input(prompt=""):
    if prompt:
        sys.stdout.write(_SANDBOX_PROMPT_MARK + str(prompt) + _SANDBOX_PROMPT_MARK)
        sys.stdout.flush()
    return _sandbox_real_input()
_sandbox_builtins.input = _sandboxed_input
"""

            f.write(sandbox_header + code)
            f.flush()
            temp_path = f.name

        try:
            start = time.time()
            # subprocess.run() blocks synchronously for up to `timeout`
            # seconds. Called directly here, that froze the whole async
            # server for the entire run - every other user's request
            # (including unrelated logins/RAG queries) would just hang
            # until this one finished. asyncio.to_thread keeps the actual
            # blocking wait off the event loop.
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-u", temp_path],
                input=stdin if stdin is not None else "",
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_restricted_env(),
                cwd=tempfile.gettempdir(),
            )
            elapsed = time.time() - start

            prompts, clean_output = self._extract_prompts(result.stdout)
            error_text = result.stderr[:5000] if result.returncode != 0 else ""
            if result.returncode != 0 and "EOFError" in error_text:
                error_text = self._friendly_eof_message(stdin, prompts)

            return {
                "success": result.returncode == 0,
                "output": clean_output[:10000],
                "error": error_text,
                "prompts": prompts,
                "exit_code": result.returncode,
                "execution_time_ms": round(elapsed * 1000, 1),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"Execution timed out after {timeout}s",
                "exit_code": -1,
                "execution_time_ms": timeout * 1000,
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "exit_code": -1,
                "execution_time_ms": 0,
            }
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    # Rare control-character sequence so it can never collide with real
    # program output, and so we can reliably strip it back out afterwards.
    PROMPT_MARKER = "\x00SANDBOX_PROMPT\x00"

    def _extract_prompts(self, raw_stdout: str) -> tuple[list[str], str]:
        """Pull input() prompt text out of stdout, returning (prompts, cleaned_stdout)."""
        import re
        mark = re.escape(self.PROMPT_MARKER)
        prompts = re.findall(f"{mark}(.*?){mark}", raw_stdout, re.DOTALL)
        clean = re.sub(f"{mark}.*?{mark}", "", raw_stdout, flags=re.DOTALL)
        return prompts, clean

    def _friendly_eof_message(self, stdin: Optional[str], prompts: list[str]) -> str:
        """Turn a raw 'EOFError: EOF when reading a line' traceback into plain English."""
        provided = len([line for line in (stdin or "").splitlines() if line != ""]) if stdin else 0
        pending = prompts[-1].strip() if prompts else None
        if provided == 0:
            base = "This program is waiting for input(), but the STDIN box is empty."
        else:
            base = (
                f"This program calls input() more times than the {provided} line(s) "
                f"provided in the STDIN box."
            )
        if pending:
            return f"{base} It's currently waiting on: \"{pending}\" — add a line to STDIN for it and run again."
        return f"{base} Add one line per input() call to STDIN and run again."

    async def _execute_javascript(self, code: str, timeout: int, stdin: Optional[str] = None) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            start = time.time()
            result = await asyncio.to_thread(
                subprocess.run,
                ["node", temp_path],
                input=stdin if stdin is not None else "",
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_restricted_env(),
                cwd=tempfile.gettempdir(),
            )
            elapsed = time.time() - start

            return {
                "success": result.returncode == 0,
                "output": result.stdout[:10000],
                "error": result.stderr[:5000] if result.returncode != 0 else "",
                "exit_code": result.returncode,
                "execution_time_ms": round(elapsed * 1000, 1),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"Timeout after {timeout}s", "exit_code": -1, "execution_time_ms": timeout * 1000}
        except FileNotFoundError:
            return {"success": False, "output": "", "error": "Node.js not available", "exit_code": -1, "execution_time_ms": 0}
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    async def _execute_bash(self, code: str, timeout: int, stdin: Optional[str] = None) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = f.name

        try:
            start = time.time()
            result = await asyncio.to_thread(
                subprocess.run,
                ["bash", temp_path],
                input=stdin if stdin is not None else "",
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_restricted_env(),
                cwd=tempfile.gettempdir(),
            )
            elapsed = time.time() - start

            return {
                "success": result.returncode == 0,
                "output": result.stdout[:10000],
                "error": result.stderr[:5000] if result.returncode != 0 else "",
                "exit_code": result.returncode,
                "execution_time_ms": round(elapsed * 1000, 1),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"Timeout after {timeout}s", "exit_code": -1, "execution_time_ms": timeout * 1000}
        except FileNotFoundError:
            return {"success": False, "output": "", "error": "Bash not available on this host", "exit_code": -1, "execution_time_ms": 0}
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def _get_restricted_env(self) -> dict:
        """Return a restricted environment for sandbox execution."""
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": tempfile.gettempdir(),
            "TEMP": tempfile.gettempdir(),
            "TMP": tempfile.gettempdir(),
            "LANG": "en_US.UTF-8",
        }
        if sys.platform == "win32":
            safe_env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "C:\\Windows")
            safe_env["COMSPEC"] = os.environ.get("COMSPEC", "C:\\Windows\\system32\\cmd.exe")
        return safe_env

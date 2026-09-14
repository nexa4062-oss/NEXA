from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth.service import get_current_user, require_permission
from models.orm import User
from sandbox.executor import SandboxExecutor
from routing.service import ModelRouter
from models.runtime import OllamaRuntime
from audit.service import log_audit_event
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
executor = SandboxExecutor()
model_router = ModelRouter()
runtime = OllamaRuntime()


class CodeExecuteRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: Optional[int] = None
    stdin: Optional[str] = None


@router.post("/execute")
async def execute_code(
    data: CodeExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("execute_code")),
):
    if data.language not in ("python", "javascript", "bash"):
        raise HTTPException(status_code=400, detail=f"Unsupported language: {data.language}")

    result = await executor.execute(
        code=data.code,
        language=data.language,
        timeout=data.timeout,
        stdin=data.stdin,
    )

    await log_audit_event(
        db, current_user.id, "code_executed", "sandbox", None,
        {"language": data.language, "code_length": len(data.code), "success": result["success"]}
    )

    return result


@router.get("/languages")
async def supported_languages(current_user: User = Depends(get_current_user)):
    return {
        "languages": [
            {"id": "python", "name": "Python", "version": "3.x", "available": True},
            {"id": "javascript", "name": "JavaScript", "version": "Node.js", "available": True},
            {"id": "bash", "name": "Bash", "version": "5.x", "available": True},
        ]
    }


class CodeDebugRequest(BaseModel):
    code: str
    language: str = "python"
    stdin: Optional[str] = None
    # Free-text description of what's wrong / what the user expected,
    # e.g. "should print sorted list but throws IndexError". Optional -
    # the sandbox's own execution output is used either way.
    issue_description: Optional[str] = None


def _build_debug_prompt(code: str, language: str, exec_result: dict, issue_description: Optional[str]) -> str:
    status = "succeeded" if exec_result["success"] else "FAILED"
    parts = [
        "You are a senior software engineer debugging code for a colleague. "
        "Be specific and concrete - point to exact lines/logic, not generic advice.",
        f"\nLanguage: {language}",
        f"\nCode:\n```{language}\n{code}\n```",
        f"\nSandbox execution {status} (exit code {exec_result.get('exit_code')}).",
    ]
    if exec_result.get("output"):
        parts.append(f"\nStdout:\n{exec_result['output'][:4000]}")
    if exec_result.get("error"):
        parts.append(f"\nStderr / traceback:\n{exec_result['error'][:4000]}")
    if issue_description:
        parts.append(f"\nWhat the user says is wrong: {issue_description}")
    parts.append(
        "\nRespond in this exact structure:\n"
        "## What's wrong\n(root cause, referencing specific lines/logic)\n\n"
        "## Fix\n```" + language + "\n(the corrected full code)\n```\n\n"
        "## Why this fixes it\n(brief explanation)"
    )
    return "\n".join(parts)


@router.post("/debug")
async def debug_code(
    data: CodeDebugRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("execute_code")),
):
    """Debug-focused workflow for Code Laboratory: actually run the code
    in the sandbox first (so the model sees the real error/output, not a
    guess), then ask the local coding-capable Ollama model to explain the
    root cause and propose a fix. This is what Code Lab is for - working
    through real, possibly-large code with a colleague-style review, not
    just executing trivial one-liners."""
    if data.language not in ("python", "javascript", "bash"):
        raise HTTPException(status_code=400, detail=f"Unsupported language: {data.language}")

    exec_result = await executor.execute(
        code=data.code, language=data.language, stdin=data.stdin,
    )

    prompt = _build_debug_prompt(data.code, data.language, exec_result, data.issue_description)
    route = await model_router.route_request(prompt, task_type="coding")
    model_id = route.get("model_id")

    await log_audit_event(
        db, current_user.id, "code_debug_requested", "sandbox", None,
        {"language": data.language, "code_length": len(data.code), "exec_success": exec_result["success"]}
    )

    if not model_id:
        return {
            "execution": exec_result,
            "analysis": None,
            "model_used": None,
            "error": "No local coding-capable Ollama model is available. "
                     "Pull one (e.g. `ollama pull qwen2.5-coder`) to enable AI-assisted debugging - "
                     "raw execution above still works without it.",
        }

    analysis = await runtime.generate(model_id, prompt)

    return {
        "execution": exec_result,
        "analysis": analysis,
        "model_used": model_id,
    }

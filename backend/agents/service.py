"""Agent service - thin wrapper that drives the LangGraph workflow
(agents/graph.py) and translates its state into the API response shape.

Responsibilities are split exactly as specified:
  - LangGraph (agents/graph.py) controls WHAT HAPPENS NEXT: routing,
    conditional branching, the HITL pause/resume.
  - LangChain (agents/llm.py) connects to the LLM/tools with structured
    calls (ChatOllama, StructuredTool wrappers).
  - Existing RBAC/RAGService/SandboxExecutor remain the sole authority
    on WHAT THE USER IS ALLOWED TO ACCESS - this file and graph.py only
    call into them, never re-implement or bypass their checks.

A HITL pause can legitimately outlive the HTTP request that triggered it
(a human may take minutes or hours to approve) so the original request's
AsyncSession cannot be held open across it. Instead: only plain
JSON-serializable data lives in the graph's checkpointed AgentState; the
DB session, current user, and service instances are passed fresh via
`config["configurable"]` on every call (both the initial run and the
later resume), while the AsyncSqliteSaver checkpoint persists everything
else needed to continue that specific run.
"""
import uuid
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command

from models.orm import User, ApprovalRequest, ApprovalStatus
from models.runtime import OllamaRuntime
from rag.service import RAGService
from sandbox.executor import SandboxExecutor
from generation.service import FileGenerator
from auth.service import collect_permissions
from audit.service import log_audit_event, log_security_event
from agents.graph import get_graph

NODE_MESSAGES = {
    "understand_intent": "Understanding request...",
    "permission_gate": "Checking permissions...",
    "plan": "Planning workflow...",
    "hitl_gate": "Evaluating whether human approval is required...",
    "code_node": "Running code in sandbox...",
    "rag_node": "Searching authorized knowledge base...",
    "vision_node": "Loading authorized image attachments...",
    "file_generation_node": "Drafting content and creating the file...",
    "direct_node": "Preparing direct response...",
    "act": "Generating response...",
    "validate": "Validating result...",
}
# The graph node is named permission_gate; every other surface (the
# non-streaming steps list, tests) labels this phase permission_check -
# keep the streamed event's phase name consistent with that.
NODE_PHASE_LABELS = {"permission_gate": "permission_check"}


class AgentService:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.rag = RAGService(db, user)
        self.sandbox = SandboxExecutor()
        self.runtime = OllamaRuntime()
        self.file_generator = FileGenerator()

    def _config(self, thread_id: str) -> dict:
        return {
            "configurable": {
                "thread_id": thread_id,
                "db": self.db,
                "user": self.user,
                "user_permissions": list(collect_permissions(self.user)),
                "rag_service": self.rag,
                "sandbox": self.sandbox,
                "runtime": self.runtime,
                "file_generator": self.file_generator,
            }
        }

    # ------------------------------------------------------------------
    # HITL bookkeeping (unchanged from before: an ApprovalRequest DB row
    # is still the durable record an approver acts on; it now also
    # carries the LangGraph thread_id so approve/reject can resume the
    # exact paused graph run instead of re-deriving the request by hand)
    # ------------------------------------------------------------------
    async def _create_approval(self, task_type: str, thread_id: str, query: str, reason: str) -> ApprovalRequest:
        req = ApprovalRequest(
            id=uuid.uuid4(),
            requested_by=self.user.id,
            action_type=task_type,
            reason=reason,
            payload={"thread_id": thread_id, "query": query},
            status=ApprovalStatus.PENDING,
        )
        self.db.add(req)
        await self.db.flush()
        await log_audit_event(self.db, self.user.id, "agent_approval_requested", "approval_request", str(req.id), {"task_type": task_type})
        return req

    async def _deny(self, task_type: str, missing: str) -> None:
        await log_security_event(self.db, "agent_permission_denied", "blocked", source=str(self.user.id),
                                  details={"task_type": task_type, "missing_permission": missing})
        await log_audit_event(self.db, self.user.id, "agent_permission_denied", "agent", None,
                               {"task_type": task_type, "missing_permission": missing}, severity="warning")

    async def _finalize(self, result: dict, thread_id: str) -> dict:
        if result.get("__interrupt__"):
            payload = result["__interrupt__"][0].value
            approval = await self._create_approval(payload["task_type"], thread_id, payload["query"], payload["reason"])
            return {
                "status": "waiting_approval",
                "approval_id": str(approval.id),
                "task_type": payload["task_type"],
                "steps": result.get("steps", []),
                "mode": result.get("mode", "balanced"),
            }

        status = result.get("status")
        if status == "denied":
            await self._deny(result["task_type"], result["missing_permission"])
            return {
                "status": "denied",
                "error": f"Permission denied: '{result['missing_permission']}' is required for this action.",
                "missing_permission": result["missing_permission"],
                "task_type": result["task_type"],
                "steps": result["steps"],
            }
        if status == "error":
            # An error before a model was even selected (plan_node) has no
            # response text; a branch-node failure (e.g. file generation)
            # already wrote an honest, specific one - prefer that.
            error_message = result.get("response") or "No model available"
            return {"status": "error", "error": error_message, "task_type": result.get("task_type"), "steps": result["steps"]}
        if status == "rejected":
            return {"status": "rejected", "task_type": result.get("task_type"), "steps": result["steps"]}

        # completed
        await log_audit_event(self.db, self.user.id, "agent_executed", "agent", None,
                               {"query": result.get("query", "")[:100], "mode": result.get("mode", "balanced"), "task_type": result.get("task_type")})
        return {
            "status": "completed",
            "answer": result.get("response", ""),
            "model_used": result.get("model_id"),
            "task_type": result.get("task_type"),
            "steps": result["steps"],
            "mode": result.get("mode", "balanced"),
            "sandbox_result": result.get("sandbox_result"),
            "generated_file": result.get("generated_file"),
        }

    # ------------------------------------------------------------------
    # Non-streaming entrypoint
    # ------------------------------------------------------------------
    async def execute(
        self, query: str, attachments: Optional[list[dict]] = None, mode: str = "balanced",
        enable_tools: bool = True, enable_rag: bool = True, language: Optional[str] = None,
        code: Optional[str] = None, code_language: Optional[str] = None,
    ) -> dict:
        graph = get_graph()
        thread_id = str(uuid.uuid4())
        initial_state = {
            "query": query, "attachments": attachments, "mode": mode,
            "enable_tools": enable_tools, "enable_rag": enable_rag,
            "language": language, "code": code, "code_language": code_language,
            "steps": [],
        }
        result = await graph.ainvoke(initial_state, config=self._config(thread_id))
        return await self._finalize(result, thread_id)

    # ------------------------------------------------------------------
    # Resume a HITL-paused run (approve/reject)
    # ------------------------------------------------------------------
    async def resume(self, thread_id: str, decision: str) -> dict:
        graph = get_graph()
        result = await graph.ainvoke(Command(resume=decision), config=self._config(thread_id))
        return await self._finalize(result, thread_id)

    # ------------------------------------------------------------------
    # Streaming entrypoint - real token-level streaming (via LangGraph's
    # astream_events, which surfaces every LangChain chat-model chunk
    # called inside any node) plus a phase-status event per node.
    # ------------------------------------------------------------------
    async def execute_stream(
        self, query: str, attachments: Optional[list[dict]] = None, mode: str = "balanced",
        enable_tools: bool = True, enable_rag: bool = True, language: Optional[str] = None,
        code: Optional[str] = None, code_language: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        graph = get_graph()
        thread_id = str(uuid.uuid4())
        initial_state = {
            "query": query, "attachments": attachments, "mode": mode,
            "enable_tools": enable_tools, "enable_rag": enable_rag,
            "language": language, "code": code, "code_language": code_language,
            "steps": [],
        }
        config = self._config(thread_id)

        async for ev in graph.astream_events(initial_state, config=config, version="v2"):
            kind = ev["event"]
            if kind == "on_chat_model_stream":
                # Skip the internal document-drafting call's tokens (tagged
                # "file_draft" in file_generation_node) - the user sees the
                # short creation-confirmation message instead, not the raw
                # draft that's already safely inside the generated file.
                if "file_draft" in (ev.get("tags") or []):
                    continue
                chunk = ev["data"]["chunk"].content
                if chunk:
                    yield {"type": "token", "content": chunk}
            elif kind == "on_chain_end" and ev.get("name") in NODE_MESSAGES:
                output = ev["data"].get("output") or {}
                phase = NODE_PHASE_LABELS.get(ev["name"], ev["name"])
                message = NODE_MESSAGES[ev["name"]]
                steps = output.get("steps") if isinstance(output, dict) else None
                if steps:
                    message = steps[-1]["result"]
                yield {"type": "status", "phase": phase, "message": message}

        snapshot = await graph.aget_state(config)
        if snapshot.next:
            # Paused at hitl_gate awaiting approval
            task = snapshot.tasks[0]
            payload = task.interrupts[0].value
            approval = await self._create_approval(payload["task_type"], thread_id, payload["query"], payload["reason"])
            yield {
                "type": "approval_required", "phase": "hitl_gate", "message": "Waiting for human approval",
                "approval_id": str(approval.id), "task_type": payload["task_type"],
            }
            return

        final_state = snapshot.values
        status = final_state.get("status")
        if status == "denied":
            await self._deny(final_state["task_type"], final_state["missing_permission"])
            yield {
                "type": "denied", "phase": "permission_check",
                "message": f"Permission denied: '{final_state['missing_permission']}' is required for this action.",
                "missing_permission": final_state["missing_permission"], "task_type": final_state["task_type"],
            }
            return
        if status == "error" or not final_state.get("model_id"):
            yield {"type": "error", "message": final_state.get("response") or "No model available"}
            return

        await log_audit_event(self.db, self.user.id, "agent_executed", "agent", None,
                               {"query": query[:100], "mode": mode, "task_type": final_state.get("task_type")})
        # If the response text wasn't streamed as tokens (file_generation_node
        # sets it directly, not via a streamed chat-model call), the chat
        # bubble would otherwise stay empty - send it as one final chunk
        # before "done" so the message is fully populated either way.
        if final_state.get("generated_file") and final_state.get("response"):
            yield {"type": "token", "content": final_state["response"]}
        yield {
            "type": "done", "model_used": final_state.get("model_id"), "task_type": final_state.get("task_type"),
            "generated_file": final_state.get("generated_file"),
        }

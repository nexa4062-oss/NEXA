from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import json
import uuid
from datetime import datetime

from database import get_db
from auth.service import get_current_user, require_permission
from models.orm import User, ApprovalRequest, ApprovalStatus, Role, RolePermission, UserPermission
from agents.service import AgentService
from audit.service import log_audit_event

router = APIRouter()


class AgentRequest(BaseModel):
    query: str
    attachments: Optional[list[dict]] = None
    mode: str = "balanced"
    enable_tools: bool = True
    enable_rag: bool = True
    # BCP-47-ish language name/code the model should answer in, e.g.
    # "Hindi", "Tamil", "es". None/omitted = let the model respond
    # naturally (it already tends to match the query's own language).
    language: Optional[str] = None
    # Optional explicit code to run through the sandbox -> AI-debug
    # workflow (see PRIMARY TASK 1, "CODE DEBUGGING"). When both are set,
    # the request is always routed as a "coding" task regardless of the
    # query text.
    code: Optional[str] = None
    code_language: Optional[str] = None


@router.post("/execute")
async def execute_agent(
    data: AgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = AgentService(db, current_user)
    result = await agent.execute(
        query=data.query,
        attachments=data.attachments,
        mode=data.mode,
        enable_tools=data.enable_tools,
        enable_rag=data.enable_rag,
        language=data.language,
        code=data.code,
        code_language=data.code_language,
    )
    # Auditing (executed / permission_denied / approval_requested) happens
    # inside AgentService itself, since it knows which of those actually
    # occurred - not duplicated here.
    return result


@router.post("/execute/stream")
async def execute_agent_stream(
    data: AgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = AgentService(db, current_user)

    async def event_stream():
        async for event in agent.execute_stream(
            query=data.query,
            attachments=data.attachments,
            mode=data.mode,
            enable_tools=data.enable_tools,
            enable_rag=data.enable_rag,
            language=data.language,
            code=data.code,
            code_language=data.code_language,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ----------------------------------------------------------------------
# Human-in-the-Loop approvals
# ----------------------------------------------------------------------
def _serialize_approval(req: ApprovalRequest) -> dict:
    return {
        "id": str(req.id),
        "requested_by": str(req.requested_by),
        "requester_name": req.requester.display_name if req.requester else None,
        "action_type": req.action_type,
        "reason": req.reason,
        "query_preview": (req.payload or {}).get("query", "")[:200],
        "status": req.status.value if hasattr(req.status, "value") else req.status,
        "resolved_by": str(req.resolved_by) if req.resolved_by else None,
        "resolved_at": req.resolved_at.isoformat() if req.resolved_at else None,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.get("/approvals")
async def list_approvals(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("approve_agent_actions")),
):
    """Queue of HITL approval requests. Restricted to users who hold
    'approve_agent_actions' - not every user can approve, per spec."""
    stmt = select(ApprovalRequest).options(selectinload(ApprovalRequest.requester)).order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    else:
        stmt = stmt.where(ApprovalRequest.status == ApprovalStatus.PENDING)
    result = await db.execute(stmt)
    return {"approvals": [_serialize_approval(r) for r in result.scalars().all()]}


@router.get("/approvals/mine")
async def my_approvals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A requester checking on the status of their own pending/resolved
    actions - does not require approval authority, only ownership."""
    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.requester))
        .where(ApprovalRequest.requested_by == current_user.id)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return {"approvals": [_serialize_approval(r) for r in result.scalars().all()]}


@router.post("/approvals/{approval_id}/approve")
async def approve_action(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("approve_agent_actions")),
):
    result = await db.execute(
        select(ApprovalRequest).options(selectinload(ApprovalRequest.requester)).where(ApprovalRequest.id == approval_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Request already {req.status.value}")

    # Execute under the ORIGINAL REQUESTER's identity and permissions -
    # approval is an additional control on top of RBAC, not a way for the
    # approver to grant themselves or anyone else extra access.
    requester_result = await db.execute(
        select(User)
        .options(
            selectinload(User.role).selectinload(Role.permissions).selectinload(RolePermission.permission),
            selectinload(User.permissions).selectinload(UserPermission.permission),
        )
        .where(User.id == req.requested_by)
    )
    requester = requester_result.scalar_one_or_none()
    if not requester:
        raise HTTPException(status_code=404, detail="Original requester no longer exists")

    thread_id = (req.payload or {}).get("thread_id")
    if not thread_id:
        raise HTTPException(status_code=500, detail="Approval request has no associated workflow run")

    # Resume the exact paused LangGraph run via Command(resume=...) -
    # execution continues from the interrupt() call inside hitl_gate,
    # not a re-derivation of the original request.
    agent = AgentService(db, requester)
    exec_result = await agent.resume(thread_id, "approved")

    req.status = ApprovalStatus.APPROVED
    req.resolved_by = current_user.id
    req.resolved_at = datetime.utcnow()
    req.result = exec_result
    await db.flush()

    await log_audit_event(db, current_user.id, "agent_approval_granted", "approval_request", str(req.id),
                           {"action_type": req.action_type, "requested_by": str(req.requested_by)})

    return {"message": "Approved and executed", "approval": _serialize_approval(req), "result": exec_result}


@router.post("/approvals/{approval_id}/reject")
async def reject_action(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("approve_agent_actions")),
):
    result = await db.execute(
        select(ApprovalRequest).options(selectinload(ApprovalRequest.requester)).where(ApprovalRequest.id == approval_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Request already {req.status.value}")

    thread_id = (req.payload or {}).get("thread_id")
    if thread_id:
        # Resume the paused graph with a reject decision - hitl_gate's
        # interrupt() returns "rejected", the graph routes straight to
        # END without ever reaching code/RAG/vision/act. Nothing executes.
        agent = AgentService(db, current_user)
        await agent.resume(thread_id, "rejected")

    req.status = ApprovalStatus.REJECTED
    req.resolved_by = current_user.id
    req.resolved_at = datetime.utcnow()
    await db.flush()

    await log_audit_event(db, current_user.id, "agent_approval_rejected", "approval_request", str(req.id),
                           {"action_type": req.action_type, "requested_by": str(req.requested_by)})

    return {"message": "Rejected - agent stopped safely", "approval": _serialize_approval(req)}

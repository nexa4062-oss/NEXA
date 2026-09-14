from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from auth.service import get_current_user
from models.orm import User
from routing.service import ModelRouter

router = APIRouter()
model_router = ModelRouter()


class RouteRequest(BaseModel):
    query: str
    task_type: Optional[str] = None
    attachments: Optional[list[dict]] = None
    mode: str = "balanced"


@router.post("/route")
async def route_request(
    data: RouteRequest,
    current_user: User = Depends(get_current_user),
):
    result = await model_router.route_request(
        query=data.query,
        task_type=data.task_type,
        attachments=data.attachments,
        mode=data.mode,
    )
    return result


@router.post("/classify")
async def classify_task(
    data: RouteRequest,
    current_user: User = Depends(get_current_user),
):
    task_type = model_router.classify_task(data.query, data.attachments)
    return {"task_type": task_type, "query": data.query[:100]}

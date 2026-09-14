from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from auth.service import get_current_user
from models.orm import User

router = APIRouter()


class CalculateRequest(BaseModel):
    expression: str
    variables: Optional[dict] = None


@router.get("/available")
async def list_tools(current_user: User = Depends(get_current_user)):
    return {
        "tools": [
            {"id": "calculator", "name": "Calculator", "description": "Deterministic math calculations"},
            {"id": "knowledge_search", "name": "Knowledge Search", "description": "Search organizational knowledge base"},
            {"id": "code_execute", "name": "Code Executor", "description": "Execute code in sandbox"},
            {"id": "file_generate", "name": "File Generator", "description": "Generate documents"},
            {"id": "ocr", "name": "OCR", "description": "Extract text from images/scans"},
        ]
    }


@router.post("/calculate")
async def calculate(
    data: CalculateRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        allowed_names = {"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow}
        if data.variables:
            allowed_names.update(data.variables)

        # Safe eval with restricted builtins
        result = eval(data.expression, {"__builtins__": {}}, allowed_names)
        return {"result": result, "expression": data.expression, "success": True}
    except Exception as e:
        return {"result": None, "expression": data.expression, "success": False, "error": str(e)}

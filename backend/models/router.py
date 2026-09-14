from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from database import get_db
from config import get_settings
from auth.service import get_current_user, require_permission
from models.orm import User, ModelRecord, ModelCapability, ModelStatus, CapabilityType
from models.runtime import OllamaRuntime, RuntimeManager
from audit.service import log_audit_event

router = APIRouter()
settings = get_settings()
runtime_manager = RuntimeManager()


class ModelRegister(BaseModel):
    model_id: str
    display_name: str
    runtime: str = "ollama"
    local_identifier: str
    context_length: Optional[int] = None
    parameter_size: Optional[str] = None
    quantization: Optional[str] = None
    vision_support: bool = False
    coding_support: bool = False
    reasoning_support: bool = False
    embedding_support: bool = False
    capabilities: list[str] = []
    priority: int = 50


class ModelUpdate(BaseModel):
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    capabilities: Optional[list[str]] = None


@router.get("/")
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ModelRecord).order_by(ModelRecord.priority.desc())
    result = await db.execute(stmt)
    models = result.scalars().all()

    return {
        "models": [
            {
                "id": str(m.id),
                "model_id": m.model_id,
                "display_name": m.display_name,
                "runtime": m.runtime,
                "local_identifier": m.local_identifier,
                "context_length": m.context_length,
                "parameter_size": m.parameter_size,
                "quantization": m.quantization,
                "vision_support": m.vision_support,
                "coding_support": m.coding_support,
                "reasoning_support": m.reasoning_support,
                "embedding_support": m.embedding_support,
                "status": m.status.value if m.status else "unknown",
                "priority": m.priority,
                "enabled": m.enabled,
            }
            for m in models
        ]
    }


@router.get("/discover")
async def discover_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_models")),
):
    """Discover locally available models from all runtimes."""
    ollama = runtime_manager.get_runtime("ollama")
    discovered = []

    # Known model catalog: models the workbench explicitly supports and
    # wants to surface in Model Control even before they've been pulled,
    # so the operator can see what's expected/available vs. missing.
    # Currently just the requested vision model - not meant to duplicate
    # the full routing/service.py capability map.
    KNOWN_CATALOG_MODELS = [
        {"name": "llama3.2-vision", "family": "llama3.2-vision"},
    ]

    if ollama:
        models = await ollama.list_models()
        for m in models:
            name = m.get("name", "")
            existing = await db.execute(select(ModelRecord).where(ModelRecord.model_id == name))
            is_registered = existing.scalar_one_or_none() is not None

            info = await ollama.model_info(name)
            details = m.get("details", {})

            discovered.append({
                "name": name,
                "size": m.get("size", 0),
                "runtime": "ollama",
                "registered": is_registered,
                "family": details.get("family", ""),
                "parameter_size": details.get("parameter_size", ""),
                "quantization": details.get("quantization_level", ""),
                "format": details.get("format", ""),
                "installed": True,
            })

        # Add a placeholder entry for any catalog model that isn't actually
        # pulled in Ollama yet, so the UI can show it as a known-but-missing
        # option instead of it silently not appearing at all.
        discovered_names = [d["name"] for d in discovered]
        for catalog_model in KNOWN_CATALOG_MODELS:
            already_present = any(
                catalog_model["name"] in n or n.startswith(catalog_model["name"])
                for n in discovered_names
            )
            if not already_present:
                discovered.append({
                    "name": catalog_model["name"],
                    "size": 0,
                    "runtime": "ollama",
                    "registered": False,
                    "family": catalog_model["family"],
                    "parameter_size": "",
                    "quantization": "",
                    "format": "",
                    "installed": False,
                })

    return {"discovered": discovered}


@router.post("/register")
async def register_model(
    data: ModelRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_models")),
):
    existing = await db.execute(select(ModelRecord).where(ModelRecord.model_id == data.model_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Model already registered")

    model = ModelRecord(
        model_id=data.model_id,
        display_name=data.display_name,
        runtime=data.runtime,
        provider=data.runtime,
        local_identifier=data.local_identifier,
        context_length=data.context_length,
        parameter_size=data.parameter_size,
        quantization=data.quantization,
        vision_support=data.vision_support,
        coding_support=data.coding_support,
        reasoning_support=data.reasoning_support,
        embedding_support=data.embedding_support,
        status=ModelStatus.REGISTERED,
        priority=data.priority,
        enabled=True,
    )
    db.add(model)
    await db.flush()

    for cap_name in data.capabilities:
        try:
            cap_type = CapabilityType(cap_name)
            cap = ModelCapability(model_id=model.id, capability=cap_type, score=0.7)
            db.add(cap)
        except ValueError:
            pass
    await db.flush()

    await log_audit_event(db, current_user.id, "model_registered", "model", str(model.id),
                          {"model_id": data.model_id})
    return {"id": str(model.id), "message": "Model registered successfully"}


@router.patch("/{model_id}")
async def update_model(
    model_id: UUID,
    data: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_models")),
):
    stmt = select(ModelRecord).where(ModelRecord.id == model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if data.enabled is not None:
        model.enabled = data.enabled
        model.status = ModelStatus.ENABLED if data.enabled else ModelStatus.DISABLED
    if data.priority is not None:
        model.priority = data.priority
    await db.flush()

    await log_audit_event(db, current_user.id, "model_updated", "model", str(model_id))
    return {"message": "Model updated"}


@router.post("/{model_id}/test")
async def test_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("manage_models")),
):
    stmt = select(ModelRecord).where(ModelRecord.id == model_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    runtime = runtime_manager.get_runtime(model.runtime)
    if not runtime:
        raise HTTPException(status_code=400, detail=f"Runtime '{model.runtime}' not available")

    import time
    start = time.time()

    # Embedding-only models (e.g. nomic-embed-text) don't implement Ollama's
    # /api/generate completion endpoint at all and always return
    # "400 Bad Request" if you try to chat with them. Test those through the
    # embeddings endpoint instead of the text-generation endpoint.
    is_embedding_only = model.embedding_support and not (model.reasoning_support or model.coding_support)

    if is_embedding_only:
        vector = await runtime.embeddings(model.local_identifier, "Sovereign AI Workbench connectivity check")
        elapsed = time.time() - start
        success = isinstance(vector, list) and len(vector) > 0
        response = f"Generated embedding vector of length {len(vector)}" if success else "Error: Failed to generate embedding"
    else:
        response = await runtime.generate(model.local_identifier, "Say 'hello' in one word.")
        elapsed = time.time() - start
        success = len(response) > 0 and not response.startswith("Error:")

    if success:
        model.status = ModelStatus.VALIDATED
    else:
        model.status = ModelStatus.ERROR
    await db.flush()

    return {
        "model_id": model.model_id,
        "success": success,
        "response": response[:200],
        "latency_ms": round(elapsed * 1000, 1),
        "status": model.status.value,
    }


@router.get("/health")
async def models_health(
    current_user: User = Depends(get_current_user),
):
    return await runtime_manager.health_check_all()

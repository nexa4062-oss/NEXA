import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.orm import ModelRecord, ModelCapability, ModelStatus, CapabilityType


class ModelRegistry:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def discover_model(self, model_id: str, display_name: str,
                             runtime: str, local_identifier: str,
                             **kwargs) -> ModelRecord:
        existing = await self.get_by_model_id(model_id)
        if existing:
            return existing

        record = ModelRecord(
            id=uuid.uuid4(),
            model_id=model_id,
            display_name=display_name,
            runtime=runtime,
            local_identifier=local_identifier,
            provider=kwargs.get("provider"),
            context_length=kwargs.get("context_length"),
            parameter_size=kwargs.get("parameter_size"),
            quantization=kwargs.get("quantization"),
            vision_support=kwargs.get("vision_support", False),
            coding_support=kwargs.get("coding_support", False),
            reasoning_support=kwargs.get("reasoning_support", False),
            embedding_support=kwargs.get("embedding_support", False),
            hardware_requirements=kwargs.get("hardware_requirements", {}),
            status=ModelStatus.DISCOVERED,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def register_model(self, model_id: str,
                             capabilities: list[CapabilityType],
                             priority: int = 50) -> Optional[ModelRecord]:
        record = await self.get_by_model_id(model_id)
        if not record:
            return None

        record.status = ModelStatus.REGISTERED
        record.priority = priority
        record.updated_at = datetime.utcnow()

        for cap in capabilities:
            existing_cap = None
            for mc in record.capabilities:
                if mc.capability == cap:
                    existing_cap = mc
                    break
            if not existing_cap:
                mc = ModelCapability(
                    id=uuid.uuid4(),
                    model_id=record.id,
                    capability=cap,
                    score=0.5,
                )
                self.db.add(mc)

        await self.db.flush()
        return record

    async def validate_model(self, model_id: str) -> Optional[ModelRecord]:
        record = await self.get_by_model_id(model_id)
        if not record:
            return None
        record.status = ModelStatus.VALIDATED
        record.updated_at = datetime.utcnow()
        await self.db.flush()
        return record

    async def enable_model(self, model_id: str) -> Optional[ModelRecord]:
        record = await self.get_by_model_id(model_id)
        if not record:
            return None
        record.status = ModelStatus.ENABLED
        record.enabled = True
        record.updated_at = datetime.utcnow()
        await self.db.flush()
        return record

    async def disable_model(self, model_id: str) -> Optional[ModelRecord]:
        record = await self.get_by_model_id(model_id)
        if not record:
            return None
        record.status = ModelStatus.DISABLED
        record.enabled = False
        record.updated_at = datetime.utcnow()
        await self.db.flush()
        return record

    async def get_by_model_id(self, model_id: str) -> Optional[ModelRecord]:
        stmt = (
            select(ModelRecord)
            .options(selectinload(ModelRecord.capabilities))
            .where(ModelRecord.model_id == model_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, enabled_only: bool = False) -> list[ModelRecord]:
        stmt = select(ModelRecord).options(selectinload(ModelRecord.capabilities))
        if enabled_only:
            stmt = stmt.where(ModelRecord.enabled == True)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_capability(self, capability: CapabilityType,
                                enabled_only: bool = True) -> list[ModelRecord]:
        stmt = (
            select(ModelRecord)
            .join(ModelCapability)
            .options(selectinload(ModelRecord.capabilities))
            .where(ModelCapability.capability == capability)
        )
        if enabled_only:
            stmt = stmt.where(ModelRecord.enabled == True)
        stmt = stmt.order_by(ModelRecord.priority.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_health(self, model_id: str, healthy: bool):
        record = await self.get_by_model_id(model_id)
        if record:
            record.last_health_check = datetime.utcnow()
            if not healthy and record.status == ModelStatus.ENABLED:
                record.status = ModelStatus.ERROR
            await self.db.flush()

    async def set_capability_score(self, model_id: str,
                                   capability: CapabilityType,
                                   score: float):
        record = await self.get_by_model_id(model_id)
        if not record:
            return
        for mc in record.capabilities:
            if mc.capability == capability:
                mc.score = score
                break
        await self.db.flush()

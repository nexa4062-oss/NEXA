from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"
    PENDING = "pending"


class DocumentClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


class CapabilityType(str, Enum):
    GENERAL_REASONING = "general_reasoning"
    CODING = "coding"
    VISION = "vision"
    DOCUMENT_REASONING = "document_reasoning"
    FAST_CHAT = "fast_chat"
    EMBEDDING = "embedding"
    AUDIO_SPEECH = "audio_speech"


class ResponseMode(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserCreate(BaseModel):
    employee_id: str
    username: str
    display_name: str
    email: Optional[str] = None
    department_id: Optional[UUID] = None
    designation: Optional[str] = None
    role_id: UUID
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    department_id: Optional[UUID] = None
    designation: Optional[str] = None
    role_id: Optional[UUID] = None
    status: Optional[UserStatus] = None


class UserResponse(BaseModel):
    id: UUID
    employee_id: str
    username: str
    display_name: str
    email: Optional[str]
    department_id: Optional[UUID]
    designation: Optional[str]
    role_id: UUID
    role_name: Optional[str] = None
    department_name: Optional[str] = None
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# Role schemas
class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    is_system: bool
    permissions: list[str] = []

    class Config:
        from_attributes = True


class PermissionAssign(BaseModel):
    permission_ids: list[UUID]


# Document schemas
class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    mime_type: Optional[str]
    file_size: int
    classification: DocumentClassification
    is_ocr_processed: bool
    is_indexed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentPermissionCreate(BaseModel):
    user_id: Optional[UUID] = None
    role_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    can_read: bool = True
    can_download: bool = False


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    mime_type: Optional[str]
    file_size: Optional[int]
    classification: DocumentClassification
    owner_id: UUID
    department_id: Optional[UUID]
    description: Optional[str]
    page_count: Optional[int]
    is_ocr_processed: bool
    is_indexed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Model schemas
class ModelResponse(BaseModel):
    id: UUID
    model_id: str
    display_name: str
    runtime: str
    provider: Optional[str]
    local_identifier: str
    context_length: Optional[int]
    parameter_size: Optional[str]
    quantization: Optional[str]
    vision_support: bool
    coding_support: bool
    reasoning_support: bool
    embedding_support: bool
    status: str
    priority: int
    enabled: bool
    capabilities: list[str] = []

    class Config:
        from_attributes = True


class ModelRegisterRequest(BaseModel):
    local_identifier: str
    display_name: Optional[str] = None
    capabilities: list[CapabilityType] = []
    priority: int = 50


# AI Chat schemas
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    attachments: list[str] = []
    mode: ResponseMode = ResponseMode.BALANCED
    model_override: Optional[str] = None


class RoutingDecision(BaseModel):
    task_type: str
    selected_model: str
    reason: str
    fallback_model: Optional[str] = None


# Hardware schemas
class HardwareInfo(BaseModel):
    cpu: str
    cpu_cores: int
    ram_total_gb: float
    ram_used_gb: float
    ram_available_gb: float
    gpu_name: Optional[str] = None
    gpu_vendor: Optional[str] = None
    vram_total_gb: Optional[float] = None
    vram_used_gb: Optional[float] = None
    cuda_available: bool = False
    disk_total_gb: float
    disk_free_gb: float


# Job schemas
class JobResponse(BaseModel):
    id: UUID
    job_type: str
    status: str
    progress: float
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Audit schemas
class AuditEventResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: dict
    severity: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditFilter(BaseModel):
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    severity: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


# Sandbox schemas
class CodeExecutionRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30


class CodeExecutionResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    execution_time_ms: float
    files_generated: list[str] = []


# Generation schemas
class GenerationRequest(BaseModel):
    format: str  # docx, pptx, xlsx, pdf
    title: str
    content: str
    template: Optional[str] = None
    metadata: dict = {}


class GenerationResponse(BaseModel):
    file_id: str
    filename: str
    format: str
    file_size: int
    download_url: str

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Float,
    ForeignKey, JSON, Enum as SAEnum, BigInteger, TypeDecorator,
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class GUID(TypeDecorator):
    """Platform-independent UUID type. Uses String(36) for SQLite compatibility."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
        return value


def new_uuid():
    return uuid.uuid4()


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"
    PENDING = "pending"


class DocumentClassification(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    VALIDATED = "validated"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class CapabilityType(str, enum.Enum):
    GENERAL_REASONING = "general_reasoning"
    CODING = "coding"
    VISION = "vision"
    DOCUMENT_REASONING = "document_reasoning"
    FAST_CHAT = "fast_chat"
    EMBEDDING = "embedding"
    AUDIO_SPEECH = "audio_speech"


class Department(Base):
    __tablename__ = "departments"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="department")


class Role(Base):
    __tablename__ = "roles"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("User", back_populates="role")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    role_id = Column(GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission")


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    employee_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    email = Column(String(255))
    department_id = Column(GUID(), ForeignKey("departments.id"))
    designation = Column(String(100))
    role_id = Column(GUID(), ForeignKey("roles.id"), nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(SAEnum(UserStatus), default=UserStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)

    department = relationship("Department", back_populates="users")
    role = relationship("Role", back_populates="users")
    permissions = relationship("UserPermission", back_populates="user", cascade="all, delete-orphan")


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="permissions")
    permission = relationship("Permission")


class Document(Base):
    __tablename__ = "documents"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(BigInteger)
    file_path = Column(Text, nullable=False)
    classification = Column(SAEnum(DocumentClassification), default=DocumentClassification.INTERNAL)
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    department_id = Column(GUID(), ForeignKey("departments.id"))
    description = Column(Text)
    metadata_json = Column(JSON, default={})
    page_count = Column(Integer)
    is_ocr_processed = Column(Boolean, default=False)
    is_indexed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User")
    department = relationship("Department")
    permissions = relationship("DocumentPermission", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    document_id = Column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    role_id = Column(GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)
    department_id = Column(GUID(), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    can_read = Column(Boolean, default=True)
    can_download = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="permissions")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    document_id = Column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    section = Column(String(255))
    embedding_id = Column(String(100))
    # Embedding vector for this chunk, generated via the local Ollama
    # embedding model (e.g. nomic-embed-text) at indexing time. Stored as
    # a plain JSON array of floats rather than a dedicated vector-DB
    # column type, since the rest of this project deliberately stays on
    # SQLite/Postgres without adding a new datastore. Retrieval computes
    # cosine similarity against these in Python (see rag/service.py) -
    # this is real embedding-based semantic search, just without an ANN
    # index, which is the right tradeoff at this project's scale. Left
    # NULL for chunks indexed before an embedding model was available, or
    # for any chunk embedding generation fails on - those chunks fall
    # back to keyword search rather than being silently dropped.
    embedding = Column(JSON)
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")


class ModelRecord(Base):
    __tablename__ = "model_records"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    model_id = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    runtime = Column(String(50), nullable=False, default="ollama")
    provider = Column(String(50))
    local_identifier = Column(String(200), nullable=False)
    context_length = Column(Integer)
    parameter_size = Column(String(50))
    quantization = Column(String(20))
    vision_support = Column(Boolean, default=False)
    coding_support = Column(Boolean, default=False)
    reasoning_support = Column(Boolean, default=False)
    embedding_support = Column(Boolean, default=False)
    status = Column(SAEnum(ModelStatus), default=ModelStatus.DISCOVERED)
    hardware_requirements = Column(JSON, default={})
    priority = Column(Integer, default=50)
    enabled = Column(Boolean, default=False)
    last_health_check = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    capabilities = relationship("ModelCapability", back_populates="model", cascade="all, delete-orphan")


class ModelCapability(Base):
    __tablename__ = "model_capabilities"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    model_id = Column(GUID(), ForeignKey("model_records.id", ondelete="CASCADE"), nullable=False)
    capability = Column(SAEnum(CapabilityType), nullable=False)
    score = Column(Float, default=0.5)

    model = relationship("ModelRecord", back_populates="capabilities")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    job_type = Column(String(50), nullable=False)
    status = Column(SAEnum(JobStatus), default=JobStatus.QUEUED)
    progress = Column(Float, default=0.0)
    result = Column(JSON)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(100))
    details = Column(JSON, default={})
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    severity = Column(String(20), default="info")
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    event_type = Column(String(50), nullable=False)
    source = Column(String(100))
    destination = Column(String(255))
    action_taken = Column(String(50), nullable=False)
    details = Column(JSON, default={})
    severity = Column(String(20), default="warning")
    created_at = Column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User")


class SystemConfig(Base):
    """Key/value organisation settings, e.g. the Human-in-the-Loop toggle.
    Existed in database/schema.sql but had no ORM model or app code
    reading/writing it - the agentic HITL setting is the first real user."""
    __tablename__ = "system_config"

    key = Column(String(200), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(GUID(), ForeignKey("users.id"), nullable=True)


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(Base):
    """A Human-in-the-Loop approval request for a sensitive agent action.
    Created when HITL is enabled and the agent's planner classifies the
    requested action as sensitive; the original request is stored in
    `payload` so an authorized approver can resume execution unchanged."""
    __tablename__ = "approval_requests"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    requested_by = Column(GUID(), ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    reason = Column(Text)
    payload = Column(JSON, default={})
    status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    resolved_by = Column(GUID(), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime)
    result = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requested_by])
    resolver = relationship("User", foreign_keys=[resolved_by])


class GeneratedFile(Base):
    """Tracks every file the generation service writes to GENERATED_DIR -
    both from the manual /api/generation/generate endpoint and from the
    agent's new file_generation_node - so download access can be
    restricted to the owner (previously the download endpoint only
    checked that *some* user was logged in, not that it was the right
    one)."""
    __tablename__ = "generated_files"

    id = Column(GUID(), primary_key=True, default=new_uuid)
    filename = Column(String(500), nullable=False, unique=True)
    title = Column(String(500))
    format = Column(String(10))
    classification = Column(String(50), default="INTERNAL")
    size_bytes = Column(Integer)
    source = Column(String(20), default="manual")  # "manual" | "agent"
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")

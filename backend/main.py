import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_settings
from database import init_db, close_db
import models.orm  # noqa: F401 - ensure all ORM models are registered before init_db
from agents.checkpointer import init_checkpointer, close_checkpointer
from agents.graph import compile_graph

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Sovereign AI Workbench", version=settings.APP_VERSION)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.GENERATED_DIR, exist_ok=True)
    await init_db()
    checkpointer = await init_checkpointer()
    compile_graph(checkpointer)
    yield
    await close_db()
    await close_checkpointer()
    logger.info("Sovereign AI Workbench stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Self-hosted, air-gapped AI workbench for sovereign organizations",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}"
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


from auth.router import router as auth_router
from users.router import router as users_router
from roles.router import router as roles_router
from documents.router import router as documents_router
from knowledge.router import router as knowledge_router
from rag.router import router as rag_router
from models.router import router as models_router
from routing.router import router as routing_router
from agents.router import router as agents_router
from tools.router import router as tools_router
from sandbox.router import router as sandbox_router
from generation.router import router as generation_router
from hardware.router import router as hardware_router
from audit.router import router as audit_router
from security.router import router as security_router
from network.router import router as network_router
from audio.router import router as audio_router

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(roles_router, prefix="/api/roles", tags=["Roles"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["Knowledge Base"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(models_router, prefix="/api/models", tags=["Models"])
app.include_router(routing_router, prefix="/api/routing", tags=["Model Routing"])
app.include_router(agents_router, prefix="/api/agents", tags=["Agents"])
app.include_router(tools_router, prefix="/api/tools", tags=["Tools"])
app.include_router(sandbox_router, prefix="/api/sandbox", tags=["Sandbox"])
app.include_router(generation_router, prefix="/api/generation", tags=["File Generation"])
app.include_router(hardware_router, prefix="/api/hardware", tags=["Hardware"])
app.include_router(audit_router, prefix="/api/audit", tags=["Audit"])
app.include_router(security_router, prefix="/api/security", tags=["Security"])
app.include_router(network_router, prefix="/api/network", tags=["Network/Sovereignty"])
app.include_router(audio_router, prefix="/api/audio", tags=["Audio Transcription"])


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "air_gapped": settings.AIR_GAPPED_MODE,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "recovery": "Please try again or contact administrator"},
    )

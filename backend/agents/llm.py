"""LangChain integration layer.

Scope, per the integration brief: LangChain is used for structured LLM
interaction (ChatOllama) and standardized tool definitions - it is NOT
a second RAG/permission system. Every tool defined here wraps a service
that has *already* had its authorization decided elsewhere (RAGService's
own SQL-level filtering, or the LangGraph permission_gate node that runs
before any of these tools can be reached) - these tools never do their
own access-control, they just execute the already-authorized action.
"""
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from config import get_settings

settings = get_settings()


def get_chat_model(model_id: str, temperature: float = 0.3) -> ChatOllama:
    """Structured LangChain chat model bound to this org's own local
    Ollama runtime - never a hosted/cloud provider (AIR_GAPPED_MODE)."""
    return ChatOllama(model=model_id, base_url=settings.OLLAMA_URL, temperature=temperature)


# ---------------------------------------------------------------------
# Tool schemas + wrappers
# ---------------------------------------------------------------------
class SandboxToolInput(BaseModel):
    code: str = Field(description="The source code to execute")
    language: str = Field(default="python", description="python, javascript, or bash")


def make_sandbox_tool(sandbox) -> StructuredTool:
    """Wraps the EXISTING SandboxExecutor - only ever invoked after the
    graph's permission_gate + hitl_gate nodes have already cleared this
    specific request. This tool performs no authorization of its own."""

    async def _run(code: str, language: str = "python") -> dict:
        return await sandbox.execute(code, language)

    return StructuredTool.from_function(
        coroutine=_run,
        name="execute_code_sandbox",
        description=(
            "Execute code in the existing isolated sandbox and return the REAL "
            "stdout/stderr. Use this before explaining a bug - never guess at "
            "what an error would be."
        ),
        args_schema=SandboxToolInput,
    )


class FileGenerationToolInput(BaseModel):
    title: str = Field(description="A short, clear title for the document")
    content: str = Field(description="The full drafted body content of the document")
    format: str = Field(description="One of: docx, pdf, xlsx, pptx")


def make_file_generation_tool(generator) -> StructuredTool:
    """Wraps the EXISTING FileGenerator service - only ever invoked after
    the graph's permission_gate + hitl_gate nodes have already cleared
    this request. Writes a real file to GENERATED_DIR; never fabricates
    a filename without the file actually existing."""

    async def _run(title: str, content: str, format: str) -> str:
        return await generator.generate(title=title, content=content, format=format, classification="INTERNAL")

    return StructuredTool.from_function(
        coroutine=_run,
        name="generate_document_file",
        description="Create a real DOCX, PDF, XLSX, or PPTX file on disk from drafted title/content. Returns the file path.",
        args_schema=FileGenerationToolInput,
    )
    query: str = Field(description="The question to search the knowledge base for")


def make_rag_tool(rag_service) -> StructuredTool:
    """Wraps the EXISTING RAGService.get_context - authorization (which
    documents this user may see) is enforced inside RAGService's own SQL
    query, exactly as everywhere else in the app. This tool cannot see or
    return anything outside that filter."""

    async def _run(query: str) -> dict:
        result = await rag_service.get_context(query)
        return {
            "context": result.get("context", ""),
            "sources_found": len(result.get("citations", [])),
        }

    return StructuredTool.from_function(
        coroutine=_run,
        name="search_authorized_knowledge_base",
        description=(
            "Search the organization's document knowledge base. Only returns "
            "chunks the current user is already authorized to read."
        ),
        args_schema=RagToolInput,
    )

"""Lifecycle for the LangGraph checkpoint store.

An AsyncSqliteSaver backs the agent workflow graph so a paused
Human-in-the-Loop request (agents/graph.py's hitl_gate interrupt) can be
resumed correctly even if the app restarts while it's waiting - unlike an
in-memory checkpointer, which would silently lose the pause state on
restart. Opened once at app startup (see main.py's lifespan) and closed
at shutdown, matching how database.py manages the main SQLite connection.
"""
import os
from contextlib import AsyncExitStack
from typing import Optional

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config import get_settings

settings = get_settings()

_stack: Optional[AsyncExitStack] = None
_checkpointer: Optional[AsyncSqliteSaver] = None


async def init_checkpointer() -> AsyncSqliteSaver:
    global _stack, _checkpointer
    os.makedirs(os.path.dirname(settings.LANGGRAPH_CHECKPOINT_DB) or ".", exist_ok=True)
    _stack = AsyncExitStack()
    _checkpointer = await _stack.enter_async_context(
        AsyncSqliteSaver.from_conn_string(settings.LANGGRAPH_CHECKPOINT_DB)
    )
    return _checkpointer


async def close_checkpointer() -> None:
    global _stack, _checkpointer
    if _stack is not None:
        await _stack.aclose()
    _stack = None
    _checkpointer = None


def get_checkpointer() -> AsyncSqliteSaver:
    if _checkpointer is None:
        raise RuntimeError("LangGraph checkpointer not initialized - call init_checkpointer() at app startup")
    return _checkpointer

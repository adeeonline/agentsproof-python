from __future__ import annotations

from typing import Any, Callable, TypeVar

from .run import AgentRun

T = TypeVar("T")


def trace_llm(run: AgentRun, name: str, fn: Callable[[], T], input: Any = None) -> T:
    """Convenience wrapper for tracing a sync LLM call."""
    return run.trace("llm_call", name, fn, input)


def trace_tool(run: AgentRun, name: str, fn: Callable[[], T], input: Any = None) -> T:
    """Convenience wrapper for tracing a sync tool call."""
    return run.trace("tool_call", name, fn, input)


async def atrace_llm(run: AgentRun, name: str, fn: Callable[[], Any], input: Any = None) -> Any:
    """Convenience wrapper for tracing a sync or async LLM call."""
    return await run.atrace("llm_call", name, fn, input)


async def atrace_tool(run: AgentRun, name: str, fn: Callable[[], Any], input: Any = None) -> Any:
    """Convenience wrapper for tracing a sync or async tool call."""
    return await run.atrace("tool_call", name, fn, input)

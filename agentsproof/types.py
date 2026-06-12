from __future__ import annotations

from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional, Union

StepType = Literal["llm_call", "tool_call", "tool_result", "memory_read", "memory_write"]

# Using plain dicts with TypedDict for IDE support without runtime overhead
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict


class StepPayload(TypedDict, total=False):
    type: StepType
    name: str
    input: Any
    output: Any
    latency_ms: float
    token_count: int
    cost_usd: float


class GoldenCase(TypedDict, total=False):
    id: str
    name: str
    input: Any
    goal: str
    expected_output: Any
    expected_behavior: str
    success_criteria: List[str]
    trace_assertions: List[str]
    custom_grader_ids: List[str]


class ProofSuiteResult(TypedDict, total=False):
    passed_cases: int
    failed_cases: int
    overall_score: float
    public_url: str

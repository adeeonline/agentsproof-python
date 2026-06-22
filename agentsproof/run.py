from __future__ import annotations

import inspect
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TypeVar

import httpx

from .types import StepPayload, StepType

T = TypeVar("T")


def _get(obj: Any, key: str) -> Any:
    """Get a field from either a dict or an object attribute."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _sniff_usage(output: Any) -> Dict[str, Any]:
    """Best-effort extraction of token count from well-known LLM response shapes."""
    try:
        usage = _get(output, "usage") if output is not None else None
        if usage is None:
            return {}
        # Anthropic: input_tokens + output_tokens
        input_tokens = _get(usage, "input_tokens")
        output_tokens = _get(usage, "output_tokens")
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            return {"token_count": input_tokens + output_tokens}
        # OpenAI-compatible: total_tokens
        total_tokens = _get(usage, "total_tokens")
        if isinstance(total_tokens, int):
            return {"token_count": total_tokens}
        # OpenAI-compatible: prompt_tokens + completion_tokens
        prompt_tokens = _get(usage, "prompt_tokens")
        completion_tokens = _get(usage, "completion_tokens")
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return {"token_count": prompt_tokens + completion_tokens}
    except Exception:
        pass
    return {}


class AgentRun:
    def __init__(
        self,
        *,
        project_slug: str,
        api_key: str,
        base_url: str,
        input: Any = None,
        label: Optional[str] = None,
        golden_id: Optional[str] = None,
        goal: Optional[str] = None,
        expected_output: Any = None,
        expected_behavior: Optional[str] = None,
        success_criteria: Optional[list] = None,
        trace_assertions: Optional[list] = None,
        failure_modes: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self._api_key = api_key
        self._base_url = base_url
        self._steps: list = []
        self._started_at = time.monotonic()
        self._remote_run_id: Optional[str] = None

        self._init_remote(
            project_slug=project_slug,
            input=input,
            label=label,
            golden_id=golden_id,
            goal=goal,
            expected_output=expected_output,
            expected_behavior=expected_behavior,
            success_criteria=success_criteria,
            trace_assertions=trace_assertions,
            failure_modes=failure_modes,
            metadata=metadata or {},
        )

    def _init_remote(
        self,
        *,
        project_slug: str,
        input: Any,
        label: Optional[str],
        golden_id: Optional[str],
        goal: Optional[str],
        expected_output: Any,
        expected_behavior: Optional[str],
        success_criteria: Optional[list],
        trace_assertions: Optional[list],
        failure_modes: Optional[list],
        metadata: dict,
    ) -> None:
        with httpx.Client(follow_redirects=True) as client:
            res = client.post(
                f"{self._base_url}/runs",
                headers={"x-api-key": self._api_key},
                json={
                    "label": label,
                    "input": input,
                    "projectSlug": project_slug,
                    "clientRunId": self.run_id,
                    "goldenId": golden_id,
                    "goal": goal,
                    "expectedOutput": expected_output,
                    "expectedBehavior": expected_behavior,
                    "successCriteria": success_criteria,
                    "traceAssertions": trace_assertions,
                    "failureModes": failure_modes,
                    "metadata": metadata,
                },
                timeout=10,
            )
            res.raise_for_status()
            self._remote_run_id = res.json()["runId"]

    def log_step(self, payload: StepPayload) -> None:
        step = {
            **payload,
            "step_index": len(self._steps),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._steps.append(step)

        def _send() -> None:
            try:
                with httpx.Client(follow_redirects=True) as client:
                    client.post(
                        f"{self._base_url}/runs/{self._remote_run_id}/steps",
                        headers={"x-api-key": self._api_key},
                        json=step,
                        timeout=10,
                    )
            except Exception:
                pass  # SDK must never crash the agent

        threading.Thread(target=_send, daemon=True).start()

    def trace(
        self,
        type: StepType,
        name: str,
        fn: Callable[[], T],
        input: Any = None,
        extract: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ) -> T:
        """Wrap a sync callable and auto-log it as a step with latency captured.

        ``extract`` receives the return value of ``fn`` and should return a dict
        with optional keys ``token_count`` (int) and ``cost_usd`` (float). When
        omitted, the SDK attempts to detect usage from Anthropic / OpenAI-compatible
        response shapes automatically. Falls back to null if neither works.
        """
        t0 = time.monotonic()
        try:
            result = fn()
        except Exception as err:
            self.log_step({
                "type": type,
                "name": name,
                "input": input,
                "output": {"error": str(err)},
                "latency_ms": (time.monotonic() - t0) * 1000,
            })
            raise
        usage: Dict[str, Any] = {}
        if extract is not None:
            try:
                usage = extract(result) or {}
            except Exception:
                pass
        else:
            usage = _sniff_usage(result)
        self.log_step({
            "type": type,
            "name": name,
            "input": input,
            "output": result,
            "latency_ms": (time.monotonic() - t0) * 1000,
            **usage,
        })
        return result

    async def atrace(
        self,
        type: StepType,
        name: str,
        fn: Callable[[], Any],
        input: Any = None,
        extract: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ) -> Any:
        """Wrap a sync or async callable and auto-log it as a step. Use in async contexts.

        See ``trace()`` for docs on the ``extract`` parameter.
        """
        t0 = time.monotonic()
        try:
            result = await fn() if inspect.iscoroutinefunction(fn) else fn()
        except Exception as err:
            self.log_step({
                "type": type,
                "name": name,
                "input": input,
                "output": {"error": str(err)},
                "latency_ms": (time.monotonic() - t0) * 1000,
            })
            raise
        usage: Dict[str, Any] = {}
        if extract is not None:
            try:
                usage = extract(result) or {}
            except Exception:
                pass
        else:
            usage = _sniff_usage(result)
        self.log_step({
            "type": type,
            "name": name,
            "input": input,
            "output": result,
            "latency_ms": (time.monotonic() - t0) * 1000,
            **usage,
        })
        return result

    def complete(self, output: Any) -> dict:
        """Finish the run and trigger grading. Returns {"publicUrl": "..."}."""
        with httpx.Client(follow_redirects=True) as client:
            res = client.post(
                f"{self._base_url}/runs/{self._remote_run_id}/complete",
                headers={"x-api-key": self._api_key},
                json={"output": output},
                timeout=30,
            )
            res.raise_for_status()
            return res.json()

    async def acomplete(self, output: Any) -> dict:
        """Async version of complete()."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            res = await client.post(
                f"{self._base_url}/runs/{self._remote_run_id}/complete",
                headers={"x-api-key": self._api_key},
                json={"output": output},
                timeout=30,
            )
            res.raise_for_status()
            return res.json()

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._started_at) * 1000

    @property
    def remote_run_id(self) -> Optional[str]:
        return self._remote_run_id

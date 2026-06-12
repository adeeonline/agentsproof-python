from __future__ import annotations

import inspect
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

import httpx

from .types import StepPayload, StepType

T = TypeVar("T")


class AgentRun:
    def __init__(
        self,
        *,
        project_slug: str,
        input: Any,
        api_key: str,
        base_url: str,
        label: Optional[str] = None,
        goal: Optional[str] = None,
        expected_output: Any = None,
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
            goal=goal,
            expected_output=expected_output,
            metadata=metadata or {},
        )

    def _init_remote(
        self,
        *,
        project_slug: str,
        input: Any,
        label: Optional[str],
        goal: Optional[str],
        expected_output: Any,
        metadata: dict,
    ) -> None:
        with httpx.Client() as client:
            res = client.post(
                f"{self._base_url}/runs",
                headers={"x-api-key": self._api_key},
                json={
                    "label": label,
                    "input": input,
                    "projectSlug": project_slug,
                    "clientRunId": self.run_id,
                    "goal": goal,
                    "expectedOutput": expected_output,
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
                with httpx.Client() as client:
                    client.post(
                        f"{self._base_url}/runs/{self._remote_run_id}/steps",
                        headers={"x-api-key": self._api_key},
                        json=step,
                        timeout=10,
                    )
            except Exception:
                pass  # SDK must never crash the agent

        threading.Thread(target=_send, daemon=True).start()

    def trace(self, type: StepType, name: str, fn: Callable[[], T], input: Any = None) -> T:
        """Wrap a sync callable and auto-log it as a step with latency captured."""
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
        self.log_step({
            "type": type,
            "name": name,
            "input": input,
            "output": result,
            "latency_ms": (time.monotonic() - t0) * 1000,
        })
        return result

    async def atrace(self, type: StepType, name: str, fn: Callable[[], Any], input: Any = None) -> Any:
        """Wrap a sync or async callable and auto-log it as a step. Use in async contexts."""
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
        self.log_step({
            "type": type,
            "name": name,
            "input": input,
            "output": result,
            "latency_ms": (time.monotonic() - t0) * 1000,
        })
        return result

    def complete(self, output: Any) -> dict:
        """Finish the run and trigger grading. Returns {"publicUrl": "..."}."""
        with httpx.Client() as client:
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
        async with httpx.AsyncClient() as client:
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

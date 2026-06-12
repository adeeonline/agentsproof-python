from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

import httpx

from .run import AgentRun
from .types import GoldenCase, ProofSuiteResult


def run_proof_suite(
    *,
    project_slug: str,
    suite_slug: str,
    handler: Callable[[Any, Any], Any],
    api_key: str,
    base_url: str,
) -> ProofSuiteResult:
    """Sync version. handler(input, ctx) must be a regular (non-async) function."""
    with httpx.Client() as client:
        res = client.get(
            f"{base_url}/proof-suites/{suite_slug}/cases",
            params={"projectSlug": project_slug},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        if not res.is_success:
            raise RuntimeError(f"AgentsProof: failed to load proof suite — {res.status_code}")
        data = res.json()

    proof_run_id: str = data["proofRunId"]
    cases: list[GoldenCase] = data["cases"]

    for golden in cases:
        run_id: Optional[str] = None
        passed = False
        failure_summary: Optional[str] = None
        handler_run: Optional[AgentRun] = None

        def start_run(**overrides: Any) -> AgentRun:
            nonlocal handler_run
            r = AgentRun(
                project_slug=project_slug,
                label=overrides.get("label", f"Proof case: {golden.get('name', '')}"),
                input=overrides.get("input", golden.get("input")),
                goal=overrides.get("goal", golden.get("goal")),
                expected_output=overrides.get("expected_output", golden.get("expected_output")),
                metadata={**overrides.get("metadata", {}), "goldenId": golden["id"], "proofRunId": proof_run_id},
                api_key=api_key,
                base_url=base_url,
            )
            handler_run = r
            return r

        class Ctx:
            golden_case = golden

            @staticmethod
            def start_run(**overrides: Any) -> AgentRun:
                return start_run(**overrides)

        try:
            handler(golden.get("input"), Ctx)
            if handler_run is not None:
                run_id = handler_run.remote_run_id
            passed = True
        except Exception as err:
            failure_summary = str(err)

        try:
            with httpx.Client() as client:
                client.post(
                    f"{base_url}/proof-runs/{proof_run_id}/case-results",
                    headers={"x-api-key": api_key},
                    json={
                        "goldenId": golden["id"],
                        "runId": run_id,
                        "score": None,
                        "passed": passed,
                        "failureSummary": failure_summary,
                    },
                    timeout=10,
                )
        except Exception:
            pass

    with httpx.Client() as client:
        res = client.post(
            f"{base_url}/proof-runs/{proof_run_id}/complete",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        if not res.is_success:
            raise RuntimeError(f"AgentsProof: failed to complete proof suite — {res.status_code}")
        return res.json()


async def arun_proof_suite(
    *,
    project_slug: str,
    suite_slug: str,
    handler: Callable[[Any, Any], Any],
    api_key: str,
    base_url: str,
) -> ProofSuiteResult:
    """Async version. handler(input, ctx) can be sync or async."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{base_url}/proof-suites/{suite_slug}/cases",
            params={"projectSlug": project_slug},
            headers={"x-api-key": api_key},
            timeout=15,
        )
        if not res.is_success:
            raise RuntimeError(f"AgentsProof: failed to load proof suite — {res.status_code}")
        data = res.json()

    proof_run_id: str = data["proofRunId"]
    cases: list[GoldenCase] = data["cases"]

    for golden in cases:
        run_id: Optional[str] = None
        passed = False
        failure_summary: Optional[str] = None
        handler_run: Optional[AgentRun] = None

        def start_run(**overrides: Any) -> AgentRun:
            nonlocal handler_run
            r = AgentRun(
                project_slug=project_slug,
                label=overrides.get("label", f"Proof case: {golden.get('name', '')}"),
                input=overrides.get("input", golden.get("input")),
                goal=overrides.get("goal", golden.get("goal")),
                expected_output=overrides.get("expected_output", golden.get("expected_output")),
                metadata={**overrides.get("metadata", {}), "goldenId": golden["id"], "proofRunId": proof_run_id},
                api_key=api_key,
                base_url=base_url,
            )
            handler_run = r
            return r

        class Ctx:
            golden_case = golden

            @staticmethod
            def start_run(**overrides: Any) -> AgentRun:
                return start_run(**overrides)

        try:
            result = handler(golden.get("input"), Ctx)
            if inspect.iscoroutine(result):
                await result
            if handler_run is not None:
                run_id = handler_run.remote_run_id
            passed = True
        except Exception as err:
            failure_summary = str(err)

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{base_url}/proof-runs/{proof_run_id}/case-results",
                    headers={"x-api-key": api_key},
                    json={
                        "goldenId": golden["id"],
                        "runId": run_id,
                        "score": None,
                        "passed": passed,
                        "failureSummary": failure_summary,
                    },
                    timeout=10,
                )
        except Exception:
            pass

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{base_url}/proof-runs/{proof_run_id}/complete",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        if not res.is_success:
            raise RuntimeError(f"AgentsProof: failed to complete proof suite — {res.status_code}")
        return res.json()

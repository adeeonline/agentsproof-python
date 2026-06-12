from __future__ import annotations

from typing import Any, Callable, Optional

from .proof_suite import arun_proof_suite, run_proof_suite
from .run import AgentRun
from .types import ProofSuiteResult


class AgentsProof:
    def __init__(self, *, api_key: str, base_url: str = "https://agentsproof.dev/api") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def start_run(
        self,
        *,
        project_slug: str,
        input: Any,
        label: Optional[str] = None,
        goal: Optional[str] = None,
        expected_output: Any = None,
        metadata: Optional[dict] = None,
    ) -> AgentRun:
        return AgentRun(
            project_slug=project_slug,
            input=input,
            label=label,
            goal=goal,
            expected_output=expected_output,
            metadata=metadata,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    def run_proof_suite(
        self,
        *,
        project_slug: str,
        suite_slug: str,
        handler: Callable[[Any, Any], Any],
    ) -> ProofSuiteResult:
        """Run approved Goldens locally against your agent (sync). Handler must be a regular function."""
        return run_proof_suite(
            project_slug=project_slug,
            suite_slug=suite_slug,
            handler=handler,
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def arun_proof_suite(
        self,
        *,
        project_slug: str,
        suite_slug: str,
        handler: Callable[[Any, Any], Any],
    ) -> ProofSuiteResult:
        """Run approved Goldens locally against your agent (async). Handler can be sync or async."""
        return await arun_proof_suite(
            project_slug=project_slug,
            suite_slug=suite_slug,
            handler=handler,
            api_key=self._api_key,
            base_url=self._base_url,
        )

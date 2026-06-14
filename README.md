# agentsproof

Drop the SDK into your Python agent, define what "good" means, and get a shareable proof report.

## Install

```bash
pip install agentsproof
```

## Quick start — single run (sync)

Works with any Python agent — OpenAI, Anthropic, LangChain, LlamaIndex, or plain functions.

```python
import os
from agentsproof import AgentsProof

ap = AgentsProof(api_key=os.environ["AGENTSPROOF_API_KEY"])

def run_my_agent(user_query: str):
    run = ap.start_run(
        project_slug="my-coding-agent",
        label="Answer coding question",
        input={"query": user_query},
        goal="Search the web for relevant docs and return a working code solution",
    )

    # Wrap any callable — the SDK captures latency and output automatically
    plan = run.trace("llm_call", "gpt-4o", lambda: openai_call(user_query), input=user_query)

    results = run.trace("tool_call", "web_search", lambda: web_search(plan))

    final_answer = run.trace("llm_call", "gpt-4o", lambda: openai_call(results))

    result = run.complete({"answer": final_answer})
    print(f"Report: {result['publicUrl']}")
    # → https://agentsproof.dev/r/abc123
```

## Quick start — async agent

```python
import asyncio
import os
from agentsproof import AgentsProof

ap = AgentsProof(api_key=os.environ["AGENTSPROOF_API_KEY"])

async def run_my_agent(user_query: str):
    run = ap.start_run(
        project_slug="my-coding-agent",
        input={"query": user_query},
        goal="Return a working code solution",
    )

    # Use atrace() for async callables
    plan = await run.atrace("llm_call", "gpt-4o", lambda: async_openai_call(user_query))
    results = await run.atrace("tool_call", "web_search", lambda: async_web_search(plan))
    final_answer = await run.atrace("llm_call", "gpt-4o", lambda: async_openai_call(results))

    result = await run.acomplete({"answer": final_answer})
    print(f"Report: {result['publicUrl']}")

asyncio.run(run_my_agent("How do I reverse a list in Python?"))
```

## Proof Suites — regression testing

```python
import os
from agentsproof import AgentsProof

ap = AgentsProof(api_key=os.environ["AGENTSPROOF_API_KEY"])

def handler(input, ctx):
    run = ctx.start_run()
    result = my_agent(input)
    run.complete({"answer": result})

result = ap.run_proof_suite(
    project_slug="my-coding-agent",
    suite_slug="core-behaviors",
    handler=handler,
)
print(result)
# → {"passedCases": 17, "failedCases": 1, "overallScore": 0.91, "publicUrl": "..."}
```

### Async proof suite

```python
async def async_handler(input, ctx):
    run = ctx.start_run()
    result = await my_async_agent(input)
    await run.acomplete({"answer": result})

result = await ap.arun_proof_suite(
    project_slug="my-coding-agent",
    suite_slug="core-behaviors",
    handler=async_handler,
)
```

## API

### `AgentsProof(api_key, base_url?)`
Create a client. Get your API key from [agentsproof.dev](https://agentsproof.dev).

### `client.start_run(...)` → `AgentRun`

| Param | Type | Required | Description |
|---|---|---|---|
| `project_slug` | `str` | yes | Your project identifier |
| `input` | `Any` | yes | The initial input or prompt to the agent |
| `label` | `str` | no | Human-readable label for this run |
| `goal` | `str` | no | What this run should accomplish |
| `expected_output` | `Any` | no | Expected output for grading comparison |
| `metadata` | `dict` | no | Optional key/value metadata |

### `run.trace(type, name, fn, input?, extract?)` → `T`
Wrap a **sync** callable and auto-log it as a step with latency captured.

### `run.atrace(type, name, fn, input?, extract?)` → `Awaitable[T]`
Wrap a **sync or async** callable. Use in `async` agent code.

Token count and cost are captured automatically in priority order:

1. **`extract`** — your own callable, receives the step output, returns `{"token_count": int, "cost_usd": float}` (both optional).
2. **Auto-detection** — if no extractor is given, the SDK sniffs `output.usage` (or `output["usage"]`) for Anthropic (`input_tokens + output_tokens`) and OpenAI-compatible (`total_tokens` or `prompt_tokens + completion_tokens`) shapes.
3. **null** — if neither works, both fields are omitted from the step.

```python
# Anthropic / OpenAI — auto-detected, no extra code needed
result = run.trace("llm_call", "claude", lambda: anthropic_call(prompt))

# Any other provider — supply an extractor
result = run.trace(
    "llm_call", "my-model",
    lambda: call_my_llm(prompt),
    input=prompt,
    extract=lambda out: {"token_count": out.usage.tokens, "cost_usd": out.billed_usd},
)
```

### `run.log_step(payload)`
Manually log a step. Step types: `llm_call` | `tool_call` | `tool_result` | `memory_read` | `memory_write`.

### `run.complete(output)` → `{"publicUrl": str}`
Finish the run, trigger grading, and get back the public report URL.

### `run.acomplete(output)` → `Awaitable[{"publicUrl": str}]`
Async version of `complete()`.

### `client.run_proof_suite(...)` / `client.arun_proof_suite(...)`
Run approved Goldens locally against your agent. AgentsProof never executes user code remotely.

The SDK never raises on logging failures — steps are fire-and-forget so the SDK cannot crash your agent.

## Trace assertions

Each Golden can define `trace_assertions` in the dashboard — checked server-side after every proof run and displayed in the run's trace view.

**Structured assertions** are evaluated deterministically (no LLM involved):

| Pattern | What it checks |
|---|---|
| `must_call:tool_name` | At least one step must have `name == tool_name` |
| `must_not_call:tool_name` | No step may have `name == tool_name` |
| `max_steps:N` | Total step count must be ≤ N |
| `min_steps:N` | Total step count must be ≥ N |

**Free-text assertions** (anything not matching the patterns above) are passed to the LLM grader as extra criteria alongside `success_criteria`.

Set these in the dashboard when editing a Golden, one per line:
```
must_not_call:send_email
max_steps:10
Agent must ask for confirmation before any irreversible action
```

## How grading works

Each run is automatically scored on 5 axes:

| Axis | Weight | What it measures |
|---|---|---|
| Goal completion | 35% | Did the agent achieve the stated goal? |
| Output quality | 20% | Is the final output correct and complete? |
| Tool accuracy | 20% | Were tool calls well-formed and necessary? |
| Step efficiency | 15% | Did it avoid redundant steps or loops? |
| Safety | 10% | Did it avoid unsafe or off-policy actions? |

**Weights adjust automatically** — if your agent makes no tool calls, `tool_accuracy` weight is redistributed to `goal_completion` and `output_quality`.

**When the run is part of a Proof Suite**, the grader is also given the linked Golden's `success_criteria`, `expected_behavior`, and `failure_modes` as context, making scoring significantly more accurate. Structured `trace_assertions` are evaluated deterministically before the LLM runs. All results appear as a **Golden checks** panel in the trace view.

**Providing a `goal` always improves accuracy.** Without it, the judge infers intent from the raw input.

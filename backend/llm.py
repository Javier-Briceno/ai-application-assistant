"""
Unified LLM wrapper for Anthropic and OpenAI.
Every call is logged to job_application_assistant.llm_logs.
Structured calls validate output with Pydantic and retry on failure.
"""
import json
import time
from typing import Type, TypeVar

import anthropic
import asyncpg
import openai
from pydantic import BaseModel, ValidationError

from backend.config import settings

T = TypeVar("T", bound=BaseModel)

_anthropic = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
_openai = openai.AsyncOpenAI(api_key=settings.openai_api_key)


def _is_claude(model: str) -> bool:
    return model.startswith("claude")


async def _compute_cost(conn: asyncpg.Connection, model: str, in_tok: int, out_tok: int) -> float:
    row = await conn.fetchrow(
        "SELECT input_price, output_price FROM job_application_assistant.model_pricing WHERE model = $1",
        model,
    )
    if not row:
        return 0.0
    return (in_tok * float(row["input_price"]) + out_tok * float(row["output_price"])) / 1_000_000


async def _log(
    conn: asyncpg.Connection,
    *,
    model: str,
    node_name: str,
    profile_id: int | None,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    cost_usd: float,
) -> None:
    await conn.execute(
        """
        INSERT INTO job_application_assistant.llm_logs
            (model, node_name, profile_id, input_tokens, output_tokens, latency_ms, cost_usd)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        model,
        node_name,
        profile_id,
        input_tokens,
        output_tokens,
        latency_ms,
        cost_usd,
    )


async def log_call(
    conn: asyncpg.Connection,
    *,
    model: str,
    node_name: str,
    profile_id: int | None,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
) -> None:
    """Log a completed LLM call whose tokens and latency are already known.

    Use this for streaming calls where you capture usage from the final message
    event rather than from a blocking response object.
    """
    cost_usd = await _compute_cost(conn, model, input_tokens, output_tokens)
    await _log(
        conn,
        model=model,
        node_name=node_name,
        profile_id=profile_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


async def call_raw(
    conn: asyncpg.Connection,
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    node_name: str,
    profile_id: int | None = None,
) -> str:
    """Make a raw LLM call, log it, and return the text response."""
    start = time.monotonic()

    if _is_claude(model):
        resp = await _anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
    else:
        resp = await _openai.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = resp.choices[0].message.content or ""
        in_tok = resp.usage.prompt_tokens
        out_tok = resp.usage.completion_tokens

    latency_ms = int((time.monotonic() - start) * 1000)
    cost_usd = await _compute_cost(conn, model, in_tok, out_tok)

    await _log(
        conn,
        model=model,
        node_name=node_name,
        profile_id=profile_id,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )

    return text


def _strip_fences(text: str) -> str:
    """Strip markdown code fences that some models add around JSON."""
    t = text.strip()
    if t.startswith("```"):
        # Remove opening fence line
        t = t[t.index("\n") + 1:] if "\n" in t else t[3:]
        # Remove closing fence
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


async def call_structured(
    conn: asyncpg.Connection,
    *,
    model: str,
    system: str,
    user: str,
    response_model: Type[T],
    max_tokens: int = 4096,
    temperature: float = 0.0,
    node_name: str,
    profile_id: int | None = None,
    max_retries: int = 2,
) -> T:
    """
    Make a structured LLM call.
    Appends JSON schema to the user message, parses the response,
    validates with Pydantic, and retries up to max_retries on failure.
    """
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    schema_instruction = (
        f"\n\nRespond with ONLY a valid JSON object matching this schema — "
        f"no markdown, no explanation, raw JSON only:\n{schema}"
    )

    last_error: Exception | None = None
    current_user = user + schema_instruction

    for attempt in range(max_retries + 1):
        attempt_node = node_name if attempt == 0 else f"{node_name}_retry{attempt}"
        text = await call_raw(
            conn,
            model=model,
            system=system,
            user=current_user,
            max_tokens=max_tokens,
            temperature=temperature,
            node_name=attempt_node,
            profile_id=profile_id,
        )
        try:
            return response_model.model_validate_json(_strip_fences(text))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt < max_retries:
                current_user = (
                    user
                    + schema_instruction
                    + f"\n\nYour previous response failed validation: {exc}\n"
                    f"Fix the error and return valid JSON."
                )

    raise ValueError(
        f"LLM structured output failed after {max_retries + 1} attempt(s): {last_error}"
    )

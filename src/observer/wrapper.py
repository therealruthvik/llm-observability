"""LLM call wrappers that instrument every request with Prometheus metrics."""

import time
from typing import Any

from .cost_calculator import calculate_cost, context_utilization
from .metrics import (
    CONTEXT_UTILIZATION,
    COST_TOTAL,
    REQUEST_DURATION,
    REQUEST_TOTAL,
    TOKENS_TOTAL,
    update_cache_hit_rate,
)


def _record(
    provider: str,
    model: str,
    agent_id: str,
    user_id: str,
    duration: float,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    status: str,
) -> None:
    REQUEST_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id, status=status
    ).inc()

    REQUEST_DURATION.labels(provider=provider, model=model, agent_id=agent_id).observe(duration)

    TOKENS_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id, token_type="input"
    ).inc(input_tokens)
    TOKENS_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id, token_type="output"
    ).inc(output_tokens)
    TOKENS_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id, token_type="cache_read"
    ).inc(cache_read_tokens)
    TOKENS_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id, token_type="cache_write"
    ).inc(cache_write_tokens)

    cost = calculate_cost(
        provider, model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
    )
    COST_TOTAL.labels(
        provider=provider, model=model, agent_id=agent_id, user_id=user_id
    ).inc(cost)

    had_cache_hit = cache_read_tokens > 0
    update_cache_hit_rate(provider, model, agent_id, had_cache_hit)

    total_tokens = input_tokens + output_tokens
    util = context_utilization(provider, model, total_tokens)
    CONTEXT_UTILIZATION.labels(provider=provider, model=model, agent_id=agent_id).set(util)


async def observed_anthropic_call(
    client: Any,
    agent_id: str,
    user_id: str,
    **kwargs: Any,
) -> Any:
    model = kwargs.get("model", "unknown")
    start = time.perf_counter()
    status = "success"
    try:
        response = await client.messages.create(**kwargs)
        duration = time.perf_counter() - start
        u = response.usage
        _record(
            provider="anthropic",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=getattr(u, "input_tokens", 0),
            output_tokens=getattr(u, "output_tokens", 0),
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0),
            status=status,
        )
        return response
    except Exception:
        duration = time.perf_counter() - start
        status = "error"
        _record(
            provider="anthropic",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            status=status,
        )
        raise


async def observed_openai_call(
    client: Any,
    agent_id: str,
    user_id: str,
    **kwargs: Any,
) -> Any:
    model = kwargs.get("model", "unknown")
    start = time.perf_counter()
    status = "success"
    try:
        response = await client.chat.completions.create(**kwargs)
        duration = time.perf_counter() - start
        u = response.usage
        prompt_tokens = getattr(u, "prompt_tokens", 0)
        completion_tokens = getattr(u, "completion_tokens", 0)
        details = getattr(u, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details else 0
        _record(
            provider="openai",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_read_tokens=cached,
            cache_write_tokens=0,
            status=status,
        )
        return response
    except Exception:
        duration = time.perf_counter() - start
        status = "error"
        _record(
            provider="openai",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            status=status,
        )
        raise


async def observed_gemini_call(
    client: Any,
    agent_id: str,
    user_id: str,
    model: str,
    prompt: str,
    **kwargs: Any,
) -> Any:
    start = time.perf_counter()
    status = "success"
    try:
        response = await client.aio.models.generate_content(model=model, contents=prompt, **kwargs)
        duration = time.perf_counter() - start
        meta = getattr(response, "usage_metadata", None)
        input_tokens = getattr(meta, "prompt_token_count", 0) if meta else 0
        output_tokens = getattr(meta, "candidates_token_count", 0) if meta else 0
        cached = getattr(meta, "cached_content_token_count", 0) if meta else 0
        _record(
            provider="google",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached,
            cache_write_tokens=0,
            status=status,
        )
        return response
    except Exception:
        duration = time.perf_counter() - start
        status = "error"
        _record(
            provider="google",
            model=model,
            agent_id=agent_id,
            user_id=user_id,
            duration=duration,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
            status=status,
        )
        raise

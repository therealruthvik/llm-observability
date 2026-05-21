"""Realistic metric simulation — no real API calls, full Prometheus instrumentation."""

import asyncio
import random
import time

from src.observer.metrics import (
    CONTEXT_UTILIZATION,
    COST_TOTAL,
    REQUEST_DURATION,
    REQUEST_TOTAL,
    TOKENS_TOTAL,
    update_cache_hit_rate,
)
from src.observer.cost_calculator import calculate_cost, context_utilization

_PROFILES = [
    {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "agent_id": "research_agent",
        "input_range": (2000, 8000),
        "output_range": (400, 1200),
        "cache_hit_prob": 0.55,
        "cache_tokens_range": (800, 3000),
        "latency_range": (2.5, 9.0),
        "error_prob": 0.02,
    },
    {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "agent_id": "summary_agent",
        "input_range": (500, 2000),
        "output_range": (80, 300),
        "cache_hit_prob": 0.20,
        "cache_tokens_range": (100, 500),
        "latency_range": (0.8, 3.5),
        "error_prob": 0.015,
    },
    {
        "provider": "google",
        "model": "gemini-1.5-flash",
        "agent_id": "code_agent",
        "input_range": (800, 3000),
        "output_range": (200, 800),
        "cache_hit_prob": 0.15,
        "cache_tokens_range": (50, 300),
        "latency_range": (1.0, 5.0),
        "error_prob": 0.025,
    },
    {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "agent_id": "triage_agent",
        "input_range": (300, 1500),
        "output_range": (50, 400),
        "cache_hit_prob": 0.40,
        "cache_tokens_range": (200, 800),
        "latency_range": (0.5, 2.5),
        "error_prob": 0.01,
    },
    {
        "provider": "openai",
        "model": "gpt-4o",
        "agent_id": "analysis_agent",
        "input_range": (3000, 10000),
        "output_range": (500, 2000),
        "cache_hit_prob": 0.30,
        "cache_tokens_range": (500, 2000),
        "latency_range": (3.0, 12.0),
        "error_prob": 0.02,
    },
]

_USERS = ["user_alice", "user_bob", "user_carol", "user_dave", "user_eve"]


def _simulate_one(user_id: str | None = None, force_error: bool = False) -> dict:
    profile = random.choice(_PROFILES)
    uid = user_id or random.choice(_USERS)

    is_error = force_error or random.random() < profile["error_prob"]
    status = "error" if is_error else "success"

    latency = random.uniform(*profile["latency_range"])
    if is_error:
        latency *= 0.3

    input_tokens = random.randint(*profile["input_range"]) if not is_error else 0
    output_tokens = random.randint(*profile["output_range"]) if not is_error else 0
    cache_hit = (not is_error) and random.random() < profile["cache_hit_prob"]
    cache_read = random.randint(*profile["cache_tokens_range"]) if cache_hit else 0
    cache_write = random.randint(100, 500) if (not is_error and not cache_hit and random.random() < 0.3) else 0

    REQUEST_TOTAL.labels(
        provider=profile["provider"],
        model=profile["model"],
        agent_id=profile["agent_id"],
        user_id=uid,
        status=status,
    ).inc()

    REQUEST_DURATION.labels(
        provider=profile["provider"],
        model=profile["model"],
        agent_id=profile["agent_id"],
    ).observe(latency)

    if not is_error:
        for ttype, count in [
            ("input", input_tokens),
            ("output", output_tokens),
            ("cache_read", cache_read),
            ("cache_write", cache_write),
        ]:
            TOKENS_TOTAL.labels(
                provider=profile["provider"],
                model=profile["model"],
                agent_id=profile["agent_id"],
                user_id=uid,
                token_type=ttype,
            ).inc(count)

        cost = calculate_cost(
            profile["provider"], profile["model"],
            input_tokens, output_tokens, cache_write, cache_read,
        )
        COST_TOTAL.labels(
            provider=profile["provider"],
            model=profile["model"],
            agent_id=profile["agent_id"],
            user_id=uid,
        ).inc(cost)

        update_cache_hit_rate(profile["provider"], profile["model"], profile["agent_id"], cache_hit)

        util = context_utilization(profile["provider"], profile["model"], input_tokens + output_tokens)
        CONTEXT_UTILIZATION.labels(
            provider=profile["provider"],
            model=profile["model"],
            agent_id=profile["agent_id"],
        ).set(util)

    return {
        "provider": profile["provider"],
        "model": profile["model"],
        "agent_id": profile["agent_id"],
        "user_id": uid,
        "status": status,
        "latency_s": round(latency, 3),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
    }


async def simulate_batch(count: int = 1, user_id: str | None = None, force_error: bool = False) -> list[dict]:
    loop = asyncio.get_event_loop()
    results = []
    for _ in range(count):
        result = await loop.run_in_executor(None, _simulate_one, user_id, force_error)
        results.append(result)
        await asyncio.sleep(random.uniform(0.01, 0.05))
    return results

"""Cost per 1M tokens in USD. Verified 2026-05."""

CONTEXT_WINDOWS: dict[str, dict[str, int]] = {
    "anthropic": {
        "claude-sonnet-4-6": 200_000,
        "claude-opus-4-7": 200_000,
        "claude-haiku-4-5-20251001": 200_000,
    },
    "openai": {
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
    },
    "google": {
        "gemini-1.5-pro": 1_000_000,
        "gemini-1.5-flash": 1_000_000,
        "gemini-2.0-flash": 1_000_000,
    },
}

_COST_TABLE: dict[str, dict[str, dict[str, float]]] = {
    "anthropic": {
        "claude-sonnet-4-6": {
            "input": 3.0,
            "output": 15.0,
            "cache_write": 3.75,
            "cache_read": 0.30,
        },
        "claude-opus-4-7": {
            "input": 15.0,
            "output": 75.0,
            "cache_write": 18.75,
            "cache_read": 1.50,
        },
        "claude-haiku-4-5-20251001": {
            "input": 0.80,
            "output": 4.0,
            "cache_write": 1.0,
            "cache_read": 0.08,
        },
    },
    "openai": {
        "gpt-4o": {
            "input": 2.50,
            "output": 10.0,
            "cache_read": 1.25,
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60,
            "cache_read": 0.075,
        },
    },
    "google": {
        "gemini-1.5-pro": {
            "input": 1.25,
            "output": 5.0,
            "cache_read": 0.3125,
        },
        "gemini-1.5-flash": {
            "input": 0.075,
            "output": 0.30,
            "cache_read": 0.01875,
        },
        "gemini-2.0-flash": {
            "input": 0.10,
            "output": 0.40,
            "cache_read": 0.025,
        },
    },
}


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    rates = _COST_TABLE.get(provider, {}).get(model)
    if not rates:
        return 0.0

    billable_input = max(0, input_tokens - cache_read_tokens)
    cost = (
        billable_input * rates.get("input", 0.0)
        + output_tokens * rates.get("output", 0.0)
        + cache_write_tokens * rates.get("cache_write", 0.0)
        + cache_read_tokens * rates.get("cache_read", 0.0)
    ) / 1_000_000

    return round(cost, 8)


def context_utilization(provider: str, model: str, total_tokens: int) -> float:
    window = CONTEXT_WINDOWS.get(provider, {}).get(model, 0)
    if window == 0:
        return 0.0
    return min(1.0, total_tokens / window)

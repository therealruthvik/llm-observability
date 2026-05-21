from prometheus_client import Counter, Histogram, Gauge, REGISTRY

REQUEST_TOTAL = Counter(
    "llm_requests_total",
    "Total LLM API calls",
    ["provider", "model", "agent_id", "user_id", "status"],
)

TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total tokens consumed",
    ["provider", "model", "agent_id", "user_id", "token_type"],
)

COST_TOTAL = Counter(
    "llm_cost_dollars_total",
    "Total cost in USD",
    ["provider", "model", "agent_id", "user_id"],
)

REQUEST_DURATION = Histogram(
    "llm_request_duration_seconds",
    "LLM API call latency",
    ["provider", "model", "agent_id"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

CACHE_HIT_RATE = Gauge(
    "llm_cache_hit_rate",
    "Prompt cache hit rate (0-1) per agent",
    ["provider", "model", "agent_id"],
)

CONTEXT_UTILIZATION = Gauge(
    "llm_context_window_utilization_ratio",
    "Fraction of context window used (0-1)",
    ["provider", "model", "agent_id"],
)

_cache_call_counts: dict[str, int] = {}
_cache_hit_counts: dict[str, int] = {}


def update_cache_hit_rate(provider: str, model: str, agent_id: str, had_cache_hit: bool) -> None:
    key = f"{provider}:{model}:{agent_id}"
    _cache_call_counts[key] = _cache_call_counts.get(key, 0) + 1
    if had_cache_hit:
        _cache_hit_counts[key] = _cache_hit_counts.get(key, 0) + 1
    rate = _cache_hit_counts.get(key, 0) / _cache_call_counts[key]
    CACHE_HIT_RATE.labels(provider=provider, model=model, agent_id=agent_id).set(rate)

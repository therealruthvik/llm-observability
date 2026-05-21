# LLM Observability & Cost Intelligence Dashboard

Production-grade observability for multi-provider LLM systems. Instruments every API call across Anthropic, OpenAI, and Google Gemini with per-call token counts, latency, cost attribution, and prompt cache hit tracking — all visualized in a live Grafana dashboard with AlertManager-backed anomaly alerts.

![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Prometheus%20%7C%20Grafana%20%7C%20AlertManager-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it tracks

| Metric | Detail |
|--------|--------|
| Token counts | Input, output, cache read, cache write — per call |
| Cost | USD per call, per agent, per user, per model |
| Latency | p50 / p95 / p99 histograms per provider and model |
| Cache hit rate | Rolling prompt cache efficiency per agent |
| Context utilization | Fraction of context window consumed per call |
| Error rate | Per provider, model, agent |

All metrics carry `provider`, `model`, `agent_id`, and `user_id` labels — enabling per-user cost chargeback and per-agent efficiency analysis.

---

## Architecture

```
Locust / curl
     │
     ▼
FastAPI app (:8000)
  ├── /simulate        — zero-cost metric generation (no real API calls)
  ├── /run-pipeline    — real 3-agent pipeline (Claude → GPT → Gemini)
  ├── /run-demo        — concurrent real pipelines
  └── /metrics         — Prometheus scrape endpoint
     │
     ▼
Prometheus (:9090)  ──→  AlertManager (:9093)
     │
     ▼
Grafana (:3000)
```

**Agent pipeline (real API mode):**
```
ResearchAgent (Claude Sonnet) → SummaryAgent (GPT-4o-mini) → CodeAgent (Gemini Flash)
```

---

## Quick start

```bash
git clone https://github.com/therealruthvik/llm-observability
cd llm-observability

cp .env.template .env
# Fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY

python preflight.py        # must pass before running
docker compose up -d
```

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / llmobs |
| Prometheus | http://localhost:9090 | — |
| AlertManager | http://localhost:9093 | — |
| API docs | http://localhost:8000/docs | — |

---

## Generating metrics

### Simulation (no API keys needed)

```bash
# Single batch
curl -X POST "http://localhost:8000/simulate?count=10"

# Force errors to test alert pipeline
curl -X POST "http://localhost:8000/simulate?count=10&force_error=true"

# Pin to specific user
curl -X POST "http://localhost:8000/simulate?count=5&user_id=user_alice"
```

### Load test with Locust

```bash
pip install locust
locust --headless -u 50 -r 5 --run-time 5m --host http://localhost:8000
```

50 users, 5/s ramp — generates ~240 simulated LLM calls/second across all agents and users.

### Real API calls

```bash
curl -X POST "http://localhost:8000/run-pipeline?topic=transformer+attention&user_id=user_alice"

# Multiple concurrent pipelines
curl -X POST "http://localhost:8000/run-demo?concurrency=3"
```

---

## Dashboard panels

- **Stat row** — Total cost, total requests, p95 latency, cache hit rate, error rate, total tokens
- **Cost per Hour by Provider / Agent** — Time series burn rate (rate × 3600)
- **Token Consumption by Type** — Stacked area: input / output / cache read / cache write
- **Request Latency Percentiles** — p50, p95, p99 per model
- **Cost by User** — Bar chart for chargeback analysis
- **Cost by Model** — Donut chart breakdown
- **Context Window Utilization** — Gauge per agent (alerts at 85%)
- **Cost per Request (Anomaly View)** — Per-agent cost efficiency with 3× rolling baseline threshold overlay

---

## Alert rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| `LLMCostSpike` | 5m rate > 3× 1h baseline | warning |
| `LLMHighCostPerRequest` | cost/request > $0.05 | warning |
| `LLMHighErrorRate` | error rate > 10% for 2m | critical |
| `LLMHighLatency` | p95 > 30s for 2m | warning |
| `LLMContextWindowSaturation` | utilization > 85% | warning |

### Trigger an alert manually

```bash
# Lower threshold + force errors = fires in ~15s
# Edit prometheus/alert_rules.yml: change > 0.1 to > 0.001, for: 2m to for: 15s
curl -X POST http://localhost:9090/-/reload
curl -X POST "http://localhost:8000/simulate?count=10&force_error=true"
# Watch: http://localhost:9090/alerts
```

---

## Pre-deploy checklist

```bash
python preflight.py
```

Checks: syntax, dependency conflicts (scoped to project packages), key imports, env vars, deprecated model names, lazy client initialization, ignore file coverage.

---

## Project structure

```
├── src/
│   ├── observer/
│   │   ├── metrics.py          # Prometheus metric definitions
│   │   ├── cost_calculator.py  # Per-model cost tables (verified 2026-05)
│   │   └── wrapper.py          # observed_anthropic/openai/gemini_call()
│   ├── agents/
│   │   └── demo_agents.py      # ResearchAgent / SummaryAgent / CodeAgent
│   └── api/
│       ├── main.py             # FastAPI routes
│       └── simulator.py        # Realistic metric simulation, no API calls
├── prometheus/
│   ├── prometheus.yml
│   └── alert_rules.yml
├── alertmanager/
│   └── alertmanager.yml
├── grafana/provisioning/
│   ├── dashboards/llm_dashboard.json
│   └── datasources/prometheus.yaml
├── locustfile.py
├── preflight.py
├── docker-compose.yml
└── Dockerfile
```

---

## Cost model coverage

| Provider | Models |
|----------|--------|
| Anthropic | claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5 |
| OpenAI | gpt-4o, gpt-4o-mini |
| Google | gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash |

Cache read/write pricing tracked separately where supported (Anthropic prompt caching, OpenAI cached inputs).

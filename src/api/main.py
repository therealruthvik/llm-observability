import asyncio
import os
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.agents.demo_agents import run_pipeline
from src.api.simulator import simulate_batch

app = FastAPI(title="LLM Observability API", version="1.0.0")

DEMO_TOPICS = [
    "transformer attention mechanisms",
    "retrieval augmented generation",
    "LLM inference optimization",
    "vector database architectures",
    "multi-agent orchestration frameworks",
]

DEMO_USERS = ["user_alice", "user_bob", "user_carol", "user_dave"]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/run-pipeline")
async def run_single_pipeline(
    topic: Annotated[str, Query(description="Topic for the agent pipeline")],
    user_id: Annotated[str, Query(description="User identifier for cost attribution")],
) -> dict:
    try:
        result = await run_pipeline(topic=topic, user_id=user_id)
        return {"status": "success", "topic": topic, "user_id": user_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/simulate")
async def simulate(
    count: Annotated[int, Query(ge=1, le=20, description="Calls to simulate")] = 5,
    user_id: Annotated[str | None, Query(description="Pin to specific user")] = None,
    force_error: Annotated[bool, Query(description="Force all calls to error status")] = False,
) -> dict:
    results = await simulate_batch(count=count, user_id=user_id, force_error=force_error)
    return {"simulated": len(results), "calls": results}


@app.post("/run-demo")
async def run_demo(
    concurrency: Annotated[int, Query(ge=1, le=8, description="Parallel pipelines")] = 3,
) -> dict:
    """Run multiple concurrent pipelines across users to generate varied metric data."""
    import random

    tasks = [
        run_pipeline(
            topic=random.choice(DEMO_TOPICS),
            user_id=random.choice(DEMO_USERS),
        )
        for _ in range(concurrency)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = [r for r in results if not isinstance(r, Exception)]
    errors = [str(r) for r in results if isinstance(r, Exception)]

    return {
        "status": "completed",
        "total": concurrency,
        "succeeded": len(successes),
        "failed": len(errors),
        "errors": errors,
    }

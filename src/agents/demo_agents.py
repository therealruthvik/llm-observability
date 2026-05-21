"""Three-agent pipeline: ResearchAgent (Claude) → SummaryAgent (GPT) → CodeAgent (Gemini)."""

import os
from functools import lru_cache
from typing import Any

import anthropic
from google import genai
from openai import AsyncOpenAI

from src.observer.wrapper import (
    observed_anthropic_call,
    observed_gemini_call,
    observed_openai_call,
)

CLAUDE_MODEL = "claude-sonnet-4-6"
GPT_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-1.5-flash"

_SYSTEM_CONTEXT = (
    "You are an expert technical analyst. Be concise. Return structured output."
)


@lru_cache(maxsize=1)
def _anthropic_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@lru_cache(maxsize=1)
def _openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


@lru_cache(maxsize=1)
def _gemini_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GOOGLE_API_KEY"])


class ResearchAgent:
    """Uses Claude with prompt caching for long system context."""

    async def run(self, topic: str, user_id: str) -> str:
        response = await observed_anthropic_call(
            _anthropic_client(),
            agent_id="research_agent",
            user_id=user_id,
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_CONTEXT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Research and summarize key technical aspects of: {topic}. "
                    "Include recent developments, challenges, and opportunities. "
                    "Return JSON with keys: summary, challenges, opportunities.",
                }
            ],
        )
        return response.content[0].text


class SummaryAgent:
    """Uses GPT-4o-mini for cost-efficient summarization."""

    async def run(self, research: str, user_id: str) -> str:
        response = await observed_openai_call(
            _openai_client(),
            agent_id="summary_agent",
            user_id=user_id,
            model=GPT_MODEL,
            max_tokens=256,
            messages=[
                {
                    "role": "system",
                    "content": "Distill research into a crisp executive summary in ≤ 3 sentences.",
                },
                {"role": "user", "content": research},
            ],
        )
        return response.choices[0].message.content


class CodeAgent:
    """Uses Gemini for code generation based on research summary."""

    async def run(self, summary: str, user_id: str) -> str:
        prompt = (
            f"Based on this summary:\n{summary}\n\n"
            "Write a minimal Python proof-of-concept (≤ 30 lines) that demonstrates "
            "the most important technical concept. Include a docstring."
        )
        response = await observed_gemini_call(
            _gemini_client(),
            agent_id="code_agent",
            user_id=user_id,
            model=GEMINI_MODEL,
            prompt=prompt,
        )
        return response.text


async def run_pipeline(topic: str, user_id: str) -> dict[str, str]:
    research = await ResearchAgent().run(topic, user_id)
    summary = await SummaryAgent().run(research, user_id)
    code = await CodeAgent().run(summary, user_id)
    return {"research": research, "summary": summary, "code": code}

"""Shared Nebius LLM client for the Expat pipeline.

Both entry points (``streamlit/Home.py`` and ``loading/llm_earnings.py``)
construct their chat model here, so the provider, model id and token budget
live in exactly one place.

Nebius exposes an OpenAI-compatible API, so ``ChatOpenAI`` is used with an
explicit ``base_url`` rather than a bespoke client.
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

# Cheapest text model Nebius flags for both JSON mode and function calling.
# Override with NEBIUS_MODEL, e.g. deepseek-ai/DeepSeek-V4.1-Flash.
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"

DEFAULT_MAX_TOKENS = 5000


def load_env() -> None:
    """Load the repo-root .env.

    Resolved relative to this file rather than the working directory, so it works
    from streamlit/, from loading/, and from the repo root alike. Real environment
    variables win, which is what keeps Docker's --env-file authoritative.
    """
    load_dotenv(REPO_ROOT / ".env")


def build_chat_model(temperature: float = 0, max_tokens: int = DEFAULT_MAX_TOKENS):
    """Return a chat model pointed at Nebius.

    Reasoning is pinned off via ``extra_body``. DeepSeek reasons by default on
    this API, and ``reasoning_effort="low"`` is indistinguishable from the
    default, so there is no useful middle setting. Reasoning would also make the
    server ignore ``temperature``, costing us the determinism the earnings job
    depends on. Note DeepSeek's own ``thinking: {"type": "disabled"}`` form is
    silently ignored by Nebius - ``reasoning_effort`` is the knob that works.
    """
    load_env()

    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY is not set. Add it to .env (see .env.example)."
        )

    return ChatOpenAI(
        model=os.getenv("NEBIUS_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=None,
        max_retries=2,
        extra_body={"reasoning_effort": "none"},
    )


class CityEarnings(BaseModel):
    """One city's salary data for a given job."""

    city: str
    country: str
    currency: str
    jobtitle_and_experience: str
    average_monthly_gross_salary: float
    net_to_gross_salary_ratio: float


class CityEarningsList(BaseModel):
    cities: List[CityEarnings]


class CitySuggestion(BaseModel):
    """A city proposed by the LLM.

    Field names are load-bearing: these land in raw_config.cities, and
    clean__config_cities.sql selects `name` and `country` from it.
    """

    name: str
    country: Optional[str] = None
    description: Optional[str] = Field(
        default=None, description="Why this city fits the stated criteria."
    )


class CitySuggestionList(BaseModel):
    cities: List[CitySuggestion]

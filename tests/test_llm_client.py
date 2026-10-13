"""Tests for the Nebius client factory.

These cover configuration resolution without touching the network. The default
ChatOpenIC construction performs no I/O, so these stay fast and offline.
"""

import pytest

import llm_client


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test from a known-empty NEBIUS_* environment."""
    for var in ("NEBIUS_API_KEY", "NEBIUS_MODEL", "NEBIUS_BASE_URL"):
        monkeypatch.delenv(var, raising=False)


def test_missing_api_key_raises_a_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)  # no .env present

    with pytest.raises(RuntimeError, match="NEBIUS_API_KEY is not set"):
        llm_client.build_chat_model()


def test_defaults_when_only_the_key_is_set(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")

    model = llm_client.build_chat_model()

    assert model.model_name == llm_client.DEFAULT_MODEL
    assert "tokenfactory.nebius.com" in str(model.openai_api_base)


def test_env_overrides_are_honoured(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setenv("NEBIUS_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash")
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://example.invalid/v1")

    model = llm_client.build_chat_model()

    assert model.model_name == "deepseek-ai/DeepSeek-V4.1-Flash"
    assert "example.invalid" in str(model.openai_api_base)


def test_dotenv_supplies_the_key(monkeypatch, tmp_path):
    """A .env file is enough - no shell export required."""
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("NEBIUS_API_KEY=from-dotenv\n")
    monkeypatch.setenv("NEBIUS_MODEL", "sentinel")

    model = llm_client.build_chat_model()

    assert model.model_name == "sentinel"  # real env still wins over .env
    assert model.openai_api_key.get_secret_value() == "from-dotenv"


def test_real_environment_wins_over_dotenv(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("NEBIUS_API_KEY=from-dotenv\n")
    monkeypatch.setenv("NEBIUS_API_KEY", "from-environment")

    model = llm_client.build_chat_model()

    assert model.openai_api_key.get_secret_value() == "from-environment"


def test_reasoning_is_pinned_off(monkeypatch, tmp_path):
    """Thinking defaults on server-side and 'low' is indistinguishable from the
    default, so the request must explicitly carry reasoning_effort=none."""
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")

    model = llm_client.build_chat_model()

    assert model.extra_body == {"reasoning_effort": "none"}


def test_token_budget_defaults_to_5000(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_client, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")

    assert llm_client.build_chat_model().max_tokens == 5000
    assert llm_client.build_chat_model(max_tokens=900).max_tokens == 900


def test_earnings_schema_matches_the_dwh_primary_key():
    """job_earnings is keyed on city + jobtitle_and_experience; a rename here
    becomes a silent DuckDB write failure."""
    assert list(llm_client.CityEarnings.model_fields) == [
        "city",
        "country",
        "currency",
        "jobtitle_and_experience",
        "average_monthly_gross_salary",
        "net_to_gross_salary_ratio",
    ]

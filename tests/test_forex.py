"""Tests for the yahoo finance loader.

Two things used to go wrong here and both were silent:

- the ticker ran in the wrong direction, so the GBP rate was the reciprocal of
  the one the dbt models assume (they divide by it to reach EUR)
- a currency that yahoo refused to serve was dropped from the table, and dbt
  then dropped the cities that used it
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOADING = os.path.join(REPO_ROOT, "loading")


@pytest.fixture(scope="module")
def forex():
    os.environ.setdefault(
        "DUCKDB_LOCATION", os.path.join(REPO_ROOT, "database/dwh.duckdb")
    )
    # loading/utils.py and streamlit/utils.py share a module name, so whichever
    # directory comes first on sys.path wins.
    sys.path.insert(0, LOADING)
    sys.path.insert(1, REPO_ROOT)
    sys.modules.pop("utils", None)
    sys.modules.pop("forex", None)
    import forex as module

    return module


def test_ticker_quotes_the_foreign_currency_in_the_base(forex):
    """from_currency=GBP, to_currency=EUR needs GBPEUR=X, not EURGBP=X.

    EURGBP=X quotes GBP in EUR - the reciprocal - and dividing a GBP salary by
    it produces numbers that are wrong by the square of the real rate.
    """
    assert forex.build_ticker("EUR", "GBP") == "GBPEUR=X"
    assert forex.build_ticker("EUR", "JPY") == "JPYEUR=X"


def test_missing_currency_aborts_instead_of_writing_a_partial_table(forex, monkeypatch):
    monkeypatch.setattr(forex, "get_needed_currencies", lambda: ["GBP"])
    monkeypatch.setattr(forex, "get_forex_data", lambda base, foreign: None)
    monkeypatch.setattr(
        forex, "pipeline", type("P", (), {"run": staticmethod(lambda *a, **k: None)})()
    )

    with pytest.raises(RuntimeError, match="GBP"):
        forex.run_pipeline()


def test_eur_is_always_present(forex, monkeypatch):
    captured = {}
    monkeypatch.setattr(forex, "get_needed_currencies", lambda: [])
    monkeypatch.setattr(
        forex,
        "pipeline",
        type(
            "P",
            (),
            {"run": staticmethod(lambda data, **k: captured.setdefault("data", data))},
        )(),
    )

    forex.run_pipeline()

    rows = captured["data"]
    assert any(
        row["from_currency"] == "EUR" and row["to_currency"] == "EUR" for row in rows
    )

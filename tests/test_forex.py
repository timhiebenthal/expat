"""Tests for the yahoo finance loader.

Two things used to go wrong here and both were silent:

- the ticker ran in the wrong direction, so the GBP rate was the reciprocal of
  the one the dbt models assume (they divide by it to reach EUR)
- a currency that yahoo refused to serve was dropped from the table, and dbt
  then dropped the cities that used it

The logic under test lives in `pipeline/lib/forex.py`; `loading/forex.py` stays
as the dlt-era caller until cutover.
"""

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def forex():
    import pipeline.lib.forex as module

    return module


def test_ticker_quotes_the_foreign_currency_in_the_base(forex):
    """from_currency=GBP, to_currency=EUR needs GBPEUR=X, not EURGBP=X.

    EURGBP=X quotes GBP in EUR - the reciprocal - and dividing a GBP salary by
    it produces numbers that are wrong by the square of the real rate.
    """
    assert forex.build_ticker("EUR", "GBP") == "GBPEUR=X"
    assert forex.build_ticker("EUR", "JPY") == "JPYEUR=X"


def test_download_columns_are_flattened(forex):
    """yfinance hands back a MultiIndex column ('Close', 'GBPEUR=X').

    The ticker level is stripped and the names lowercased, so the frame ends up
    with plain open/high/low/close columns and the date moved out of the index
    where DuckDB can see it.
    """
    raw = pd.DataFrame(
        {"Open": [1.0], "Close": [0.85]},
        index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
    )
    raw.columns = pd.MultiIndex.from_product([["Open", "Close"], ["GBPEUR=X"]])

    flat = forex.flatten_download(raw)

    assert list(flat.columns) == ["date", "open", "close"]
    assert flat["close"].iloc[0] == 0.85


def test_the_eur_row_carries_the_same_keys_as_a_downloaded_row(forex):
    """The destination infers its schema from the first row, keyed by name.

    A sentinel whose keys or value types differ from the downloaded rows (EUR_ROW
    used lowercase, string dates and no volume) is written as nulls, which
    silently zeroed every EUR amount until the quality checks caught it.
    """
    raw = pd.DataFrame(
        {"Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [0.85], "Volume": [0]},
        index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
    )
    raw.columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["GBPEUR=X"]]
    )

    rows = forex.get_forex_data("EUR", "GBP", download=lambda *a, **k: raw)

    assert set(rows[0]) == set(forex.EUR_ROW), (set(rows[0]), set(forex.EUR_ROW))
    assert {k: type(v).__name__ for k, v in rows[0].items()} == {
        k: type(v).__name__ for k, v in forex.EUR_ROW.items()
    }


def test_missing_currency_aborts_instead_of_writing_a_partial_table(forex):
    with pytest.raises(RuntimeError, match="GBP"):
        forex.currency_rates(["GBP"], download=lambda *a, **k: pd.DataFrame())


def test_eur_is_always_present(forex):
    rows = forex.currency_rates([])

    assert any(
        row["from_currency"] == "EUR" and row["to_currency"] == "EUR" for row in rows
    )

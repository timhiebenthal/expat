"""Yahoo Finance FX rates, free of dlt and of network calls at import.

Two things here have silently broken before, so both are named functions with
their own tests: the ticker direction (Yahoo quotes one currency in another, and
getting it backwards squares the error) and the flattening of yfinance's
MultiIndex columns. `loading/forex.py` stays as the dlt-era entry point until
cutover and is not imported from here.
"""

import logging

import yfinance as yf

BASE_CURRENCY = "EUR"

# A currency with no rows must abort: the dbt models join the rate into the
# earnings and cost tables, so a missing rate silently drops every city that uses
# it. This sentinel guarantees EUR itself always has a row.
EUR_ROW = {
    "date": "2024-01-01",
    "open": 1.0,
    "high": 1.0,
    "low": 1.0,
    "close": 1.0,
    "from_currency": "EUR",
    "to_currency": "EUR",
}


def build_ticker(base_currency, foreign_currency):
    """Yahoo's <from><to>=X ticker quotes one <to> in <from>.

    The rows are stored as from_currency=<foreign>, to_currency=<base> and the
    dbt models divide by conversion_rate to reach EUR, so the ticker has to run
    in that same direction. 'EURGBP=X' quotes GBP in EUR - the reverse - and fed
    a rate that was wrong by the square of the real one.
    """
    return f"{foreign_currency}{base_currency}=X"


def flatten_download(frame):
    """Drop yfinance's MultiIndex ticker level and move the date out of the index.

    yfinance hands back columns like ('Close', 'GBPEUR=X'); the first level is
    the price and the second is the ticker, which is dropped so the frame carries
    plain open/high/low/close columns.
    """
    frame = frame.copy()
    frame.columns = [column[0] for column in frame.columns]
    return frame.reset_index()


def get_forex_data(
    base_currency, foreign_currency, download=None, start=None, end=None
):
    """Return the flattened rows for one pair, or None when yahoo serves none.

    ``download`` defaults to ``yf.download`` and is resolved at call time, so a
    test never reaches the network.
    """
    download = download or yf.download
    lookup_string = build_ticker(base_currency, foreign_currency)

    frame = download(lookup_string, start=start, end=end, progress=False)
    if len(frame) == 0:
        logging.error(f"No rows for {foreign_currency} into {base_currency}.")
        return None

    frame = flatten_download(frame)
    frame["from_currency"] = foreign_currency
    frame["to_currency"] = base_currency
    logging.info(
        f"Extracted {len(frame)} rows for {foreign_currency} into {base_currency}."
    )
    return frame.to_dict(orient="records")


def currency_rates(
    currencies, base_currency=BASE_CURRENCY, download=None, start=None, end=None
):
    """Fetch every currency, then insist they all came back before returning.

    dbt drops every city whose currency has no rate, so writing the table without
    them would quietly remove those cities from the dashboard.
    """
    data = []
    failed_currencies = []
    for foreign_currency in currencies:
        rows = get_forex_data(
            base_currency, foreign_currency, download=download, start=start, end=end
        )
        if rows:
            data.extend(rows)
        else:
            failed_currencies.append(foreign_currency)

    if failed_currencies:
        raise RuntimeError(
            f"No forex data for {', '.join(failed_currencies)}. "
            "Refusing to overwrite forex_daily - the cities would vanish downstream."
        )

    # Always make sure EUR has a rate, so the conversion join never misses.
    data.append(dict(EUR_ROW))
    return data

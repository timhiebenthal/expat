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
#
# Its keys and value types must match a downloaded row exactly: the destination
# infers its schema from the first row, so a row that differs lands as nulls.
EUR_ROW = {
    "date": "2024-01-01",
    "open": 1.0,
    "high": 1.0,
    "low": 1.0,
    "close": 1.0,
    "volume": 0,
    "from_currency": "EUR",
    "to_currency": "EUR",
}


def build_ticker(base_currency, foreign_currency):
    """Yahoo's <from><to>=X ticker quotes one <to> in <from>.

    The rows are stored as from_currency=<foreign>, to_currency=<base>, so this
    returns '<foreign><base>=X', whose close is <base> per one <foreign> - for
    GBP, GBPEUR=X, the EUR value of one pound. The core models multiply by it to
    reach EUR. 'EURGBP=X' is the reciprocal and would invert every amount
    (wrong by the square of the real rate).
    """
    return f"{foreign_currency}{base_currency}=X"


def flatten_download(frame):
    """Drop yfinance's MultiIndex ticker level, lowercase the names, move the date out.

    yfinance hands back columns like ('Close', 'GBPEUR=X'); the first level is
    the price and the second is the ticker, which is dropped. Names are
    lowercased both to match the shape dlt used to write and because the
    destination infers its schema from the first row: a row carrying
    differently-cased keys (the EUR sentinel did) lands as nulls, not values.
    """
    frame = frame.copy()
    frame.columns = [column[0] for column in frame.columns]
    frame = frame.reset_index()
    frame.columns = [str(column).lower() for column in frame.columns]
    return frame


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
    # One shape for every row: the destination infers its schema from the first
    # row, so the EUR sentinel below must match this exactly. An ISO string also
    # reproduces the VARCHAR date dlt used to write.
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
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

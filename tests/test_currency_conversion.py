"""The core models convert local amounts to EUR by MULTIPLYING the forex rate.

``conversion_rate`` is the close of Yahoo's ``<local><EUR>=X`` - the EUR value of
one unit of local currency (``GBPEUR=X`` ~ 1.155). The dbt models divided by it,
which inverted every non-euro amount and left it wrong by the square of the rate.
The bug shipped for a long time because nothing asserted the SQL arithmetic: the
Python loader under ``pipeline/lib/forex.py`` had tests, the models did not, and
the only guard was a frozen baseline that itself held the inverted value.

These tests execute the real asset SQL - raw through core - against a miniature
warehouse, so reintroducing the divide fails them rather than passing silently.
No network is touched.
"""

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "pipeline" / "assets"

# The fixture averages 1.15 and 1.16 into 1.155 EUR per GBP. A rate above 1 is
# the point: one pound buys more than one euro, so it is EUR-per-GBP and not its
# reciprocal. The reciprocal (0.866) is what an inverted ticker would store, and
# it is what would make the divide form look accidentally plausible.
GBP_RATE = 1.155

# raw -> clean -> prep -> core, in dependency order. Each entry is an asset path
# relative to pipeline/assets and the table its header declares.
CHAIN = [
    ("clean/config_cities.sql", "analytics.clean__config_cities"),
    ("clean/config_jobs.sql", "analytics.clean__config_jobs"),
    ("clean/job_earnings.sql", "analytics.clean__job_earnings"),
    ("clean/forex_forex_daily.sql", "analytics.clean__forex_forex_daily"),
    ("prep/avg_forex_rate.sql", "analytics.prep__avg_forex_rate"),
    ("prep/job_earnings.sql", "analytics.prep__job_earnings"),
    ("clean/numbeo_cost_of_living.sql", "analytics.clean__numbeo_cost_of_living"),
    ("prep/numbeo_cost_of_living.sql", "analytics.prep__numbeo_cost_of_living"),
    ("core/job_earnings.sql", "analytics.core__job_earnings"),
    ("core/cost_of_living.sql", "analytics.core__cost_of_living"),
]


def asset_sql(asset):
    """The SQL body of an asset, with its ``@bruin`` header stripped.

    The header is a block comment that closes with ``@bruin */``; everything
    after it is the query Bruin runs.
    """
    text = (ASSETS / asset).read_text()
    marker = "@bruin */"
    assert marker in text, f"{asset} has no closing @bruin marker"
    return text.split(marker, 1)[1]


def run_asset(con, asset, target):
    con.execute(f"create or replace table {target} as {asset_sql(asset)}")


def build_warehouse():
    """A miniature warehouse with the raw inputs the chain reads."""
    con = duckdb.connect()
    for schema in ("raw_config", "raw_earnings", "raw_numbeo", "raw_forex", "analytics"):
        con.execute(f"create schema {schema}")

    con.execute(
        "create table raw_config.cities as "
        "select * from (values ('London', 'United Kingdom'), ('Berlin', 'Germany')) "
        "t(name, country)"
    )
    con.execute(
        "create table raw_config.jobs as "
        "select * from (values ('Data Scientist', 5)) t(job_title, years_experience)"
    )

    # London is the non-euro case under test. Berlin is the EUR control: its rate
    # is 1.0, so its EUR amount must equal its local amount exactly.
    con.execute(
        "create table raw_earnings.job_earnings as "
        "select * from (values "
        "('London', 'United Kingdom', "
        " 'Data Scientist with 5 years of experience', "
        " 'GBP', 5000.0, 0.7), "
        "('Berlin', 'Germany', "
        " 'Data Scientist with 5 years of experience', "
        " 'EUR', 4000.0, 0.7)"
        ") t(city, country, jobtitle_and_experience, currency, "
        "    average_monthly_gross_salary, net_to_gross_salary_ratio)"
    )

    # cost_value is 10 GBP for a meal. Its activity has an activity_count of 12
    # in the seed, so the monthly cost is 120 GBP.
    con.execute(
        "create table raw_numbeo.cost_of_living as "
        "select 'London' city, 'Meal at an Inexpensive Restaurant' category, "
        "'10.00 £' as \"cost\""
    )

    # Two closes average to 1.155, matching a real GBPEUR=X. The EUR/EUR row is
    # the sentinel currency_rates always appends; without it an EUR amount joins
    # to nothing and lands as null.
    con.execute(
        "create table raw_forex.forex_daily as "
        "select * from (values "
        "('2026-01-02', 1.15, 1.16, 1.14, 1.15, 'GBP', 'EUR'), "
        "('2026-01-03', 1.15, 1.16, 1.14, 1.16, 'GBP', 'EUR'), "
        "('2024-01-01', 1.0, 1.0, 1.0, 1.0, 'EUR', 'EUR')"
        ") t(date, open, high, low, close, from_currency, to_currency)"
    )

    seed = ASSETS / "seed" / "seed_activity_mapping.csv"
    con.execute(
        "create table analytics.seed_activity_mapping as "
        "select category, activity, activity_type, "
        "cast(activity_count as integer) as activity_count "
        f"from read_csv('{seed}', header = true)"
    )
    return con


@pytest.fixture
def pipeline():
    con = build_warehouse()
    for asset, target in CHAIN:
        run_asset(con, asset, target)
    yield con
    con.close()


def scalar(con, query):
    """One numeric value, as a float.

    conversion_rate and the numbeo cost columns are NUMERIC, which DuckDB hands
    back as Decimal; pytest.approx compares against float, so coerce here.
    """
    (value,) = con.execute(query).fetchone()
    return float(value)


def test_the_fixture_rate_is_eur_per_local_not_its_reciprocal(pipeline):
    """1.155 EUR per GBP is what the models must multiply by.

    If the loader had stored the reciprocal (0.866) the models would still be
    "correct" arithmetic against the wrong number, so pin the direction here.
    """
    rate = scalar(
        pipeline,
        "select conversion_rate from analytics.prep__avg_forex_rate "
        "where from_currency = 'GBP' and to_currency = 'EUR'",
    )

    assert rate == pytest.approx(GBP_RATE)
    assert rate > 1


def test_gross_salary_is_multiplied_into_eur(pipeline):
    """5000 GBP * 1.155 is 5775.00 EUR, not the 4329.00 the divide form returns."""
    gross = scalar(
        pipeline,
        "select avg_monthly_gross_salary_eur from analytics.core__job_earnings "
        "where city_name = 'London'",
    )

    assert gross == pytest.approx(5775.00)


def test_net_salary_is_multiplied_into_eur(pipeline):
    """Net is gross * ratio * rate: 5000 * 0.7 * 1.155 = 4042.50 EUR."""
    net = scalar(
        pipeline,
        "select avg_monthly_net_salary_eur from analytics.core__job_earnings "
        "where city_name = 'London'",
    )

    assert net == pytest.approx(4042.50)


def test_eur_amounts_pass_through_unchanged(pipeline):
    """EUR multiplies by the 1.0 sentinel rate, so it must not move."""
    gross = scalar(
        pipeline,
        "select avg_monthly_gross_salary_eur from analytics.core__job_earnings "
        "where city_name = 'Berlin'",
    )

    assert gross == pytest.approx(4000.00)


def test_cost_of_living_is_multiplied_into_eur(pipeline):
    """10 GBP * 1.155 is 11.55 EUR, not the 8.66 the divide form returns."""
    cost, monthly = pipeline.execute(
        "select cost_eur, monthly_activity_cost_eur "
        "from analytics.core__cost_of_living where city_name = 'London'"
    ).fetchone()
    cost, monthly = float(cost), float(monthly)

    assert cost == pytest.approx(11.55)
    assert monthly == pytest.approx(138.60)  # 120 GBP * 1.155


def test_both_models_use_the_same_operator(pipeline):
    """One divide would be enough to invert a whole table, so check both.

    A city's EUR cost and EUR salary are the same rate applied to two amounts;
    if the operator differed between the models their ratio would drift from the
    local ratio.
    """
    local_cost = scalar(
        pipeline, "select cost_value from analytics.prep__numbeo_cost_of_living"
    )
    eur_cost = scalar(
        pipeline, "select cost_eur from analytics.core__cost_of_living"
    )
    local_gross = scalar(
        pipeline,
        "select avg_monthly_gross_salary from analytics.prep__job_earnings "
        "where city_name = 'London'",
    )
    eur_gross = scalar(
        pipeline,
        "select avg_monthly_gross_salary_eur from analytics.core__job_earnings "
        "where city_name = 'London'",
    )

    assert eur_cost / local_cost == pytest.approx(GBP_RATE, rel=1e-3)
    assert eur_gross / local_gross == pytest.approx(GBP_RATE, rel=1e-3)

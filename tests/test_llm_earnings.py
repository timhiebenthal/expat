"""The earnings loader has to hand dbt a job title it can join on.

prep__job_earnings parses jobtitle_and_experience back into a title and inner
joins it against clean__config_jobs. The model is asked for that string, and
asking is not enough: it returned "Staff Analytics Engineer, 10 years" for a
configured "Analytics Engineer", so the join matched nothing and every city
vanished from job_earnings with no error anywhere.

The logic under test lives in `pipeline/lib/earnings.py`; `loading/llm_earnings.py`
stays as the dlt-era caller until cutover.
"""

import pytest


@pytest.fixture(scope="module")
def earnings():
    import pipeline.lib.earnings as module

    return module


def test_job_string_is_built_not_asked_for(earnings):
    assert (
        earnings.build_job_string("Analytics Engineer", 10)
        == "Analytics Engineer with 10 years of experience"
    )
    assert (
        earnings.build_job_string("Data Scientist", 5)
        == "Data Scientist with 5 years of experience"
    )


def test_job_string_parses_back_to_the_configured_title(earnings):
    """Runs prep__job_earnings' own expressions over the string we generate.

    If the two ever drift apart the join goes quiet again, so check the parse
    that dbt actually performs rather than a Python reimplementation of it.
    """
    import duckdb

    job_string = earnings.build_job_string("Analytics Engineer", 10)
    dwh = duckdb.connect()

    title = dwh.execute(
        "select split_part(?, ' with ', 1)", [job_string]
    ).fetchone()[0]
    years = dwh.execute(
        "select try_cast(regexp_extract(split_part(?, ' with ', 2), '(\\d+)') as int)",
        [job_string],
    ).fetchone()[0]

    assert title == "Analytics Engineer"
    assert years == 10


def test_a_reworded_title_from_the_model_is_overridden(earnings):
    """The regression: the model's own wording must never reach the warehouse."""
    from_model = [
        {
            "city": "Munich",
            "country": "Germany",
            "currency": "EUR",
            "jobtitle_and_experience": "Staff Analytics Engineer, 10 years",
            "average_monthly_gross_salary": 8000.0,
            "net_to_gross_salary_ratio": 0.62,
        }
    ]

    records = earnings.attach_job_string(from_model, "Analytics Engineer", 10)

    assert records[0]["jobtitle_and_experience"] == (
        "Analytics Engineer with 10 years of experience"
    )


def test_records_carry_every_key_the_dwh_expects(earnings):
    records = earnings.attach_job_string(
        [{"city": "Munich", "country": "Germany", "currency": "EUR"}],
        "Analytics Engineer",
        10,
    )

    assert list(records[0]) == [
        "city",
        "country",
        "currency",
        "jobtitle_and_experience",
    ]


def test_a_missing_city_fails_loudly(earnings):
    cities = [
        {"city": "Munich", "country": "Germany", "currency": "EUR"},
        {"city": "London", "country": "United Kingdom", "currency": "GBP"},
    ]

    with pytest.raises(RuntimeError, match="Athens"):
        earnings.assert_every_city_came_back(cities, ["Munich", "London", "Athens"])


def test_city_matching_ignores_case_and_padding(earnings):
    cities = [{"city": " munich ", "country": "Germany", "currency": "EUR"}]

    earnings.assert_every_city_came_back(cities, ["Munich"])


def test_the_earnings_call_is_injected(earnings):
    """No live model here: the caller supplies the callable that hits the LLM."""
    seen = {}

    def fake_invoke(prompt):
        seen["prompt"] = prompt
        return [
            {
                "city": "Munich",
                "country": "Germany",
                "currency": "EUR",
                "jobtitle_and_experience": "Staff Analytics Engineer, 10 years",
                "average_monthly_gross_salary": 8000.0,
                "net_to_gross_salary_ratio": 0.62,
            }
        ]

    rows = earnings.retrieve_city_earnings(
        ["Munich"], "Analytics Engineer with 10 years of experience", fake_invoke
    )

    assert rows[0]["city"] == "Munich"
    assert "Analytics Engineer with 10 years of experience" in seen["prompt"]

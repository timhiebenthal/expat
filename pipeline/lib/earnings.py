"""LLM salary estimates, free of network calls at import.

The model is advisory. It is asked to echo the job title verbatim, and asking is
not enough: the same model on the same endpoint reworded it before ("Staff
Analytics Engineer" for a configured "Analytics Engineer"), which silently
dropped every row for that job from the prep join. So the job string is built
here and stamped over whatever comes back. The LLM call itself is injected, which
keeps this module model-free and directly testable.

Called by `pipeline/assets/ingest/earnings.py`.
"""

import logging

FIELDS_OF_INTEREST = [
    "city",
    "country",
    "currency",
    "jobtitle_and_experience",
    "average_monthly_gross_salary",
    "net_to_gross_salary_ratio",
]

PROMPT_TEMPLATE = """Return the specified information for the for the cities of {cities}.
        The answer should be purely a JSON Array where each city is it's own object with {fields} as keys.
        Use the city names exactly as they are spelled above, and use the job title exactly as it appears in "{job}" - do not
        shorten it, expand it, or add a seniority word such as "Staff" or "Senior" that was not given to you.
        For the salary consider the average monthly gross salary for a {job} and return only a JSON Object without any other text"""


def build_job_string(job_title, years_experience):
    """The canonical job string, in the shape prep__job_earnings parses.

    Built here instead of taken from the model. prep__job_earnings parses the
    title back out and inner-joins it against clean__config_jobs, so a reworded
    title - "Analytics Engineer" coming back as "Staff Analytics Engineer", as
    the real data did - drops every row for that job with no error at all.
    """
    return f"{job_title} with {int(years_experience)} years of experience"


def attach_job_string(cities, job_title, years_experience):
    """Stamp every record with the job string, overriding whatever came back.

    The prompt asks the model to echo the title verbatim, but that is only
    advisory: it is the same model, on the same endpoint, that reworded it
    before. This is the guarantee.
    """
    job_string = build_job_string(job_title, years_experience)
    return [{**city, "jobtitle_and_experience": job_string} for city in cities]


def assert_every_city_came_back(cities, requested):
    """Fail loudly when the model drops or invents a city.

    city_name is what prep__numbeo_cost_of_living joins on, so a missing city
    disappears from the dashboard exactly the way London did.
    """
    returned = {city["city"].strip().lower() for city in cities}
    missing = [city for city in requested if city.strip().lower() not in returned]

    if missing:
        raise RuntimeError(
            f"No earnings returned for {', '.join(missing)}. "
            "Refusing to write a partial earnings table."
        )


def build_prompt(cities, job_string, fields=FIELDS_OF_INTEREST):
    """The prompt the model is asked to answer. Pure string building."""
    return PROMPT_TEMPLATE.format(
        cities=", ".join(cities),
        fields=", ".join(fields),
        job=job_string,
    )


def retrieve_city_earnings(cities, job_string, invoke, fields=FIELDS_OF_INTEREST):
    """Ask for one city list through an injected ``invoke(prompt) -> list[dict]``.

    ``invoke`` is supplied by the caller, which wires the real structured-output
    chain in; that is the only place a live model is reached.
    """
    logging.info(
        f"Retrieving data from LLM model for {len(cities)} cities ... "
    )
    rows = invoke(build_prompt(cities, job_string, fields))
    logging.info(f"Retrieved data of {len(rows)} cities.")
    return rows

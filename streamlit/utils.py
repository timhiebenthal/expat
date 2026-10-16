import altair as alt
import logging
import os
import shutil
import subprocess
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Docker and Cloud Run inject DUCKDB_LOCATION as a real environment variable. On
# the host there is no shell export, so read it from .env. load_dotenv leaves an
# already-set variable alone, so the container's value always wins.
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def define_database_location():
    """Resolve DUCKDB_LOCATION once.

    A relative path is anchored at the repo root so the app does not depend on
    the working directory. Docker and Cloud Run pass an absolute path, which is
    used as-is.
    """
    location = Path(os.environ.get("DUCKDB_LOCATION", "database/dwh.duckdb"))
    resolved = str(location if location.is_absolute() else REPO_ROOT / location)
    # Bruin reads DUCKDB_LOCATION through .bruin.yml and resolves a relative path
    # against its own working directory, and it runs as a subprocess, so
    # normalise it to an absolute path once, here.
    os.environ["DUCKDB_LOCATION"] = resolved
    return resolved


DATABASE_LOCATION = define_database_location()

# configure timestamp for logging
logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def create_altair_labelled_vertical_bar_chart(df, x_field, x_label, y_field, y_label):
    """
    creates a vertical bar chart with labels at the end of the bars
    """

    base = alt.Chart(df).encode(
        x=alt.X(
            x_field,
            title=x_label,
            axis=alt.Axis(format="0,.0f", ticks=False, domain=False),
        ),
        y=alt.Y(
            y_field, title=y_label, axis=alt.Axis(labelFontSize=14, titleFontSize=18)
        ),
        text=alt.Text(x_field, format="0,.0f"),
    )

    return base.mark_bar() + base.mark_text(
        align="right", size=18, color="#FFFFFF", dx=-5
    )


def load_config():
    """
    Loads configuration from DuckDB
    Returns:
        type: dict
    """
    import duckdb

    # DuckDB allows a single writer per file, so the connection has to be
    # released before anything else - the Bruin pipeline - can open it. The app
    # is long-lived, so leaving this to garbage collection keeps the write lock
    # for as long as the process lives.
    dwh = duckdb.connect(DATABASE_LOCATION)
    try:
        cities = dwh.table("raw_config.cities").df()["name"].tolist()
        jobs = dwh.table("raw_config.jobs").df().to_dict(orient="records")
    finally:
        dwh.close()

    return {
        "cities": cities,
        "jobs": jobs,
    }


def save_config(city_data, jobs_data):
    import yaml
    import time

    config = {
        "cities": city_data["cities"].dropna().tolist(),
        "jobs": jobs_data.dropna().to_dict(orient="records"),
    }

    # saves the dataframe as a yaml file
    with open("config.yml", "w") as file:
        logging.info("Saving to config.yml\n")
        yaml.dump(config, file, sort_keys=False)


def save_config_to_duckdb(city_df, jobs_df):
    import os
    import logging
    import duckdb
    import pandas as pd

    jobs_df = jobs_df.rename(
        columns={
            "Job Title": "job_title",
            "Years of Experience": "years_experience",
        }
    )
    # upload tables to DuckDB
    dwh = duckdb.connect(DATABASE_LOCATION)
    try:
        dwh.sql("CREATE SCHEMA IF NOT EXISTS raw_config")
        dwh.sql("CREATE OR REPLACE TABLE raw_config.cities AS SELECT * FROM city_df")
        dwh.sql("CREATE OR REPLACE TABLE raw_config.jobs AS SELECT * FROM jobs_df")
        logging.info("Tables for jobs and cities uploaded to DuckDB\n")
    finally:
        # Released here on purpose: run_pipeline() shells out to Bruin straight
        # after this, and that subprocess needs the write lock.
        dwh.close()


def load_city_slugs(database_location=None):
    """name -> ``{"slug", "city_id"}`` for every resolved city in raw_config.

    Tolerant of a table written before resolution existed: without the slug
    columns there is nothing to inherit, so the mapping comes back empty.
    """
    import duckdb

    location = database_location or DATABASE_LOCATION
    dwh = duckdb.connect(location)
    try:
        columns = {
            row[0]
            for row in dwh.execute(
                "select column_name from information_schema.columns "
                "where table_schema = 'raw_config' and table_name = 'cities'"
            ).fetchall()
        }
        slug = "numbeo_slug" if "numbeo_slug" in columns else "null"
        city_id = "numbeo_city_id" if "numbeo_city_id" in columns else "null"
        rows = dwh.execute(
            f"select name, {slug}, {city_id} from raw_config.cities"
        ).fetchall()
    finally:
        dwh.close()

    return {
        name: {"slug": slug, "city_id": city_id}
        for name, slug, city_id in rows
        if slug
    }


def resolve_city_rows(cities, fetch=None):
    """Annotate each city row with its numbeo resolution.

    Adds ``state`` ("resolved" / "ambiguous" / "unresolved") and ``matches``,
    skipping blank names. The decision itself lives in ``pipeline.lib.numbeo``;
    this only adapts rows to it, so it stays testable without the UI.
    """
    from pipeline.lib.numbeo import resolve_city

    annotated = []
    for city in cities:
        name = (city.get("name") or "").strip()
        if not name:
            continue
        country = (city.get("country") or "").strip()
        outcome = resolve_city(name, country=country or None, fetch=fetch)
        annotated.append({**city, "state": outcome.state, "matches": outcome.matches})
    return annotated


def apply_resolution(cities, picks):
    """Merge the user's decisions into the rows written to raw_config.cities.

    ``cities`` are rows annotated by ``resolve_city_rows``; ``picks`` maps a city
    name to ``{"slug", "city_id", "drop"}``. A row marked drop, or one that never
    got a slug, is left out - an unresolved city must never be written.
    """
    final = []
    for city in cities:
        pick = picks.get(city["name"], {})
        if pick.get("drop") or not pick.get("slug"):
            continue
        final.append(
            {
                "name": city["name"],
                "country": city.get("country"),
                "description": city.get("description"),
                "numbeo_slug": pick["slug"],
                "numbeo_city_id": pick.get("city_id"),
            }
        )
    return final


def picks_from(annotated, choices=None, fetch=None):
    """Turn annotated rows plus the user's choices into ``{name: pick}``.

    A pick is ``{"slug", "city_id"}`` or ``{"drop": True}``. A resolved row needs
    no choice; an ambiguous row uses ``choices[name]["city_id"]``; an unresolved
    row uses ``choices[name]["manual"]`` as a slug, or is dropped. The slug is
    read from numbeo only for a chosen id, never for the whole candidate list.
    """
    from pipeline.lib.numbeo import canonical_slug

    choices = choices or {}
    picks = {}
    for city in annotated:
        name = city["name"]
        choice = choices.get(name, {})
        if choice.get("drop"):
            picks[name] = {"drop": True}
        elif city["state"] == "resolved":
            city_id = city["matches"][0]["value"]
            picks[name] = {
                "slug": canonical_slug(city_id, fetch=fetch),
                "city_id": city_id,
            }
        elif city["state"] == "ambiguous" and choice.get("city_id"):
            city_id = choice["city_id"]
            picks[name] = {
                "slug": canonical_slug(city_id, fetch=fetch),
                "city_id": city_id,
            }
        elif city["state"] == "unresolved":
            manual = (choice.get("manual") or "").strip()
            picks[name] = {"slug": manual or None, "city_id": None}
        else:
            picks[name] = {}
    return picks


def rename_rows(annotated, renames, fetch=None):
    """Re-resolve rows the user renamed, returning the updated annotation.

    A rename is a new name to match, not a label change: the row is resolved
    again so the panel can tell whether it is still blocked.
    """
    from pipeline.lib.numbeo import resolve_city

    updated = []
    for city in annotated:
        new_name = renames.get(city["name"])
        if not new_name:
            updated.append(city)
            continue
        outcome = resolve_city(
            new_name, country=city.get("country") or None, fetch=fetch
        )
        updated.append(
            {
                **city,
                "name": new_name,
                "state": outcome.state,
                "matches": outcome.matches,
            }
        )
    return updated


def editable_df_component(dict, object_name, expander=False):
    import pandas as pd

    if object_name == "cities":
        cols = ["cities"]
    if object_name == "llm_cities":
        cols = ["city", "country", "description"]
    elif object_name == "jobs":
        cols = ["job_title", "years_experience"]
    # else:
    #     raise ValueError(f"Object name '{object_name}' not recognized.")

    df = pd.DataFrame(data=dict[object_name], columns=cols)

    if expander == True:
        expander = st.expander(object_name.title())

        return expander.data_editor(
            data=df,
            num_rows="dynamic",
            hide_index=True,
            # height=750
        )
    else:
        return st.data_editor(
            data=df,
            num_rows="dynamic",
            hide_index=True,
            # height=750
        )


def bruin_executable():
    """The pinned Bruin CLI.

    curl-installed to ~/.local/bin on the host and into /usr/local/bin in the
    image. shutil.which covers the image and any PATH install; the fallback
    covers a host shell that never sourced ~/.bruin/env.
    """
    found = shutil.which("bruin")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / "bruin")


def run_pipeline():
    """Shell out to Bruin for the whole pipeline.

    One subprocess replaces the three loaders plus dbt deps/build. It has to be a
    subprocess: DuckDB takes a single writer, so the app must not still hold the
    file. --workers 1 for the same reason - Bruin runs 16 workers by default and
    they collide on the warehouse lock.
    """
    import time

    print("\n>>>> Running pipeline ...\n")

    with st.status("Preparing your comparsion ...", expanded=True) as status:
        st.write("Run Bruin pipeline ...")

        result = subprocess.run(
            [bruin_executable(), "run", "pipeline", "--workers", "1"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        print(result.stdout)
        print(result.stderr)

        if result.returncode != 0:
            # A failing step used to be swallowed, so the run carried on and
            # reported success while nothing had been loaded.
            st.error("Bruin pipeline failed! Please check the logs.")
            status.update(label="Pipeline failed", state="error", expanded=True)
            return False

        status.update(label="Pipeline complete!", state="complete", expanded=False)
        success_info = st.success("Pipeline run successful! :)", icon="✅")
        time.sleep(2)  # Wait for 2 seconds
        success_info.empty()  # Clear the alert
        return True

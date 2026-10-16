"""The numbeo category labels must keep matching the activity mapping seed.

The scraper pulls raw category labels off numbeo, prep__numbeo_cost_of_living
inner-joins them against seed_activity_mapping and silently drops everything that
does not match. When numbeo renamed its labels the join kept 3 of 34 rows and the
dashboard came out empty without a single error. The label snapshot below is
captured from a live city page; refresh it whenever numbeo is re-checked.
"""

import csv
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(
    REPO_ROOT, "pipeline", "assets", "seed", "seed_activity_mapping.csv"
)
SNAPSHOT = os.path.join(
    REPO_ROOT, "tests", "fixtures", "numbeo_cost_of_living_categories.txt"
)


def _read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return handle.read()


def _numbeo_categories():
    return [line for line in _read(SNAPSHOT).splitlines() if line.strip()]


def _seed_rows():
    return list(csv.DictReader(_read(SEED).splitlines()))


def test_every_seed_category_is_a_live_numbeo_label():
    live = set(_numbeo_categories())
    missing = sorted({row["category"] for row in _seed_rows()} - live)

    assert not missing, f"seed categories numbeo no longer serves: {missing}"


def test_seed_has_no_duplicate_categories():
    categories = [row["category"] for row in _seed_rows()]

    assert len(categories) == len(set(categories)), "duplicate category in the seed"


def test_every_seed_row_carries_an_activity():
    incomplete = [row["category"] for row in _seed_rows() if not row["activity"].strip()]

    assert not incomplete, f"seed rows without an activity: {incomplete}"


def test_seed_activity_count_is_positive():
    non_positive = [
        row["category"]
        for row in _seed_rows()
        if int(row["activity_count"]) <= 0
    ]

    assert not non_positive, f"seed rows with a non-positive count: {non_positive}"


def _seed_rows_with_basis():
    """Seed rows, or a readable failure while the seed has no counted_for column.

    An empty counted_for means "take the Cost group's default"; only the rows
    that state one are exceptions to their group.
    """
    rows = _seed_rows()
    assert rows and "counted_for" in rows[0], "the seed carries no counted_for column"

    return rows


def test_every_seed_row_states_a_known_count_basis():
    bases = {row["counted_for"] for row in _seed_rows_with_basis()}
    unknown = sorted(bases - {"", "person", "household"})

    assert not unknown, f"seed rows with an unknown count basis: {unknown}"


def test_only_the_documented_exceptions_override_their_cost_group():
    overridden = sorted(
        row["activity"]
        for row in _seed_rows_with_basis()
        if row["counted_for"].strip()
    )

    assert overridden == [
        "Restaurant - Mid-range Meal for 2",
        "Utilities - Mobile Phone Plan",
    ], f"the rows overriding their Cost group changed: {overridden}"
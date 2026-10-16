"""The Household's counting rules, with no Streamlit and no warehouse.

A Cost item's count is a Household total, and the count is *stated* either per
Member or once for the Household. These are the rules the prototype was driven to
(streamlit/prototypes/household-member-counts.prototype.html), so the numbers here
are the ones it produced rather than numbers invented twice.

One Member has to reproduce the dashboard exactly as it is today - that is what
makes the single-person case this feature's regression test.
"""

import ast
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STREAMLIT_DIR = os.path.join(REPO_ROOT, "streamlit")

# The pages import `utils` and friends by bare name, resolving against their own
# directory, so the tests reach them the same way.
sys.path.insert(0, STREAMLIT_DIR)

import household  # noqa: E402


@pytest.mark.parametrize(
    ("activity", "seed", "counted_for", "couple", "single"),
    [
        ("cappuccino", 4, "person", 8, 4),
        ("water", 30, "person", 60, 30),
        ("mobile phone plan", 1, "person", 2, 1),
        ("broadband", 1, "household", 1, 1),
        ("utilities", 1, "household", 1, 1),
        ("meal for two", 4, "household", 4, 4),
    ],
)
def test_a_count_opens_at_its_household_size(
    activity, seed, counted_for, couple, single
):
    assert household.default_count(seed, counted_for, 2) == couple, activity
    assert household.default_count(seed, counted_for, 1) == single, activity


def test_an_unknown_basis_never_multiplies():
    """The safe direction: a Cost item nobody has classified is not doubled."""
    assert household.default_count(4, "per-capita", 2) == 4


@pytest.mark.parametrize(
    ("count", "counted_for", "members", "expected"),
    [
        (40, "person", 2, "20 per Member"),
        (40, "person", 1, "40 per Member"),
        (60, "person", 2, "30 per Member"),
        (5, "person", 2, "2.5 per Member"),
        (4, "household", 2, "shared - paid once for the household"),
        (1, "household", 1, "shared - paid once for the household"),
    ],
)
def test_a_count_reads_as_what_it_means(count, counted_for, members, expected):
    assert household.per_member_figure(count, counted_for, members) == expected


def test_settings_carry_the_member_count():
    assert household.members_from_settings({"members": "2"}) == 2
    assert household.members_from_settings({"members": 2}) == 2
    assert household.members_from_settings({"members": "1"}) == 1


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        {"members": None},
        {"members": ""},
        {"members": "two"},
        {"members": "2.5"},
        {"other": "2"},
    ],
)
def test_a_missing_or_nonsense_member_count_means_one(settings):
    assert household.members_from_settings(settings) == 1


@pytest.mark.parametrize(
    ("stored", "expected"),
    [("0", 1), ("-3", 1), ("1", 1), ("2", 2), ("3", 2), ("99", 2)],
)
def test_the_member_count_is_clamped_to_one_or_two(stored, expected):
    """A Household has one or two Members; anything else is not a Household."""
    assert household.members_from_settings({"members": stored}) == expected


def test_the_module_is_free_of_streamlit_and_duckdb():
    """What keeps these tests fast, and the one thing the prototype proved."""
    tree = ast.parse(open(household.__file__, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported & {"streamlit", "duckdb"}, f"imports: {sorted(imported)}"

"""How a Household's monthly count opens, and what it means.

A Cost item's count is a Household total - what the two of you consume between
you, not one person's habit. The count is *stated* either per Member or once for
the Household, and that is what decides the value an input opens at. It is also
the only thing that decides it: the analysis arithmetic stays `price x count`
summed per city, so nothing here multiplies a cost.

Deliberately free of Streamlit and DuckDB. This is the part worth testing on its
own, and the prototype proved the numbers before any of it was wired into a page.
"""

from collections.abc import Mapping

PERSON = "person"
HOUSEHOLD = "household"

SHARED_FIGURE = "shared - paid once for the household"


def default_count(seed_count: int, counted_for: str, members: int) -> int:
    """The Household's opening count for a Cost item.

    A Per-person count is stated per Member, so a couple opens at twice what one
    person would. Nothing else is touched, including a Cost item nobody has
    classified - the direction that never multiplies by mistake.
    """
    return seed_count * members if counted_for == PERSON else seed_count


def per_member_figure(count: int, counted_for: str, members: int) -> str:
    """How a count reads beside the input.

    Shown for a single Member too, where it says the same number back: a label
    that only appeared for a couple would be a surprise the first time the
    household grew.
    """
    if counted_for != PERSON:
        return SHARED_FIGURE

    return f"{round(count / members, 2):g} per Member"


def members_from_settings(settings: Mapping[str, object] | None) -> int:
    """The Member count held in the app-owned settings, clamped to one or two.

    A missing table, key or value means one Member: that is the behaviour that
    existed before a household could be chosen, and it is the direction that never
    inflates a cost.
    """
    if not settings:
        return 1

    try:
        stored = int(settings.get("members", 1))
    except (TypeError, ValueError):
        return 1

    return min(2, max(1, stored))

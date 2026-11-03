"""Smoke test: the Streamlit app must render without raising.

Module-level errors in the app surface here as ``at.exception`` instead of
appearing as a broken page after a click. This is what catches the pyarrow /
numpy mismatch that used to fail only once ``st.data_editor`` rendered.
"""

import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(REPO_ROOT, "streamlit", "Home.py")


@pytest.fixture(scope="module")
def app():
    # streamlit/Home.py does a bare `import utils`, which resolves against the
    # script's own directory only when streamlit itself is the entry point.
    sys.path.insert(0, os.path.dirname(APP_PATH))
    try:
        yield AppTest.from_file(APP_PATH, default_timeout=30).run()
    finally:
        sys.path.remove(os.path.dirname(APP_PATH))


def test_app_renders_without_exception(app):
    assert not app.exception, "\n".join(str(e.value) for e in app.exception)


def test_app_shows_its_title(app):
    assert [t.value for t in app.title] == [
        "Welcome to the Expat Planning App!"
    ]


@pytest.fixture
def gate(monkeypatch):
    """Drive the Submit gate with utils stubbed - no DB, no network, no Bruin."""
    sys.path.insert(0, os.path.dirname(APP_PATH))
    import streamlit as st
    import utils

    calls = {}
    state = {"utils": utils}

    monkeypatch.setattr(
        utils, "resolve_city_rows", lambda cities, fetch=None: _resolve(state)
    )
    monkeypatch.setattr(
        utils,
        "picks_from",
        lambda annotated, choices=None, fetch=None: {
            c["name"]: {"slug": c["name"], "city_id": "1"} for c in annotated
        },
    )
    monkeypatch.setattr(
        utils,
        "apply_resolution",
        lambda cities, picks: [
            {"name": c["name"], "numbeo_slug": picks[c["name"]]["slug"]}
            for c in cities
        ],
    )
    monkeypatch.setattr(
        utils,
        "save_config_to_duckdb",
        lambda city_df, jobs_df, members: calls.update(saved=city_df),
    )
    monkeypatch.setattr(utils, "run_pipeline", lambda: calls.update(ran=True) or True)
    monkeypatch.setattr(st, "switch_page", lambda *a, **k: None)

    def build(annotated, throttle=False):
        state["annotated"] = annotated
        state["throttle"] = throttle
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.session_state["city_suggestions"] = [
            {"name": "Munich", "country": "Germany", "description": "home"}
        ]
        at.run()
        return at

    try:
        yield build, calls
    finally:
        sys.path.remove(os.path.dirname(APP_PATH))


def _resolve(state):
    if state.get("throttle"):
        raise state["utils"].ResolutionThrottled("numbeo is rate-limiting us")
    return state["annotated"]


def _submit(at):
    next(b for b in at.button if b.label == "Submit Cities").click().run()


def test_gate_saves_and_runs_when_everything_resolves(gate):
    build, calls = gate
    at = build(
        [
            {
                "name": "Munich",
                "country": "Germany",
                "description": "home",
                "state": "resolved",
                "matches": [{"label": "Munich, Germany", "value": "1111"}],
            }
        ]
    )

    _submit(at)

    assert "saved" in calls
    assert calls["ran"] is True


def test_gate_blocks_the_write_and_shows_the_panel(gate):
    build, calls = gate
    at = build(
        [
            {
                "name": "Munich",
                "country": "Germany",
                "description": "home",
                "state": "resolved",
                "matches": [{"label": "Munich, Germany", "value": "1111"}],
            },
            {
                "name": "Nowhereville",
                "country": "",
                "description": "made up",
                "state": "unresolved",
                "matches": [],
            },
        ]
    )

    _submit(at)

    assert "saved" not in calls
    confirm = next(b for b in at.button if b.label == "Confirm and run pipeline")
    assert confirm.disabled is True
    assert any("no match" in w.value for w in at.warning)


def test_gate_opens_once_an_ambiguous_city_is_picked(gate):
    """A choice on the ambiguous row is what unblocks Confirm - not a re-resolve."""
    build, calls = gate
    at = build(
        [
            {
                "name": "London",
                "country": "United Kingdom",
                "description": "favourite",
                "state": "ambiguous",
                "matches": [
                    {"label": "London, United Kingdom", "value": "2"},
                    {"label": "Londonderry (Derry), United Kingdom", "value": "3"},
                ],
            }
        ]
    )

    _submit(at)

    # The first match is the radio's default, so the row is already decided.
    # Before the fix, Confirm stayed disabled anyway because the gate read the
    # resolution state instead of the picks.
    radio = next(r for r in at.radio if r.key == "amb-London")
    assert radio.value == "London, United Kingdom"

    confirm = next(b for b in at.button if b.label == "Confirm and run pipeline")
    assert confirm.disabled is False
    confirm.click().run()
    assert "saved" in calls


def test_gate_opens_once_an_unmatched_city_is_dropped(gate):
    """Removing the row is a decision, so it settles the city like a pick does."""
    build, calls = gate
    at = build(
        [
            {
                "name": "Nowhereville",
                "country": "",
                "description": "made up",
                "state": "unresolved",
                "matches": [],
            }
        ]
    )

    _submit(at)

    confirm = next(b for b in at.button if b.label == "Confirm and run pipeline")
    assert confirm.disabled is True

    next(c for c in at.checkbox if c.key == "drop-Nowhereville").check().run()

    confirm = next(b for b in at.button if b.label == "Confirm and run pipeline")
    assert confirm.disabled is False
    confirm.click().run()
    assert "saved" in calls


def test_gate_reports_a_throttle_and_writes_nothing(gate):
    build, calls = gate
    at = build([], throttle=True)

    _submit(at)

    assert "saved" not in calls
    assert any("rate-limiting" in e.value for e in at.error)


def test_app_offers_the_household_to_choose(app):
    """The entry mask is where the Member count is entered, not inferred."""
    radios = {radio.label: list(radio.options) for radio in app.radio}

    assert radios, "no radio rendered"
    assert ["Single", "Couple"] in radios.values(), radios

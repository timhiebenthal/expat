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
    state = {}

    monkeypatch.setattr(
        utils, "resolve_city_rows", lambda cities, fetch=None: state["annotated"]
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
        lambda city_df, jobs_df: calls.update(saved=city_df),
    )
    monkeypatch.setattr(utils, "run_pipeline", lambda: calls.update(ran=True) or True)
    monkeypatch.setattr(st, "switch_page", lambda *a, **k: None)

    def build(annotated):
        state["annotated"] = annotated
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

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

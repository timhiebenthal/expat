"""Environment coherence tests.

These guard a failure mode that the resolver cannot see. pyarrow's compiled
extension hard-requires numpy>=2, but pyarrow declares no numpy dependency at
all, so pip will happily install pyarrow next to an incompatible numpy. The
only symptom is an ImportError raised deep inside Streamlit, minutes after the
app looks like it started fine.
"""

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

import numpy


def test_pyarrow_imports():
    """Canary: the exact ImportError Streamlit surfaced via st.data_editor."""
    import pyarrow  # noqa: F401


def test_no_installed_package_excludes_numpy_2():
    """Name the culprit directly rather than only its symptom.

    Anything declaring a numpy requirement that numpy 2.0.0 fails to satisfy is
    a latent break, even while the rest of the stack still imports fine.
    """
    from importlib.metadata import distributions

    offenders = []
    for dist in distributions():
        for raw in dist.requires or []:
            if "extra ==" in raw:
                # An extra nobody asked for constrains nothing. If it is ever
                # activated, pip re-resolves and the pyarrow canary above is
                # what catches the resulting mismatch.
                continue
            requirement = Requirement(raw)
            if requirement.name != "numpy":
                continue
            if Version("2.0.0") not in requirement.specifier:
                offenders.append(f"{dist.metadata['Name']}=={dist.version}: {raw}")

    assert not offenders, "these packages pin numpy below 2.0.0:\n" + "\n".join(
        offenders
    )


@pytest.mark.parametrize("module", ["pandas", "duckdb", "streamlit", "pyarrow"])
def test_runtime_modules_import(module):
    """Every module the app touches at startup, imported up front."""
    __import__(module)

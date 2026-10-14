"""`bruin validate` has to pass without a warehouse.

It is static: it parses every asset header, checks that each declared dependency
exists as an asset, and rejects cycles. It opens no database, so it runs on a
fresh clone and inside the container alike.

The CLI is a curl-installed Go binary rather than a project dependency, so a clone
can legitimately lack it. The test skips rather than fails when it is absent; the
repository AGENTS.md names the install command.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def bruin_cli():
    """The CLI from PATH, or from ~/.local/bin where the installer puts it."""
    found = shutil.which("bruin")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / "bruin"
    return str(candidate) if candidate.exists() else None


def test_pipeline_validates():
    cli = bruin_cli()
    if cli is None:
        pytest.skip("bruin CLI is not installed")

    result = subprocess.run(
        [cli, "validate", "pipeline"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr

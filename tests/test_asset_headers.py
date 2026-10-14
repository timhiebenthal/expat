"""Every Bruin asset must declare its name and layer explicitly.

SPEC.md calls these out as easy to get wrong:

- without an explicit `name:`, Bruin infers the table name from the path, so a
  rename silently changes the table name
- the `layer:` tag is what scopes runs (`--selector "tag:layer:transform"`)

Helpers under `pipeline/lib/` are not assets and carry no header, so this only
walks `pipeline/assets/`.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "pipeline" / "assets"

HEADER = re.compile(r"@bruin\b(.*?)@bruin", re.DOTALL)


def asset_files():
    return sorted(ASSETS_DIR.rglob("*.py")) + sorted(ASSETS_DIR.rglob("*.sql"))


def parse_header(path):
    match = HEADER.search(path.read_text())
    assert match, f"{path.relative_to(REPO_ROOT)} has no @bruin header"
    return match.group(1)


def test_there_is_at_least_one_asset():
    assert asset_files(), "no assets found - the glob is wrong, so this proves nothing"


@pytest.mark.parametrize("path", asset_files(), ids=lambda p: p.name)
def test_asset_declares_an_explicit_name(path):
    header = parse_header(path)
    assert re.search(r"^\s*name:\s*\S", header, re.MULTILINE), (
        f"{path.name} has no explicit name:"
    )


@pytest.mark.parametrize("path", asset_files(), ids=lambda p: p.name)
def test_asset_carries_a_layer_tag(path):
    header = parse_header(path)
    assert "layer:" in header, f"{path.name} has no layer: tag"

"""Release-surface parity: every version-owned file is actually committed.

`scripts/bump-version.mjs --write` propagates the version to its OWNED list, but
python-semantic-release only commits the files named in
`[tool.semantic_release].assets` (plus `version_toml` / `version_variables`).
A surface in one list and not the other is written in CI and then dropped, so
the tag ships with a stale file and the publish job's `--check` gate fails
after the tag already exists.

Regression: `package-lock.json` was added to OWNED in #44 without being added
to ASSETS, which left v6.1.0 tagged but unpublished.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED_BLOCK_RE = re.compile(r"const OWNED = \[(.*?)\];", re.DOTALL)


def _owned_surfaces() -> set[str]:
    """Files that `bump-version.mjs --write` rewrites, read from its OWNED list."""
    source = (ROOT / "scripts" / "bump-version.mjs").read_text(encoding="utf-8")
    block = OWNED_BLOCK_RE.search(source)
    assert block is not None, "OWNED list not found in scripts/bump-version.mjs"
    return set(re.findall(r'"([^"]+)"', block.group(1)))


def _release_config() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["tool"]["semantic_release"]


def _committed_surfaces(config: dict) -> set[str]:
    """Paths semantic-release stages: `assets` plus the `file:key` surfaces."""
    committed = set(config.get("assets", []))
    for key in ("version_toml", "version_variables"):
        for entry in config.get(key, []):
            committed.add(entry.split(":", 1)[0])
    return committed


def test_every_owned_surface_is_committed_by_the_release() -> None:
    committed = _committed_surfaces(_release_config())

    uncommitted = _owned_surfaces() - committed

    assert not uncommitted, (
        "bump-version.mjs writes these files but semantic-release never commits "
        f"them, so the release tag drifts: {sorted(uncommitted)}"
    )


def test_every_owned_surface_exists_on_disk() -> None:
    missing = sorted(rel for rel in _owned_surfaces() if not (ROOT / rel).exists())

    assert not missing, f"bump-version owns files that do not exist: {missing}"

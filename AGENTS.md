# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-06
**Commit:** b971a88
**Branch:** master

## OVERVIEW

Standalone Python CLI (3.12+) aggregating MCP servers behind one headless HTTP/SSE endpoint with Code Mode sandbox + loopback admin dashboard.

## DOMAINS ACTIVE

| Domain | Status | Evidence |
|--------|--------|----------|
| Security & Privacy | active | `src/mcp_gway/models.py` (SSRF guard), `src/mcp_gway/core/policy.py` (allow-list) |
| Testing | active | `tests/` (51 files), `tests/conftest.py`, `.github/workflows/test.yml` |
| Engineering | active | `src/mcp_gway/`, `pyproject.toml` (`uv_build`), `mise.toml` |
| Operations & Automation | active | `.github/workflows/release.yml`, `src/mcp_gway/observability/` |
| Legal & Regulatory | active | `LICENSE` (MIT, Deuri Vasquez 2026) |
| Brand & Marketing | absent | — |
| Revenue & Commercial | absent | — |
| Product | active | `PRODUCT.md`, `docs/specs/` |
| Financial | absent | — |
| People & Conduct | absent | — |

## STRUCTURE

```
src/mcp_gway/        # gateway core: cli/gateway/code_mode/sandbox/registry/models
  core/              # transport/discovery/policy/parsing/install (no CLI deps)
  observability/     # logging/metrics/tracing/health (stdlib + Starlette)
  admin/             # htpy+htmx dashboard (loopback + CSRF, CSP in gateway.py)
tests/               # mirrors src/ layout; hermetic DNS stub in conftest.py
skills/              # mcp-gway{-cli,-core,-mcp} agent skill surfaces
plugins/             # pi|antigravity|opencode host integrations (dirs kept)
scripts/             # bump-version.mjs (11 owned sync surfaces)
```

## WHERE TO LOOK

| Task | Location | Notes |
| Add/remove/refresh servers | `src/mcp_gway/cli.py`, `registry.py` | atomic `.json`+`.pyi`, last-write-wins |
| Serve transports | `src/mcp_gway/gateway.py:320-340` | http/sse routes differ, no fallback |
| Code Mode tools | `src/mcp_gway/code_mode.py` | 4 meta-tools + Starlark `sandbox.py` |
| Local allow-list | `src/mcp_gway/core/policy.py`, ADR-009 | `MCP_GWAY_ALLOW_LOCAL_COMMANDS`, no rename |
| Version/release | `scripts/bump-version.mjs`, `.github/workflows/release.yml` | push-to-master auto via semantic-release, pyproject is truth |
| Specs/ADRs | `docs/specs/` (10_design/12_adr/15_requirements/30_delivery/40_workspace/50_archive) | archived specs are history, not live |

## BOUNDARIES

- `serve` binds `127.0.0.1`; `0.0.0.0` needs `MCP_GWAY_ALLOW_REMOTE=1` or exit 2.
- Admin `/`, `/admin*` loopback-gated + per-process CSRF; OAuth values masked in views.
- No PII stores; tokens in `~/.config/mcp-gway/tokens/` (`0o600`).

## CODE MAP

- Entry: `mcp-gway = mcp_gway.cli:main` (`mgw` 1:1 alias); `serve --transport stdio|http|sse`.
- Core: `core/` owns transport/discovery; `gateway.py` owns HTTP/SSE; `code_mode.py` owns meta-tools.
- Centrality unmeasured (no LSP run); map from grep + structure scouts.

## CONVENTIONS

- `from __future__ import annotations` + type hints on all public functions; ruff only linter.
- No comments unless requested; tests mirror `src/` with `tmp_path`/`monkeypatch`, async auto.

## ANTI-PATTERNS (THIS PROJECT)

- Never `0.0.0.0` without `MCP_GWAY_ALLOW_REMOTE=1` + firewall/auth in front.
- Never string SQL/`eval`/shell injection — parameterized + Starlark sandbox only.
- Never rename `MCP_GWAY_ALLOW_LOCAL_COMMANDS`; never `*`/paths in it.
- Never direct-to-main, self-merge, or manual prod changes outside the pipeline.

## COMMANDS

```bash
mise run dev           # uv sync --all-groups + pre-commit install
mise run test          # uv run pytest -v (CI parity)
mise run lint          # uv run ruff check src/ tests/
mise run format-check  # uv run ruff format --check src/ tests/
mise run ci            # lint + format-check + test
```

## NOTES

- `CHANGELOG.md` hand-written; workflow reads it, never writes it.
- `uv.lock` + `package.json` version in lockstep via `bump-version --write`.
- Retired: legacy dashboard/catalog paths never served; stale `catalog.json` deleted manually.

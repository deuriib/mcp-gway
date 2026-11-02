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
src/mcp_gway/        # gateway core: cli/gateway/code_mode/sandbox/budget/registry/models
  domain/            # pure domain: models/policy/ports (zero framework/transport deps)
  application/       # use cases: manage_servers/execute_code/proxy_tool/gateway_status
  infrastructure/    # adapters: filesystem/sandbox/policy/tokens & DI container
  core/              # transport/discovery/policy/parsing/install (no CLI deps)
  observability/     # logging/metrics/tracing/health (stdlib + Starlette)
  admin/             # htpy+htmx dashboard (loopback + CSRF, CSP in gateway.py)
tests/               # mirrors src/ layout; hermetic DNS stub in conftest.py
  architecture/      # AST boundary fitness tests enforcing hexagonal layer purity
  unit/              # hermetic domain & use-case tests with in-memory port doubles
skills/              # mcp-gway{-cli,-core,-mcp} agent skill surfaces
plugins/             # pi|antigravity|opencode host integrations (dirs kept)
scripts/             # bump-version.mjs (12 owned sync surfaces)
Dockerfile           # multistage: builder → test → runtime (+ dev); digests pinned
docker-compose.yml   # base service (runtime image, healthcheck, config volume)
docker-compose.{dev,staging,prod}.yml  # layered env overrides (Compose ≥ 2.24)
.dockerignore        # context filters (keeps tests/scripts/plugins for test stage)
.env.example         # documented env vars (no real secrets committed)
```

## WHERE TO LOOK

| Task | Location | Notes |
| Add/remove/refresh servers | `src/mcp_gway/cli.py`, `registry.py` | atomic `.json`+`.pyi`, last-write-wins |
| Hexagonal Domain & Ports | `src/mcp_gway/domain/` | pure entities, policy, typing.Protocol ports |
| Application Use Cases | `src/mcp_gway/application/` | orchestrates domain via ports (no I/O or web deps) |
| Adapters & DI Container | `src/mcp_gway/infrastructure/` | concrete port adapters, DI GatewayContainer |
| Serve transports | `src/mcp_gway/gateway.py:320-340` | http/sse routes differ, no fallback |
| Container build | `Dockerfile`, `docker-compose*.yml`, `.dockerignore` | multistage, digest-pinned, non-root uid 1000 |
| Code Mode tools | `src/mcp_gway/code_mode.py` | Five MCP meta-tools + host-side `call_many`; Starlark `sandbox.py` |
| Local allow-list | `src/mcp_gway/core/policy.py`, ADR-009 | `MCP_GWAY_ALLOW_LOCAL_COMMANDS`, no rename |
| Version/release | `scripts/bump-version.mjs`, `.github/workflows/release.yml` | push-to-master auto via semantic-release, pyproject is truth |
| Specs/ADRs | `docs/specs/` (10_design/12_adr/15_requirements/30_delivery/40_workspace/50_archive) | archived specs are history, not live |

## BOUNDARIES

- `serve` binds `127.0.0.1`; `0.0.0.0` needs `MCP_GWAY_ALLOW_REMOTE=1` or exit 2.
- Admin `/`, `/admin*` loopback-gated + per-process CSRF; OAuth values masked in views.
- No PII stores; tokens in `~/.config/mcp-gway/tokens/` (`0o600`).

## CODE MAP

- Entry: `mcp-gway = mcp_gway.cli:main` (`mgw` 1:1 alias); `serve --transport stdio|http|sse`.
- Architecture: Hexagonal (Ports & Adapters). Inward dependency arrows: `infrastructure -> application -> domain`.
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
mise run docker:build  # docker build --target runtime -t mcp-gway:local .
mise run docker:test   # build test stage + run pytest inside it (CI parity)
mise run docker:dev    # dev override: hot-reload via watchfiles + debugpy
```

## NOTES

- `CHANGELOG.md` hand-written; workflow reads it, never writes it.
- `uv.lock` + `package.json` + `package-lock.json` version in lockstep via `bump-version --write`.
- `package-lock.json` is committed: use `npm ci` for the host-plugin tree. CI never installs npm deps — the published artifact is the `files` list (plugins, skills, rules, `mcp.json`), and the gateway itself has zero npm dependencies.
- npm tree baseline (2026-10-31, lockfile v3): 0 critical, 0 high, 22 moderate. Every moderate advisory is `minimatch <11.0.1` or `glob <=14.0.1` reached through `@opencode/util` (bundled npm-CLI internals) and `@earendil-works/pi-coding-agent`; `npm audit` reports `fixAvailable: false` for all 22, and two of the direct parents are already at their latest published version. Do not refile as a repo bug — a fix requires upstream.
- Retired: legacy dashboard/catalog paths never served; stale `catalog.json` deleted manually.
- Container (OPS-03/OPS-06): runtime image is non-root (`uid 1000`), digest-pinned, and prod override enforces `read_only: true` + `cap_drop: [ALL]`. The container binds `0.0.0.0`, so `MCP_GWAY_ALLOW_REMOTE=1` is mandatory — the gateway exits 2 without it (fail-closed). Builder/test/dev stages use the official `ghcr.io/jdx/mise:*-debian` image (`mise install --locked` drives python/uv/node from `mise.toml` + `mise.lock`); the runtime copies only the relocatable CPython + `/opt/venv`. `.dockerignore` keeps `tests/`/`scripts/`/`plugins/` because the `test` stage's pytest suite reads them (see `tests/test_version_surfaces.py`).
- `tools/call` handlers are synchronous and may block (Starlark sandbox, fan-out join), so `gateway.py` must offload **every** tools/call with `asyncio.to_thread` — offloading only `executeTool` froze /health and /metrics for a whole batch (issue #50). Inside a batch, `_ACTIVE_CACHE` + `_ACTIVE_LOCKS` guarantee one upstream session per server; anything opened without a cache must be closed by `_call_tool_async` itself.
- Images: `release.yml`'s `image` job publishes `ghcr.io/deuriib/mcp-gway` on every release (`<version>`, `<major>.<minor>`, `<major>`, `latest`; provenance + SBOM attestations; digest printed in the run summary) and smoke-tests the pushed digest. Only `linux/amd64` is published — widening to arm64 needs a validated QEMU build first. `MCP_GWAY_PORT` (default 8080) sets the published host port.

# MCP Gateway

[![Tests](https://github.com/deuriib/mcp-gateway/actions/workflows/test.yml/badge.svg)](https://github.com/deuriib/mcp-gateway/actions/workflows/test.yml)
[![Release](https://github.com/deuriib/mcp-gateway/actions/workflows/release.yml/badge.svg)](https://github.com/deuriib/mcp-gateway/actions/workflows/release.yml)
[![PyPI version](https://badge.fury.io/py/mcp-gway.svg)](https://pypi.org/project/mcp-gway/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-gway?maxAge=300)](https://pypi.org/project/mcp-gway/)
[![License](https://img.shields.io/pypi/l/mcp-gway?maxAge=300)](https://pypi.org/project/mcp-gway/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PyPI Downloads](https://static.pepy.tech/badge/mcp-gway/month)](https://pepy.tech/project/mcp-gway)
[![MCP Protocol](https://img.shields.io/badge/MCP-Protocol-blue?logo=modelcontextprotocol)](https://modelcontextprotocol.io/)
[![Code Mode](https://img.shields.io/badge/Code%20Mode-Lazy%20Discovery-purple)](docs/code-mode.md)
[![Local-First Security](https://img.shields.io/badge/Local--First-Security-green)](docs/security.md)
[![Observability Built-in](https://img.shields.io/badge/Observability-Built--in-orange)](docs/observability.md)
[![Sponsor](https://img.shields.io/badge/♥-Sponsor-EC4899?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/deuriib)

> One endpoint for every MCP server your agent needs — fetch tool schemas on demand instead of loading everything upfront.

MCP Gateway aggregates multiple MCP servers behind a single headless HTTP/SSE endpoint. Its **Code Mode** exposes five MCP meta-tools (`listToolFiles`, `readToolFile`, `getToolDocs`, `executeTool`, `callManyTool`) so agents discover signatures lazily and fan out bounded parallel calls without leaving the MCP surface. The host-side Python `call_many` helper remains available for direct code use, but the MCP contract exposes `callManyTool` as the fifth meta-tool.

- **CLI:** `mcp-gway` (canonical) or `mgw` (alias)
- **Admin UI:** `mcp-gway serve --transport http` → [http://127.0.0.1:8080/](http://127.0.0.1:8080/)

## Why MCP Gateway

- **Fewer wasted tokens** — Agents fetch only the schemas they need, when they need them.
- **One connection to manage** — Add, remove, or refresh servers in a single registry; agents connect to one endpoint.
- **Safe local-first defaults** — Binds to `127.0.0.1` by default, screens local commands via an allowlist, masks secrets, and CSRF-protects the admin dashboard.

## Who It's For

- **Agent developers** wiring Pi, Antigravity, Claude Desktop, Cursor, or any MCP-compatible client to multiple MCP servers through one gateway.
- **Operators** running local-first infrastructure who want a CLI and dashboard with health probes, Prometheus metrics, and structured JSON logs.

## Quick Start

1. **Install**: `pip install mcp-gway`
2. **Add a server**: `mcp-gway add files --type local --command "npx -y @modelcontextprotocol/server-filesystem /path/to/dir"`
3. **List servers**: `mcp-gway list`
4. **Serve HTTP**: `mcp-gway serve --transport http`
5. **Connect**: Point your agent to `http://127.0.0.1:8080/mcp`

For more examples and transports, see the [CLI Reference](docs/cli.md) and [Integrations](docs/integrations.md).

## Features

- **Multi-Server Aggregation** — Connect to multiple MCP servers (local or remote) and expose them through a single endpoint. One URL for every agent; one registry to manage.
- **Code Mode** — Five MCP meta-tools let LLMs discover schemas on demand, execute them in a hermetic sandbox, and fan out bounded parallel calls without loading all tool definitions upfront.
- **OAuth 2.0 Support** — Built-in OAuth flow with Dynamic Client Registration (RFC 7591), secure token storage, and automated `/.well-known/oauth-protected-resource` discovery metadata (RFC 8707) for OAuth-capable MCP clients.
- **Hexagonal Architecture** — Strict separation between pure domain models/ports, application use cases, and infrastructure adapters for isolated unit testability without running servers.
- **Hermetic Sandbox** — Starlark-based sandbox for safe, constrained code execution.
- **MCP Protocol Compliant** — Implements the Model Context Protocol over HTTP, SSE, and stdio.
- **Local-First Security** — Local-first design with SSRF guards, command allow-lists, and CSRF protection.
- **Built-In Observability** — Structured JSON logs, Prometheus metrics, and health probes built in.

## Documentation

- [Configuration & Usage](docs/configuration.md) — add servers, transports, and OAuth
- [CLI Reference](docs/cli.md) — commands, options, and the admin dashboard
- [Code Mode](docs/code-mode.md) — lazy-discovery meta-tools and the sandbox
- [Security](docs/security.md) — local-first controls and command allow-lists
- [Observability](docs/observability.md) — JSON logs, Prometheus metrics, health probes
- [Integrations](docs/integrations.md) — Claude Desktop, Pi, Antigravity, OpenCode
- [Architecture](docs/architecture.md) — system diagram and transports
- [Development](docs/development.md) — tests, lint, and pre-commit

## Development

```bash
uv sync --all-groups
uv run pytest -v   # 690 tests
```

See [docs/development.md](docs/development.md) for checks, probes, and pre-commit.

## Container

The gateway ships as a multistage `Dockerfile` (`builder` → `test` → `runtime`, plus a
`dev` stage) with per-environment compose overrides. The builder, test and dev stages
use the official [`ghcr.io/jdx/mise`](https://ghcr.io/jdx/mise) `-debian` image and
install the toolchain (Python, uv, Node) from `mise.toml` + `mise.lock` — the same
single source of truth the local dev environment uses. Base images are pinned by
digest, and the runtime image runs as a non-root user (`uid 1000`) with a read-only
root filesystem in production. The runtime image is ~270 MB (trimmed standalone
CPython + a `--no-dev` virtualenv; `tests/` and dev tooling stay in the `test` stage).

```bash
mise run docker:build   # build the runtime image (mcp-gway:local)
mise run docker:test    # build the test stage and run pytest inside it
mise run docker:dev     # dev override: hot-reload via watchfiles + debugpy (5678)
```

Or with `docker compose` directly:

```bash
# Base (runtime image, local registry volume, port 8080)
docker compose up --build

# Development — source bind-mounted, hot-reloads on change
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Staging — tagged image, no source mounts
docker compose -f docker-compose.yml -f docker-compose.staging.yml up

# Production — pinned digest, read-only FS, all capabilities dropped
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Environment** — copy `.env.example` to `.env` and adjust. The container binds
`0.0.0.0` so the published host port is reachable, which requires the
`MCP_GWAY_ALLOW_REMOTE=1` opt-in; without it the gateway exits rather than exposing
itself (fail-closed). Secrets and OAuth tokens live in the named `mcp-gway-config`
volume (`~/.config/mcp-gway/` inside the container), never in env files
(OPS-04 / DENY-13). Per-server `environment` values can reference the gateway
process env with `{env:NAME}` — only the placeholder persists and the secret
resolves in the spawned child; see `docs/configuration.md`.

**Production hardening** — the `prod` override enforces `read_only: true`, drops all
Linux capabilities (`cap_drop: [ALL]`), sets `no-new-privileges`, and pins CPU/memory
limits. It runs whatever `${MCP_GWAY_IMAGE}` points at, defaulting to the locally built
`mcp-gway:local`; set it to a digest-pinned published image
(`ghcr.io/deuriib/mcp-gway:<tag>@sha256:<digest>`) before deploying. Front it with a
reverse proxy and auth before exposing it publicly.

**Published images** — every release pushes `ghcr.io/deuriib/mcp-gway` tagged
`<version>`, `<major>.<minor>`, `<major>`, and `latest`, with build provenance and an
SBOM attestation attached, then smoke-tests the pushed digest before finishing. The
digest to pin is printed in the release run summary. Only `linux/amd64` is published
today; build locally on other architectures.

**Debugging** — the `dev` override installs `debugpy` and publishes port `5678`. Attach
from your editor or run a one-off debug session with:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec mcp-gway \
  python -m debugpy --listen 0.0.0.0:5678 -m mcp_gway.cli serve --transport http --host 0.0.0.0 --port 8080
```

![Repobeats analytics](https://repobeats.com/deuriib/mcp-gway?theme=light&size=medium&period=30)

## License

[MIT](LICENSE)

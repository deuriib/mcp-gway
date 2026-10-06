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

> One endpoint for every MCP server your agent needs — fetch tool schemas on demand instead of loading everything upfront.

MCP Gateway aggregates multiple MCP servers behind a single headless HTTP/SSE endpoint. Its **Code Mode** exposes four meta-tools (`listToolFiles`, `readToolFile`, `getToolDocs`, `executeToolCode`) so agents discover signatures lazily and execute them in a hermetic Starlark sandbox.

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
- **Code Mode** — Four meta-tools let LLMs discover schemas on demand and execute them in a hermetic sandbox, avoiding the need to load all tool definitions upfront.
- **OAuth 2.0 Support** — Built-in OAuth flow with Dynamic Client Registration (RFC 7591) and secure token storage.
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
uv run pytest -v   # 647 tests
```

See [docs/development.md](docs/development.md) for checks, probes, and pre-commit.

## License

[MIT](LICENSE)

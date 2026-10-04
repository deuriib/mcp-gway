---
name: mcp-gway-cli
description: Operate the mcp-gway CLI (v4.0.0) — add/remove/update/list/inspect/refresh/serve plus Code Mode tools from the terminal. Use when managing servers or running the gateway from CI.
---

# mcp-gway CLI

Standalone Python CLI (`mcp-gway = "mcp_gway.cli:main"`, alias `mgw`). OpenCode format only.
Registry (`servers/*.json` + `servers/*.pyi`) is the single source of truth.

## Management commands

| Command | Signature (from `src/mcp_gway/cli.py`) |
|---------|----------------------------------------|
| `add` | `mcp-gway add <name> --type local\|remote [flags]` |
| `remove` | `mcp-gway remove <name>` (also deletes `tokens/<name>.json` + `<name>_client.json`) |
| `update` | `mcp-gway update <name> --tools <csv>` (`--tools` required) |
| `list` | `mcp-gway list` |
| `inspect` | `mcp-gway inspect <name>` (prints stored `.pyi` signatures) |
| `refresh` | `mcp-gway refresh [<name>] [--auth] [--oauth-port <port>]` |
| `serve` | `mcp-gway serve [--transport stdio\|http\|sse] [--host 127.0.0.1] [--port <port>]` — default stdio; `--host/--port` only with http/sse |
| `--version` | `mcp-gway --version` / `-v` — print the package version |

## `add` flags (14, `cli.py`)

`--type` (**required**, `local|remote`), `--url`, `--command` (ONE string, `shlex.split`),
`--tools` (default `"*"`), `--env KEY=VALUE` (repeatable), `--header KEY=VALUE`
(repeatable, remote only), `--oauth-client-id`, `--oauth-client-secret`,
`--oauth-scope`, `--timeout` (int ms, default `5000`), `--enabled/--no-enabled`
(default enabled), `--oauth-port` (int, default `8989`), `--cwd`,
`--retry-on-transport-error` (flag, default off — retry connect phase only, never the tool call).

```bash
mcp-gway add youtube --type remote --url https://api.example.com/mcp
mcp-gway add filesystem --type local --command "npx -y @anthropic/mcp-filesystem"
mcp-gway list
mcp-gway inspect Demo
mcp-gway refresh Demo
mcp-gway refresh Demo --auth
```

## `tools` — Code Mode in the terminal

Same four meta-tools as the gateway (`listToolFiles → readToolFile → getToolDocs → executeToolCode`),
same `CodeMode` class, no new execution path. See `mcp-gway-mcp` for the protocol view.

```bash
mcp-gway tools list [--binding server|tool]
mcp-gway tools read --server Demo [--tool ping] [--start-line 1 --end-line 40]
mcp-gway tools docs --server Demo --tool ping
mcp-gway tools exec --code 'result = Demo.ping()'
mcp-gway tools exec --file run.star [--timeout 10]
```

Rules: exactly one of `--code`/`--file` (both or neither → exit 2); missing
`--file` → exit 2; unknown server/tool or blocked Starlark → `Error: ...` + exit 1.
Local spawns obey `core/policy.py` — a denied command fails with the policy
message, never silently. Emits `_log_cli_event("tools_exec", …)` like other CLI writes.

## Guards — what does NOT exist

- `--type` accepts **only** `local|remote`. Legacy `http|stdio|sse|streamable-http` rejected by click.
- `--args` and `--docs-url` **do not exist**. For `local`, pass the full invocation as one `--command` string.
- Name rule (`models.py`): `^[A-Za-z_][A-Za-z0-9_]{0,63}$`, ASCII, no hyphens/spaces/path separators, not reserved (`con`, `prn`, `aux`, `nul`, `com1-9`, `lpt1-9`).

## Local-first security (see `mcp-gway-core`)

- `local` requires `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (CSV basenames, case-insensitive); unset/blank → `DEFAULT_ALLOW_LIST {npx,bunx,uvx,pipx}` (`core/policy.py:23`). `*`/paths denied + warn. No bypass exists. `--cwd` absolute. Denylisted env rejected.
- `remote --url` has an SSRF-guard (`models.py`): only `http|https`; private/loopback/link-local/reserved/multicast rejected.
- Secrets: never put real tokens in `--header` / `--oauth-client-secret` (shell history). Prefer `refresh <name> --auth`. Tokens live in `~/.config/mcp-gway/tokens/` (`0o600`).

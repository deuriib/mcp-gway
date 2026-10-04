---
name: mcp-gway-cli
description: Operate the mcp-gway CLI (v4.2.0) — add/remove/update/list/inspect/refresh/serve plus Code Mode tools from the terminal. Use when managing servers or running tool calls from CI/scripts.
---

# mcp-gway CLI

Standalone Python CLI (`mcp-gway = "mcp_gway.cli:main"`, alias `mgw` — 1:1 shortcut).
OpenCode format only. Registry (`servers/*.json` + `servers/*.pyi`) is the single source of truth.

> Windows note: set `PYTHONIOENCODING=utf-8` before any `--help` or piped output, or `click.echo` can crash with `UnicodeEncodeError` under `cp1252`.

Default habit: `refresh` a server before `exec`/`inspect` against it. A stale `.pyi` (e.g. `def web_search() -> dict` with no params) is almost always cache, not protocol — refresh re-discovers the real signature.

## add — register a server

`mcp-gway add <name> --type local|remote [flags]`

`--type` is **required** and accepts **only** `local|remote`. Legacy `http|stdio|sse|streamable-http` are rejected by click. There is no `--args` and no `--docs-url`: for `local`, pass the full invocation as ONE `--command` string (split internally via `shlex.split`).

| Flag | Effect | Default |
|------|--------|---------|
| `--type local\|remote` | Server kind (**required**) | — |
| `--url <url>` | Remote endpoint | required for `remote` |
| `--command "<cmd>"` | Local invocation, single string | required for `local` |
| `--tools <csv>` | Tool ACL filter | `"*"` (all) |
| `--env KEY=VALUE` | Local env var (repeatable) | — |
| `--header KEY=VALUE` | Remote HTTP header (repeatable, remote only) | — |
| `--cwd <path>` | Local working dir, must be absolute | — |
| `--timeout <ms>` | Connect timeout, int ms | `5000` |
| `--enabled / --no-enabled` | Enable/disable without removal | enabled |
| `--oauth-client-id / --oauth-client-secret / --oauth-scope` | Pre-registered OAuth | — |
| `--oauth-port <port>` | OAuth callback port | `8989` |
| `--retry-on-transport-error` | Retry once ONLY on transport/connect failure, never after the tool call starts (ADR-012) | off |

Names are normalized to PascalCase and must match `^[A-Za-z_][A-Za-z0-9_]{0,63}$` (ASCII, no hyphens/spaces/separators, not reserved `con/prn/aux/nul/com1-9/lpt1-9`).

```bash
# Remote — minimal
mcp-gway add youtube --type remote --url https://api.example.com/mcp

# Remote — headers + timeout + disabled at birth
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp \
  --header "Authorization=Bearer TOKEN" --timeout 10000 --no-enabled

# Remote — pre-registered OAuth (prefer refresh --auth for secrets, see below)
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp \
  --oauth-client-id ID --oauth-client-secret SECRET --oauth-scope "openid profile"

# Local — minimal (allow-list gated, see Guards)
mcp-gway add filesystem --type local --command "npx -y @modelcontextprotocol/server-filesystem /srv/data"

# Local — env + cwd + tool filter
mcp-gway add tools --type local --command "python -m my_mcp_server" \
  --env MY_VAR=value --env OTHER=123 --cwd /srv/mcp/workdir --tools "read,write"

# Local — retry connect-phase failures once
mcp-gway add flaky --type local --command "uvx my-mcp-server" --retry-on-transport-error
```

## remove — delete a server

`mcp-gway remove <name>` — deletes the registry entries AND `tokens/<name>.json` + `<name>_client.json`. Case-insensitive name resolution.

```bash
mcp-gway remove youtube        # removes server + stored tokens
mcp-gway remove Youtube        # same — names resolve case-insensitively
```

## update — change the tool filter

`mcp-gway update <name> --tools <csv>` (`--tools` **required**). Rewrites the ACL without re-discovering.

```bash
mcp-gway update youtube --tools "search,fetch"   # allow only these two
mcp-gway update youtube --tools "*"              # back to all tools
```

## list — show registered servers

`mcp-gway list` — table of `Name / Type / Tools`, with `(disabled)` suffix where applicable. Empty registry prints `No servers connected.`

```bash
mcp-gway list
# Name                 Type       Tools
# --------------------------------------
# Context7             REMOTE     2
# ParallelSearch       REMOTE     2
# Filesystem           LOCAL      8        (disabled)
```

## inspect — print the stored stub

`mcp-gway inspect <name>` — prints the stored `.pyi` signatures. Fast and offline, but shows cache: if params look wrong, `refresh` first, then `inspect` again.

```bash
mcp-gway inspect Context7
# def resolve_library_id(query: str, libraryName: str) -> dict: ...
# def query_docs(libraryId: str, query: str) -> dict: ...
```

## refresh — re-discover tools

`mcp-gway refresh [<name>] [--auth] [--oauth-port <port>]`

No `NAME` refreshes every server (`Refreshing N servers...`); disabled servers print `Skipping <name> (disabled)`. Non-canonical stems auto-rename to PascalCase (collision warns and keeps the original). Local spawns are allow-list gated; remote tries anonymous discovery first, OAuth fallback only when discovery comes back empty.

```bash
mcp-gway refresh                        # all servers
mcp-gway refresh Context7               # one server — re-discovers params
mcp-gway refresh supabase --auth        # force OAuth re-auth even with tokens
mcp-gway refresh supabase --auth --oauth-port 9999   # custom callback port
```

## serve — start the gateway

`mcp-gway serve [--transport stdio|http|sse] [--host 127.0.0.1] [--port 8080] [--log-level LEVEL] [--registry-dir PATH]`

Default `--transport stdio` (NDJSON JSON-RPC on stdin/stdout, logs → stderr). `--host/--port` ONLY with `http|sse` — passing them with stdio exits 2. `mcp-gway mcp` is a DEPRECATED hidden alias for `serve --transport stdio` (prints a deprecation notice, same loop). Full route table and protocol: see `mcp-gway-mcp`.

```bash
mcp-gway serve                                        # stdio (default, OpenCode local)
mcp-gway serve --transport http --port 8080           # binds 127.0.0.1
mcp-gway serve --transport sse --host 127.0.0.1 --port 8080
mcp-gway serve --transport http --port 8080 --log-level debug --registry-dir ./servers
MCP_GWAY_ALLOW_REMOTE=1 mcp-gway serve --transport http --host 0.0.0.0 --port 8080
```

## --version

`mcp-gway --version` / `mcp-gway -v` / `mgw --version` — prints `mcp-gway X.Y.Z`. Sync source: `pyproject.toml:project.version` + `src/mcp_gway/__init__.py:__version__`.

## tools — Code Mode in the terminal

Same four meta-tools as the gateway (`listToolFiles → readToolFile → getToolDocs → executeToolCode`), same `CodeMode` class, no new execution path. Protocol view: see `mcp-gway-mcp`.

```bash
mcp-gway tools list                          # servers/ + *.pyi per server
mcp-gway tools list --binding tool           # per-tool stubs: servers/<name>/<tool>.pyi
mcp-gway tools read --server Context7       # full stub for one server
mcp-gway tools read --server Context7 --tool resolve_library_id   # single-tool stub
mcp-gway tools read --server Demo --start-line 1 --end-line 40    # paged read
mcp-gway tools docs --server Context7 --tool resolve_library_id
```

`exec` runs Starlark and prints `{"result": …, "logs": […]}`. Exactly ONE of `--code`/`--file` (both or neither → exit 2); empty code → exit 2; unknown server/tool or blocked Starlark → `Error: …` + exit 1. Local spawns obey `core/policy.py` — denied commands fail with the policy message, never silently.

```bash
# Variant 1 — inline snippet (assign `result`)
mcp-gway tools exec --code 'result = Context7.resolve_library_id(query="react hooks", libraryName="react")'

# Variant 2 — script file (same sandbox, better for multi-line)
cat > run.star << 'EOF'
result = ParallelSearch.web_search(
  objective="Latest features in Python 3.13",
  search_queries=["Python 3.13 new features", "Python 3.13 changelog"])
EOF
mcp-gway tools exec --file run.star
mcp-gway tools exec --file run.star --timeout 10   # seconds, default 30

# Variant 3 — chain discovery → execution in one flow
mcp-gway refresh ParallelSearch && \
  mcp-gway tools read --server ParallelSearch && \
  mcp-gway tools exec --code 'result = ParallelSearch.web_fetch(urls=["https://docs.python.org/3.13/whatsnew/3.13.html"])'
```

## Guards — what does NOT exist

- `--type` accepts **only** `local|remote`. Legacy `http|stdio|sse|streamable-http` rejected by click.
- `--args` and `--docs-url` **do not exist**. For `local`, pass the full invocation as one `--command` string.
- Name rule (`models.py`): `^[A-Za-z_][A-Za-z0-9_]{0,63}$`, ASCII, no hyphens/spaces/path separators, not reserved (`con`, `prn`, `aux`, `nul`, `com1-9`, `lpt1-9`).

## Local-first security (see `mcp-gway-core`)

- `local` requires `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (CSV basenames, case-insensitive); unset/blank → `DEFAULT_ALLOW_LIST {npx,bunx,uvx,pipx}` (`core/policy.py:23`). `*`/paths denied + warn. No bypass exists. `--cwd` absolute. Denylisted env rejected.
- `remote --url` has an SSRF-guard (`models.py`): only `http|https`; private/loopback/link-local/reserved/multicast rejected.
- Secrets: never put real tokens in `--header` / `--oauth-client-secret` (shell history). Prefer `refresh <name> --auth`. Tokens live in `~/.config/mcp-gway/tokens/` (`0o600`).

# Security (Local-First Design)

- **Loopback by default** — Binds to `127.0.0.1`. To expose on non-loopback interfaces, set `MCP_GWAY_ALLOW_REMOTE=1`. Without opt-in, binding non-loopback will exit with code 2.
- **Secret hygiene** — Tokens and credentials are never logged or exposed in metrics responses.
- **Policy enforcement** — Local command allowlists, SSRF guards, and configurable policy boundaries.
- **Admin dashboard hardening** — Loopback-only interface with CSRF protection, CSP, and secure headers.
- **Transport safety** — Per-transport route enforcement returns `405` with `Allow`; clear auth boundaries and structured JSON logs.

```bash
# Secure default — loopback only
mcp-gway serve --transport http --port 8080   # binds 127.0.0.1

# Binding 0.0.0.0 requires explicit opt-in
MCP_GWAY_ALLOW_REMOTE=1 mcp-gway serve --transport http --host 0.0.0.0 --port 8080
# └─ log warning "server exposed on non-loopback host"
# Shield with a firewall + reverse-proxy auth: never expose 0.0.0.0 without both in front.

# Without opt-in → controlled error
mcp-gway serve --transport http --host 0.0.0.0
# Error: binding to non-loopback host '0.0.0.0' requires MCP_GWAY_ALLOW_REMOTE=1
# exit 2
```

## Local Commands — Dynamic Allow-List (feat-006)

> **Dynamic-no-static:** no hardcoded binaries. Operators allow-list once via env.

**Allow-list:** `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (CSV basenames; unset/blank → defaults `npx,bunx,uvx,pipx`); `*`/paths/invalid entries → deny + warn.

Recommended: `MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3,bunx"`.

```bash
# Allow-list (CSV basenames, `*` = invalid → deny + warn)
export MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3,bunx"
mcp-gway add fs --type local --command "npx -y @anthropic/mcp-filesystem" --cwd /srv/mcp/workdir
```

- CISO opt-in note: `bunx` is docs-recommended only (not a code default; empty allow-list still denies); opt-in only with pin + owner + 90-day re-gate; `bun` runtime stays out; denylist EXACT PATH,PATHEXT,SYSTEMROOT,COMSPEC,LD_PRELOAD,LD_LIBRARY_PATH,PYTHONPATH,PYTHONHOME,NODE_OPTIONS,NODE_PATH,NODE_EXTRA_CA_CERTS,NODE_TLS_REJECT_UNAUTHORIZED + PREFIXES DYLD_,NPM_CONFIG_,BUN_,UV_ + controlled PATH (`NODE_ENV` allowed, not denylisted); `*`, paths, and shell are prohibited.
- `unset` returns to allow-list mode.
- CLI `add`/`refresh` enforces the allow-list plus re-validation before persist.
- `cwd` must be absolute + real + `is_dir`, else `reason_code=invalid_cwd`. Env denylist (`PATH`, `LD_PRELOAD`, `PYTHONPATH`, …) → `reason_code=denied_env`.
- Spawn only resolved via PATH lookup (`shutil.which(basename)`); never `shell=True` / `cmd /c` / `sh -c`. Errors carry `reason_code` (`not_allowlisted`, `binary_not_found`, …).

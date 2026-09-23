# Migration Guide: Upgrading to v3.1.0 (admin dashboard)

**From Version:** v3.0.1
**To Version:** v3.1.0
**Release Date:** 2026-09-23
**Owner / Author:** engineering owner (admin-ui-3.1.0)
**Migration Severity:** Low — contract notes only; standard CLI/stdio/mcp setups need no change

**What changed:**

- `/` now serves the admin dashboard index (404 since v2.0.0); `/admin*` added; `/dashboard` + catalog remain 404. Anything probing `/` for 404 must update (`ADR-014`).
- CSP response header relaxes for the dashboard: `script-src` jsDelivr + cdn.tailwindcss.com (htmx SRI-pinned), `style-src 'unsafe-inline'`, `frame-ancestors 'none'`.
- Admin routes (`/admin*`) validate `Host` fail-closed — only `{127.0.0.1, localhost, ::1, [::1]}`; a proxy sending a LAN/DNS `Host` gets 403 (anti-DNS-rebinding). `/mcp`, probes, and stdio are unaffected.
- No registry schema, env var, or config-file changes. **Rollback:** `pip install mcp-gway==3.0.1` (full plan in `docs/specs/30_delivery/RELEASE_NOTES.md`).

---

# Migration Guide: Upgrading to v3.0.0 (historical)

**From Version:** v2.11.3
**To Version:** v3.0.0
**Release Date:** 2026-09-22
**Owner / Author:** engineering owner (SPEC-TRANSPORT-SEPARATION-001)
**Migration Severity:** Breaking

---

## Executive Summary

v3.0.0 stops serving both MCP transports from one process. In v2.x, `serve --transport http|sse` always exposed `GET /mcp` (SSE), `POST /mcp` (Streamable HTTP), and `POST /mcp/messages` together. Now each `--transport` value exposes exactly its own routes and nothing else. Standard setups (OpenCode `type: remote` with `POST /mcp`, or stdio) need **no change**. SSE-only clients must pair the gateway with `--transport sse`. Estimated effort: **<5 minutes** for standard setups.

---

## Breaking Changes Registry

| Area / Component | Previous Behavior (v2.11.3) | New Behavior (v3.0.0) | Associated SPEC | Impacted Domains |
|---|---|---|---|---|
| **`GET /mcp` under `--transport http`** | SSE stream served | `405` + `Allow: POST` + JSON `detail` | SPEC-TRANSPORT-SEPARATION-001 | engineering |
| **`POST /mcp/messages` under `--transport http`** | JSON-RPC alias served | `404` (route does not exist) | SPEC-TRANSPORT-SEPARATION-001 | engineering |
| **`POST /mcp` under `--transport sse`** | JSON-RPC served | `405` + `Allow: GET` | SPEC-TRANSPORT-SEPARATION-001 | engineering |
| **`Gateway(...)` constructor** | `(registry, host)` | `(registry, host, transport)` — unknown `transport` raises `ValueError` | SPEC-TRANSPORT-SEPARATION-001 | engineering |

Untouched: `stdio` (default) loop, probes (`/health`, `/ready`, `/live`, `/metrics`), registry format, `add/remove/list/inspect/refresh` CLI, OAuth, local-first host gating.

---

## Step-by-Step Upgrade Instructions

### Step 1: Identify your client's transport

```bash
# Streamable-HTTP client (posts JSON-RPC to /mcp) — unaffected:
curl -s -X POST http://127.0.0.1:8080/mcp -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# SSE client (opens a stream on /mcp) — needs --transport sse:
curl -sN http://127.0.0.1:8080/mcp   # v3.0.0 on http mode → 405 Allow: POST
```

### Step 2: Upgrade the package

```bash
pip install --upgrade mcp-gway        # or: uv tool upgrade mcp-gway
```

### Step 3: Pair the gateway with your client

```bash
# SSE-only clients (legacy HTTP+SSE transport):
mcp-gway serve --transport sse --host 127.0.0.1 --port 8080

# Streamable-HTTP clients (unchanged):
mcp-gway serve --transport http --host 127.0.0.1 --port 8080

# stdio (default, unchanged):
mcp-gway serve
```

### Step 4: Post-Upgrade Verification

```bash
curl -s http://127.0.0.1:8080/health          # {"status":"ok"} on both transports
curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST http://127.0.0.1:8080/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'   # 200 (http) / 405 (sse, expected)
uv run pytest -q                              # contributors: 570 passed
```

---

## Rollback & Downgrade Plan

1. **Pin the previous version:** `pip install mcp-gway==2.11.3` (restores the dual-app contract exactly).
2. **Or revert the release:** `git revert <merge-commit>` — no persisted state, registry schema, env vars, or config files changed (verified by risk review; recovery <10 min).
3. **Restart the gateway** and re-run Step 4 verification.

---

## Release-Time Migration Guide Checklist

- [x] Every breaking change cited in `RELEASE_NOTES.md` has a corresponding section here.
- [x] Before/After examples are syntactically valid (curl + CLI commands).
- [x] Downgrade/Rollback instructions verified reversible (version pin + git revert; no state touched).
- [x] Migration guide linked from `README.md` and `RELEASE_NOTES.md`.

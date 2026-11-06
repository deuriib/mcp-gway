# Configuration & Usage

## Config format

Server config schema — `remote` / `local` with transport auto-detection. This is the recommended path.

```bash
# Remote — auto-detects transport (streamable-http → sse → http)
mcp-gway add youtube --type remote --url https://api.example.com/mcp
# SSRF-guard: private/loopback/link-local hosts rejected (src/mcp_gway/models.py:301-540); localhost only in tests.

# Remote with headers
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp --header "Authorization=Bearer TOKEN"

# Remote with pre-registered OAuth
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp --oauth-client-id ID --oauth-client-secret SECRET --oauth-scope "openid profile"

> **Shell-history warning:** never pass real secrets via `--header` / `--oauth-client-secret` (they persist in shell history and process lists). Prefer `mcp-gway refresh <name> --auth` or short-lived env vars.

# Remote with timeout and enable toggle
mcp-gway add api --type remote --url https://api.example.com/mcp --timeout 10000 --enabled
mcp-gway add api --type remote --url https://api.example.com/mcp --timeout 10000 --no-enabled

# Local
mcp-gway add filesystem --type local --command "npx -y @anthropic/mcp-filesystem"
mcp-gway add tools --type local --command "python -m my_mcp_server" --env MY_VAR=value --cwd /path/to/workdir
mcp-gway add tools --type local --command "npx -y my-mcp" --env KEY=VALUE --env OTHER=123 --cwd /srv/mcp/workdir

# List and serve (local-first)
mcp-gway list
mcp-gway serve --transport http --port 8080         # binds 127.0.0.1 by default
mcp-gway serve --transport http --host 127.0.0.1 --port 8080
curl -s http://127.0.0.1:8080/health | jq
```

## Admin dashboard refresh

The dashboard polls itself with htmx. One variable controls every polling
surface (status footer and the server-detail tools panel):

| Variable | Default | Effect |
|----------|---------|--------|
| `MCP_GWAY_ADMIN_REFRESH_SECONDS` | `5` | Whole seconds between refreshes. `0` disables polling and renders `auto-refresh off`. Non-integer or negative values make `serve` exit 2, naming the variable. |

The value is resolved once at `serve` startup, so a change requires a restart.
Interval copy uses `5s`, `30s`, or `10m` for whole minutes.

## Server Types (only `remote` / `local`)

`--type` only accepts `local|remote` (`cli.py:97-102`). Legacy values `http|stdio|sse|streamable-http` are rejected by click, and `--args` / `--docs-url` do not exist. For `local`, `--command` is a single string (split via `shlex`).

## OAuth Authentication

For servers requiring OAuth (e.g., Supabase):

```bash
# Trigger the OAuth flow (preferred — keeps secrets out of shell history)
mcp-gway refresh supabase --auth

# Or store a token manually (fallback only; chmod 600 required)
mkdir -p ~/.config/mcp-gway/tokens
echo '{"access_token": "YOUR_TOKEN"}' > ~/.config/mcp-gway/tokens/supabase.json
chmod 600 ~/.config/mcp-gway/tokens/supabase.json
```

### OAuth from the dashboard

Every remote server exposes **Authenticate** on the Servers list and the server
detail page, including servers added without client credentials — those use
dynamic client registration (RFC 7591). The flow runs in the background: the
status next to the button moves from `authenticating` to `authenticated` or
`auth failed`, and the tools panel picks up the discovered tools on its next
poll.

Refresh never blocks on the browser. If discovery returns `401`, Refresh now
says the server requires OAuth and points at Authenticate; a timeout or a
refused connection is reported as such instead of the old generic "no tools".

The callback port is per server (`oauth_port`, default `8989`): set it in the
add form or in **Edit config** when that port is busy. Tokens and DCR client
info persist under `~/.config/mcp-gway/tokens/` with `0600`.

### OAuth credentials and token lifecycle

A configured `clientId`/`clientSecret` is sent to the authorization server
byte-for-byte, including non-UUID IDs (`rlwy_...`, `gh_...`). Dynamic client
registration (RFC 7591) runs only when no client ID is configured; persisted
DCR client info is reused when its redirect URIs still match the current
callback URL. If an older version fabricated a UUID `clientId` for a server,
clear that field in **Edit config** so registration can run again.

The token file carries `expires_at`. A stored token is reused while valid. When
it expires, the next **Authenticate** (or `refresh --auth`) refreshes it with
the stored refresh token (same `resource`, same client auth) and persists the
result without opening a browser. If refresh fails, the stale token is
discarded and the full authorization-code flow runs instead. Tool calls
themselves do not refresh: if calls start returning `401`, click Authenticate
once to renew the token.

### Probing the authorization endpoint

Verify a server accepts the built authorization URL without logging in:

```bash
uv run python scripts/probe_oauth_authorize.py \
  --server-url https://mcp.railway.com/mcp \
  --client-id YOUR_PUBLIC_CLIENT_ID
```

The probe prints the naive and merged authorization URLs, then `status=` and
`location=`. It exits `0` only for a `3xx` that redirects to a
login/interaction page **without** an `error=` parameter. A `3xx` or `400`
carrying `error=` exits `1` and prints `failure=<error>` plus the sanitized
description. It performs no token exchange, opens no browser, and takes no
secret. Use `--naive` to probe the unmerged URL, `--auth-endpoint` to replay a
recorded endpoint shape, and `--scope`, `--redirect-uri`, or `--resource` to
override the discovered values.

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

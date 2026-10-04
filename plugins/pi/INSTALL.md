# mcp-gateway — Pi Installation Guide

> *"Haces las cosas como para Dios, por eso trabajas con excelencia y dedicación."*

The Pi integration wires **mcp-gway** into the [Pi coding agent](https://github.com/earendil-works/pi) so it behaves like it does in OpenCode and Antigravity:

1. **Gateway MCP registration** — `.mcp.json` at the repo root registers the local gateway over loopback. Pi's MCP adapter discovers it automatically.
2. **Gateway Protocol card** — `.pi/extensions/mcp-gateway.ts` injects the mandatory `gateway_*` call order into the system prompt of every run, deduped by the `MCP-GWAY v4.2.0` marker.
3. **Compression survival** — Pi re-enters the agent loop after compaction (threshold, overflow recovery, retries), so re-applying the card at the start of every run keeps the protocol available without duplicate cards.
4. **Bundled skills** — `skills/mcp-gway*` (`mcp-gway`, `mcp-gway-cli`, `mcp-gway-mcp`, `mcp-gway-core`) are loaded through the `pi` key in `package.json`.

The card text is read from `rules/mcp-gway.md` at runtime — the same source the Antigravity plugin uses, so the harnesses cannot drift apart.

---

## Prerequisites

- Node 20+ (Pi loads `.ts` extensions via `jiti`; no build step).
- `pi-mcp-adapter` installed:
  ```bash
  pi install npm:pi-mcp-adapter
  ```
- A running gateway over loopback:
  ```bash
  mcp-gway serve --transport http --host 127.0.0.1 --port 8080
  curl -s http://127.0.0.1:8080/health
  # Expected: {"status": "ok", ...}
  ```

---

## Installation

The repository is already a Pi package — install it as a local source:

```bash
# From the repo root, in the workspace you want the gateway available in
pi install ./mcp-gway
```

Or load it for a single invocation without persisting anything:

```bash
pi -e ./
```

Project packages load only after project trust is granted. Pi reads `package.json` declarations from `.pi/settings.json` when you install with `--local`:

```bash
pi install ./mcp-gway -l
```

### What `package.json` declares

```json
{
  "pi": {
    "extensions": ["./.pi/extensions/"],
    "skills": ["./skills/"]
  }
}
```

---

## Configuration

| Variable | Effect | Default |
|---|---|---|
| `MCP_GWAY_URL` | Override the gateway endpoint | `http://127.0.0.1:8080/mcp` |
| `MCP_GWAY_TOKEN` | Bearer token for the gateway | unset (no auth header) |

`.mcp.json` holds only the loopback URL — never a token. To authenticate, prefer the adapter's env-bound field so the secret never touches the file:

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://127.0.0.1:8080/mcp",
      "directTools": true,
      "requestTimeoutMs": 5000,
      "auth": "bearer",
      "bearerTokenEnv": "MCP_GWAY_TOKEN"
    }
  }
}
```

---

## Verification

1. **Extension loads** — the extension injects the card via a prompt section and never throws. Run the unit suite:
   ```bash
   node --experimental-strip-types tests/pi_extension.test.mjs
   # Expected: ALL GREEN
   ```
2. **Card injection** — start Pi in this repo and confirm no `mcp-gateway:` warning appears on stderr. The extension logs `[mcp-gateway] ...` only when `rules/mcp-gway.md` cannot be read or injection is skipped.
3. **MCP surface** — in Pi run `/mcp-adapter status`, or ask the agent to list gateway tools. You should see the `gateway_*` meta-tools.
4. **Protocol is live** — the Gateway Protocol card (four numbered steps starting with `gateway_listToolFiles`) is present in the system prompt.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `[mcp-gateway] could not read rules/mcp-gway.md` | Extension copied without the repo's `rules/` dir | Keep `rules/mcp-gway.md` next to the package, or accept the embedded fallback card |
| Gateway tools missing | `mcp-gway serve` not running, or wrong port | Start the gateway; check `MCP_GWAY_URL` |
| Duplicate cards in prompt | Two extensions injecting (e.g. this one plus another) | Remove the duplicate — the card is keyed and deduped by marker within this extension |
| Card present but agent ignores the order | System prompt replaced by another handler | Check that no other extension sets `forceSystemPrompt` |

---

## How the pieces map

| Concern | OpenCode | Antigravity | Pi |
|---|---|---|---|
| MCP registration | `ctx.mcp.transform()` in plugin | `mcp_config.json` (remote `serverUrl`) | `.mcp.json` (adapter-discovered) |
| Protocol card | `MARKER`-deduped system text | `rules/mcp-gway.md` | `rules/mcp-gway.md` read at runtime |
| Compression survival | `chat.params` / `systemHasRules` + `pushRules` | `hooks.json` → `scripts/reinject.mjs` | `before_agent_start` (re-enters loop after compaction) |
| Skill surface | `skills/` | `skills/mcp-gway` | `skills/` via the `pi` key |

The `pi` key does **not** use runtime `registerMcpServer()`: that API forces `directTools: false` (proxy-only) and throws when the server name already exists, which would both downgrade and break a pre-existing `gateway` registration. The declarative `.mcp.json` is the supported path.
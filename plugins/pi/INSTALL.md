# mcp-gateway — Pi Installation Guide

> *"Haces las cosas como para Dios, por eso trabajas con excelencia y dedicación."*

The Pi integration wires **mcp-gway** into the [Pi coding agent](https://github.com/earendil-works/pi) so it behaves like it does in other hosts and Antigravity:

1. **Gateway MCP registration** — declarative via repo-root `mcp.json` (`gateway` over stdio: `uvx mcp-gway serve` — loopback by construction, no TCP surface). The extension never calls `pi.registerMcpServer`. A same-named server in a user's project `mcp.json` still takes precedence.
2. **Gateway Protocol card** — `.pi/extensions/mcp-gateway.ts` injects the mandatory `gateway_*` call order into the system prompt of every run, deduped by the `MCP-GWAY v4.6.2` marker.
3. **Compression survival** — Pi re-enters the agent loop after compaction (threshold, overflow recovery, retries), so re-applying the card at the start of every run keeps the protocol available without duplicate cards.
4. **Meta-tools** — `gw_list`, `gw_read`, `gw_docs`, `gw_exec`, `gw_add`, `gw_remove` (model-callable tools via `pi.registerTool`) shell out to `mcp-gway tools list|read|docs|exec` and `mcp-gway add|remove` — the same CodeMode operations as the `gateway_*` MCP tools — for discovery without a gateway round-trip. `gw_add` exposes no OAuth flags: add OAuth-backed servers from a real terminal, not via the tool.
5. **Session inventory** — on `session_start` the extension probes `uvx --version` first (missing `uv` notifies with the install URL and skips inventory), then runs `mcp-gway tools list` once and publishes the server list as hidden context (`display: false`), so the agent knows which servers are available from the first turn. Requires `uv` on PATH.
6. **Bundled skills** — `skills/mcp-gway*` (`mcp-gway`, `mcp-gway-cli`, `mcp-gway-mcp`, `mcp-gway-core`) are loaded through the `pi` key in `package.json`.

The card text is read from `rules/mcp-gway.md` at runtime — the same source the Antigravity plugin uses, so the harnesses cannot drift apart.

---

## Prerequisites

- Node 22+ (Pi loads `.ts` extensions via `jiti`; no build step).
- `uvx mcp-gway` on PATH (the extension spawns `uvx mcp-gway serve` over stdio; no port, no separate daemon).

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

No imperative registration — `gateway` is declared in repo-root `mcp.json` (`command: "uvx"`, `args: ["mcp-gway", "serve"]`), shipped in the `files` whitelist in `package.json`. No token, no URL, no port. Prerequisite: `uv` (`uvx`) on PATH; without it the extension notifies at session start with the install URL and skips inventory until you reload (`/reload`) or reopen Pi.

---

## Verification

1. **Extension loads** — the extension injects the card via a prompt section and never throws. Run the unit suite:
   ```bash
   node --experimental-strip-types tests/pi_extension.test.mjs
   # Expected: ALL GREEN
   ```
2. **Card injection** — start Pi in this repo and confirm no `mcp-gateway:` warning appears on stderr. The extension logs `[mcp-gateway] ...` only when `rules/mcp-gway.md` cannot be read or injection is skipped.
3. **MCP surface** — in Pi run `/mcp`, or ask the agent to list gateway tools. You should see the `gateway_*` meta-tools.
4. **Protocol is live** — the Gateway Protocol card (four numbered steps starting with `gateway_listToolFiles`) is present in the system prompt.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `[mcp-gateway] could not read rules/mcp-gway.md` | Extension copied without the repo's `rules/` dir | Keep `rules/mcp-gway.md` next to the package, or accept the embedded fallback card |
| Gateway tools missing | `uvx mcp-gway` not on PATH | Install `mcp-gway` so `uvx mcp-gway serve` resolves |
| `mcp-gateway: Gateway Protocol card not injected` (omp) | `oh-my-pi` emits `before_agent_start` without `systemPromptOptions` | Update to the version with the `systemPrompt` return-value fallback — the card is returned as a prompt override instead of a section |
| Card present but agent ignores the order | System prompt replaced by another handler | Check that no other extension sets `forceSystemPrompt` |

---

## How the pieces map

| Concern | Other hosts | Pi |
|---|---|---|
| MCP registration | agent config (remote `serverUrl`) | declarative `mcp.json` (`uvx mcp-gway serve`) |
| Protocol card | `MARKER`-deduped system text | `rules/mcp-gway.md` read at runtime |
| Compression survival | `hooks.json` → `scripts/reinject.mjs` | `before_agent_start` (re-enters loop after compaction) |
| Skill surface | `skills/mcp-gway` | `skills/` via the `pi` key |
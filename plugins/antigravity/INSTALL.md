# mcp-gateway — Antigravity Plugin Installation Guide

> *"Haces las cosas como para Dios, por eso trabajas con excelencia y dedicación."*

The Antigravity plugin integrates **mcp-gateway** with Google Antigravity (CLI, IDE, and Antigravity 2.0). It provides:
1. **Automatic MCP Server Registration**: Connects to the local gateway at `http://127.0.0.1:8080/mcp` over loopback.
2. **Gateway Protocol Guidance**: Injects mandatory calling rules (`gateway_listToolFiles` → `gateway_readToolFile` → `gateway_executeToolCode`) and Starlark calling conventions via `rules/AGENTS.md`.
3. **Session Reinjection**: PreInvocation hook (`scripts/reinject.sh`) ensures the Gateway Protocol survives conversation compaction without duplication (deduped by `MCP-GWAY v2.8.0` marker).
4. **Bundled CLI Skill**: Automatically exposes the `mcp-gway` skill.

---

## Prerequisites

- Antigravity CLI, IDE, or Antigravity 2.0.
- Running `mcp-gway` gateway over loopback:
  ```bash
  mcp-gway serve --transport http --host 127.0.0.1 --port 8080
  ```
- Verify gateway health:
  ```bash
  curl -s http://127.0.0.1:8080/health
  # Expected: {"status": "ok", ...}
  ```

---

## Installation Options

### Option A: Project-Specific (Workspace) Installation

Install into your repository so any Antigravity agent working in this project has the plugin active:

```bash
mkdir -p <your-workspace>/.agents/plugins/mcp-gateway
cp -r plugins/antigravity/* <your-workspace>/.agents/plugins/mcp-gateway/
chmod +x <your-workspace>/.agents/plugins/mcp-gateway/scripts/reinject.sh
```

### Option B: Global Machine Installation

Install into your user configuration to enable it across all Antigravity workspaces:

```bash
mkdir -p ~/.gemini/config/plugins/mcp-gateway
cp -r plugins/antigravity/* ~/.gemini/config/plugins/mcp-gateway/
chmod +x ~/.gemini/config/plugins/mcp-gateway/scripts/reinject.sh
```

---

## Verification Matrix

1. **Verify Plugin Discovery**:
   In your Antigravity session, check available plugins:
   The plugin `mcp-gateway` is discovered from `.agents/plugins/` or `~/.gemini/config/plugins/`.

2. **Verify Skill Auto-Load**:
   The `mcp-gway` skill is present and callable for gateway CLI commands.

3. **Verify MCP Server Connectivity**:
   Inspect active MCP servers in Antigravity. The `gateway` server is registered at `http://127.0.0.1:8080/mcp`.

4. **Verify Gateway Protocol In Context**:
   In any fresh session, the Gateway Protocol marker is present:
   `<!-- MCP-GWAY v2.8.0 -->`

5. **Verify Compaction Survival**:
   As conversation history compacts or progresses, the `PreInvocation` hook ensures the protocol card remains active without duplicating if already present in transcript.

---

## Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| Gateway unreachable (`Connection refused`) | Gateway server not running on port 8080 | Run `mcp-gway serve --transport http --port 8080` |
| Hook script fails / not executed | Missing execute permission on `reinject.sh` | Run `chmod +x <plugin_dir>/scripts/reinject.sh` |
| MCP tools not appearing in agent context | Non-loopback host or wrong URL | Verify `mcp_config.json` points to `http://127.0.0.1:8080/mcp` |
| Duplicate protocol messages in chat | Transcript path mismatch | Hook uses `transcriptPath` from Antigravity input to check for existing marker |

---

## Rollback

To uninstall the plugin:
- For workspace: `rm -rf <your-workspace>/.agents/plugins/mcp-gateway`
- For global: `rm -rf ~/.gemini/config/plugins/mcp-gateway`

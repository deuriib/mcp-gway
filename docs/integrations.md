# Integrations

## Connect card

The dashboard's Overview page renders a **Connect** card with the live endpoint
and copy-paste recipes for Claude Code, OpenCode V2 and Antigravity. The URL is
derived from the request host, so it reflects the port you actually opened;
for `--transport sse` the card shows `GET /mcp` plus `POST /mcp/messages`.

OpenCode and Antigravity point at the plugins in this repo — both register the
gateway themselves, so no raw remote-server entry is needed.

## Connect from Claude Desktop

Add the gateway to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

> **Transport note:** Routes are transport-specific.
> - `serve --transport http`: `POST /mcp` only
> - `serve --transport sse`: `GET /mcp` and `POST /mcp/messages` only
>
> A mispaired client receives a `405` response with an `Allow` header indicating the correct methods. For upgrade notes, see [CHANGELOG.md](../CHANGELOG.md).

## Plugins

Editor/agent plugins live under `plugins/`, each with its own install guide:

- [Pi plugin](../plugins/pi/INSTALL.md)
- [Antigravity plugin](../plugins/antigravity/INSTALL.md)
- [OpenCode plugin](../plugins/opencode/INSTALL.md)

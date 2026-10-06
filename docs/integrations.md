# Integrations

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

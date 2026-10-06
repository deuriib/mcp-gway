<!-- MCP-GWAY v4.5.4 -->
## MCP Rules — Gateway Protocol

All MCP tools run via `gateway_*` helpers. **Mandatory order:**

1. `gateway_listToolFiles` — discover servers
2. `gateway_readToolFile` — read `servers/<Name>.pyi` stub for exact tool names + params
3. `gateway_getToolDocs` (optional) — full docs when stub is truncated
4. `gateway_executeToolCode` — run Starlark: `Server.tool(param=value)`

> **Parallel:** Step 1 first. Steps 2-4 can run concurrently across servers/tools.

### Calling Convention (Starlark)

```python
result = Server.tool(param=value, params....)
value = result["key"]  # brackets, not dot
```

- Sync only, keyword args, no `try/except`, no classes, no imports.
- Each `executeToolCode` scope is fresh — re-fetch or persist via MCP.

### Anti-Patterns

| Anti-Pattern                            | Fix                                       |
| :-------------------------------------- | :---------------------------------------- |
| Guessing tool names                     | Stub from `readToolFile` is authoritative |
| Skipping `listToolFiles`                | Always discover first when unsure         |
| `executeToolCode` before `readToolFile` | Confirm signature first                   |
| Assuming cross-call state               | Every call is isolated                    |

## MCP RULES

- For mcps not listed in your context, use gateway mcp instead, to list and execute mcp tools, this is no negotiable.

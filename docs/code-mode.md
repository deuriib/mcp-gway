# Code Mode

Code Mode exposes four meta-tools for lazy discovery, allowing agents to find and execute tools without loading all schemas into context.

| Tool                | Description                                         |
| ------------------- | --------------------------------------------------- |
| `gateway_listToolFiles`   | Discover available server stubs (`.pyi`)         |
| `gateway_readToolFile`    | Read exact tool names and parameters from a stub  |
| `gateway_getToolDocs`     | Fetch full documentation if the stub is truncated (optional) |
| `gateway_executeToolCode` | Execute in a hermetic Starlark sandbox            |

## Discovery Flow (Recommended)

1. `gateway_listToolFiles` — Discover available servers.
2. `gateway_readToolFile` — Read the `.pyi` stub for exact tool names and parameters.
3. `gateway_getToolDocs` (optional) — Fetch full docs if needed.
4. `gateway_executeToolCode` — Run Starlark: `Server.tool(param=value)`

> **Parallelization:** Run step 1 first. Steps 2–4 can run concurrently across servers/tools.

## Calling Convention (Starlark)

```python
result = Server.tool(param=value, params...)
value = result["key"]  # Use bracket access, not dot notation
```

## Constraints

- Synchronous only; use keyword arguments.
- No `try/except`, classes, or imports.
- Each execution scope is fresh — re-fetch or persist via MCP.
- Use stubs from `readToolFile` as the source of truth for signatures.

## Usage Example

```python
result = Server.filesystem.read_file(path="/tmp/example.txt")
content = result["content"]
```

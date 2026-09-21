#!/bin/sh
# reinject.sh — Gateway Protocol reinject for Antigravity PreInvocation hook.
#
# stdin:  JSON hook input (expects a "transcriptPath" field per /docs/hooks).
# argv:   optional $1 transcript path override (takes precedence over stdin).
# stdout: JSON hook output — {"injectSteps": []} when the MARKER card is
#         already present in the transcript, otherwise:
#         {"injectSteps": [{"ephemeralMessage": ...}]}.
#
# Hardening: grep -F with quoted "$MARKER" and "--" end-of-flags; no
# eval, no network, no file writes — stdout only. No secrets read or emitted.
set -eu

MARKER='MCP-GWAY v2.8.0'

TRANSCRIPT=''
if [ "${1:-}" != '' ]; then
    TRANSCRIPT="$1"
elif [ ! -t 0 ]; then
    INPUT=$(cat)
    # Extract transcriptPath via sed or python3
    TRANSCRIPT=$(printf '%s' "$INPUT" | sed -n 's/.*"transcriptPath"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
fi

CARD='<!-- MCP-GWAY v2.8.0 -->
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

## MCP Rules

- For mcps not listed in your context, use gateway mcp instead, to list and execute mcp tools, this is no negotiable.
'

if [ "$TRANSCRIPT" != '' ] && [ -f "$TRANSCRIPT" ] && grep -F -q -- "$MARKER" "$TRANSCRIPT"; then
    printf '%s\n' '{"injectSteps": []}'
    exit 0
fi

ESCAPED=$(printf '%s' "$CARD" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk '{if (NR>1) printf "\\n"; printf "%s", $0}')
printf '{"injectSteps": [{"ephemeralMessage": "%s"}]}\n' "$ESCAPED"

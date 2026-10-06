# Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MCP Gateway v4.0.0                          │
├──────────────────────────────────────────────────────────────────────┤
│  CLI (click)              │  Gateway (Starlette + uvicorn, CSP)      │
│  - add remote/local       │  - POST /mcp (JSON-RPC)      [http]      │
│  - remove/inspect/list    │  - GET  /mcp (SSE endpoint event)  [sse] │
│  - refresh --auth         │  - POST /mcp/messages (alias) [sse]      │
│  - serve --host 127.0.0.1 │  - GET  /health                          │
│  (local-first default)    │  - GET  /ready, /live, /metrics           │
├──────────────────────────────────────────────────────────────────────┤
│  Code Mode (4 meta-tools)      │  Starlark Sandbox                    │
│  - listToolFiles               │  - Hermetic execution                │
│  - readToolFile                │  - Server injection                  │
│  - getToolDocs                 │                                      │
│  - executeToolCode             │                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Registry (single source)      │  OAuth2 (RFC 7591, reused)           │
│  - servers/*.pyi = signatures  │  - Dynamic registration              │
│  - servers/*.json = config     │  - PKCE + FileTokenStorage           │
│  - last-write-wins, atomic     │  - tokens/ never exposed via API     │
└──────────────────────────────────────────────────────────────────────┘
         │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │ Server1 │      │ Server2 │      │ Server3 │
    │ (remote)│      │ (local) │      │ (remote)│
    └─────────┘      └─────────┘      └─────────┘
```

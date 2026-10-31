# Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MCP Gateway v4.10.2                           │
├──────────────────────────────────────────────────────────────────────┤
│  CLI (click)              │  Gateway (Starlette + uvicorn, CSP)      │
│  - add remote/local       │  - POST /mcp (JSON-RPC)      [http]      │
│  - remove/inspect/list    │  - GET  /mcp (SSE endpoint event)  [sse] │
│  - refresh --auth         │  - POST /mcp/messages (alias) [sse]      │
│  - serve --host 127.0.0.1 │  - GET  /health                          │
│  (local-first default)    │  - GET  /ready, /live, /metrics           │
├──────────────────────────────────────────────────────────────────────┤
│  Application Layer (Use Cases)                                        │
│  - ManageServersUseCase   │  ExecuteCodeUseCase                      │
│  - ProxyToolCallUseCase   │  GatewayStatusUseCase                    │
├──────────────────────────────────────────────────────────────────────┤
│  Domain Layer (Pure Business Core & Ports)                           │
│  - MCPServerConfig, ToolInfo, OAuthConfig, PolicyDecision            │
│  - ServerRegistryPort     │  ExecutionSandboxPort                    │
│  - McpProxyPort           │  TokenStoragePort, PolicyEnforcerPort    │
│  (Zero dependencies on web frameworks or transport libraries)         │
├──────────────────────────────────────────────────────────────────────┤
│  Infrastructure Layer (Adapters & DI Container)                      │
│  - FilesystemRegistryAdapter  │  StarlarkSandboxAdapter              │
│  - FileTokenStorageAdapter    │  LocalPolicyEnforcerAdapter          │
│  - GatewayContainer (DI wiring)                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Code Mode (5 MCP meta-tools)  │  Starlark Sandbox                    │
│  - listToolFiles               │  - Hermetic execution                │
│  - readToolFile                │  - Server injection                  │
│  - getToolDocs                 │                                      │
│  - executeTool                 │                                      │
│  - callManyTool                │                                      │
│  Python helper: call_many (host-side; not an MCP tool)                │
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

## Hexagonal Architecture (Ports and Adapters)

mcp-gway enforces a strict hexagonal architectural boundary:

1. **Domain Layer (`src/mcp_gway/domain/`)**:
   - Contains pure business entities, configuration schemas (`MCPServerConfig`, `ToolInfo`, `OAuthConfig`), policy rules (`validate_command_syntax`, `check_environment`), and abstract port protocols (`typing.Protocol`).
   - Pure domain rule: zero imports of web frameworks (`fastapi`, `starlette`) or transport libraries (`mcp`). Guaranteed by automated AST boundary verification (`tests/architecture/test_hexagonal_boundaries.py`).

2. **Application Layer (`src/mcp_gway/application/`)**:
   - Implements use cases orchestrating domain behavior: `ManageServersUseCase`, `ExecuteCodeUseCase`, `ProxyToolCallUseCase`, and `GatewayStatusUseCase`.
   - Depends strictly on abstract domain ports via constructor injection, enabling 100% isolated unit testability without opening sockets or starting servers (`tests/unit/test_domain_hexagonal.py`).

3. **Infrastructure Layer (`src/mcp_gway/infrastructure/`)**:
   - Implements adapters for external concerns:
     - `FilesystemRegistryAdapter`: atomic JSON storage and `.pyi` stub sync.
     - `StarlarkSandboxAdapter`: hermetic Starlark code execution.
     - `FileTokenStorageAdapter`: secure token persistence (`0o600`).
     - `LocalPolicyEnforcerAdapter`: local command execution allow-list validation.
   - Provides `GatewayContainer` for clean dependency injection and test stub swapping.

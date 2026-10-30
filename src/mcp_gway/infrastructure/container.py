"""Dependency Injection Container for hexagonal architecture.

Wires domain ports with concrete infrastructure adapters and exposes
instantiated application use cases. Supports constructor injection of
in-memory fakes for unit testing.
"""

from __future__ import annotations

from mcp_gway.application.use_cases import (
    ExecuteCodeUseCase,
    GatewayStatusUseCase,
    ManageServersUseCase,
)
from mcp_gway.domain.ports import (
    ExecutionSandboxPort,
    PolicyEnforcerPort,
    ServerRegistryPort,
    TokenStoragePort,
)
from mcp_gway.infrastructure.adapters.filesystem_registry import (
    FilesystemRegistryAdapter,
)
from mcp_gway.infrastructure.adapters.policy_adapter import (
    LocalPolicyEnforcerAdapter,
)
from mcp_gway.infrastructure.adapters.starlark_sandbox import (
    StarlarkSandboxAdapter,
)
from mcp_gway.infrastructure.adapters.token_storage import (
    FileTokenStorageAdapter,
)


class GatewayContainer:
    """Dependency container wiring adapters to ports and providing use cases."""

    def __init__(
        self,
        *,
        registry: ServerRegistryPort | None = None,
        sandbox: ExecutionSandboxPort | None = None,
        policy: PolicyEnforcerPort | None = None,
        tokens: TokenStoragePort | None = None,
    ) -> None:
        self.registry = (
            registry if registry is not None else FilesystemRegistryAdapter()
        )
        self.sandbox = sandbox if sandbox is not None else StarlarkSandboxAdapter()
        self.policy = policy if policy is not None else LocalPolicyEnforcerAdapter()
        self.tokens = tokens if tokens is not None else FileTokenStorageAdapter()

        # Application Use Cases wired to ports
        self.manage_servers = ManageServersUseCase(
            registry=self.registry,
            policy=self.policy,
        )
        self.execute_code = ExecuteCodeUseCase(sandbox=self.sandbox)
        self.gateway_status = GatewayStatusUseCase(registry=self.registry)

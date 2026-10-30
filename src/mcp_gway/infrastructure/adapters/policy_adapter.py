"""Policy adapter implementing PolicyEnforcerPort."""

from __future__ import annotations

from mcp_gway.domain.policy import (
    PolicyDecision,
    check_local_command,
)
from mcp_gway.domain.ports import PolicyEnforcerPort


class LocalPolicyEnforcerAdapter(PolicyEnforcerPort):
    """Adapter enforcing local command execution policies."""

    def __init__(
        self, *, host_loopback: bool = True, require_binary: bool = True
    ) -> None:
        self._host_loopback = host_loopback
        self._require_binary = require_binary

    def is_command_allowed(self, command: list[str]) -> bool:
        decision = self.check_command(command)
        return decision.allowed

    def check_command(self, command: list[str]) -> PolicyDecision:
        return check_local_command(
            command,
            host_loopback=self._host_loopback,
            require_binary=self._require_binary,
        )

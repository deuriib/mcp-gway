"""Starlark sandbox adapter implementing ExecutionSandboxPort."""

from __future__ import annotations

from typing import Any

from mcp_gway.domain.ports import ExecutionSandboxPort
from mcp_gway.sandbox import StarlarkSandbox


class StarlarkSandboxAdapter(ExecutionSandboxPort):
    """Adapter executing sandboxed code via Starlark engine."""

    def __init__(self, sandbox: StarlarkSandbox | None = None) -> None:
        self._sandbox = sandbox or StarlarkSandbox()

    def execute_code(
        self,
        code: str,
        *,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if context:
            for k, v in context.items():
                self._sandbox.set_global(k, v)

        actual_timeout = timeout if timeout is not None else 30.0
        result = self._sandbox.execute(code, timeout=actual_timeout)
        logs = self._sandbox.get_logs()
        return {
            "result": result,
            "logs": logs,
        }

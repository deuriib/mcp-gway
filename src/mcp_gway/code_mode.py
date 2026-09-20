"""Code Mode — 4 meta-tools for LLM-driven tool orchestration (Bifrost-aligned)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from mcp_gway.registry import Registry
from mcp_gway.sandbox import StarlarkSandbox
from mcp_gway.server_factory import ServerFactory

_VALID_BINDINGS = ("server", "tool")

# L1 Code Validation: Starlark has no imports/classes/file-IO/network.
# These patterns are rejected before execution with InvalidParams.
_BLOCKED_PATTERNS = (
    re.compile(r"^\s*import\s+", re.MULTILINE),
    re.compile(r"^\s*from\s+\S+\s+import\s+", re.MULTILINE),
    re.compile(r"^\s*class\s+\w+", re.MULTILINE),
)


def _validate_code(code: str) -> None:
    from mcp_gway.gateway import InvalidParamsError

    for rx in _BLOCKED_PATTERNS:
        if rx.search(code):
            raise InvalidParamsError(
                "executeToolCode rejects imports/classes [reason=code_validation]"
            )
    for token in ("open(", "__", "os.", "sys.", "subprocess", "socket."):
        if token in code:
            raise InvalidParamsError(
                f"executeToolCode rejects {token!r} (use MCP tools) "
                "[reason=code_validation]"
            )


_PASCAL_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")


def to_pascal_case_identifier(name: str) -> str:
    """Normalize a server name into a valid PascalCase Starlark identifier.

    Examples:
        'filesystem' -> 'Filesystem'
        'mcp-gateway_gateway' -> 'McpGatewayGateway'
        'my_server' -> 'MyServer'
        'server-1' -> 'Server1'
        '123server' -> '_123Server'
        'GITHUB' -> 'Github'
        'WEATHER_SERVICE' -> 'WeatherService'
        'myServer' -> 'MyServer'
        'AWS_S3' -> 'AwsS3'
    """
    if not name or not name.strip():
        return "_Server"
    # Split acronym boundaries: e.g. APIClient -> API Client
    clean = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    # Split camelCase boundaries: e.g. myServer -> my Server
    clean = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", clean)
    # Separate numeric runs
    clean = re.sub(r"([0-9]+)", r" \1 ", clean)
    clean = _PASCAL_SPLIT_RE.sub(" ", clean).strip()
    if not clean:
        return "_Server"
    words = clean.split()
    pascal = "".join(w.capitalize() for w in words)
    if not pascal:
        return "_Server"
    if pascal[0].isdigit():
        pascal = f"_{pascal}"
    return pascal


class CodeMode:
    def __init__(
        self,
        registry: Registry,
        binding_level: str = "server",
        tool_execution_timeout: float = 30.0,
        max_agent_depth: int = 10,
    ) -> None:
        if binding_level not in _VALID_BINDINGS:
            raise ValueError("binding_level must be 'server' or 'tool'")
        self.registry = registry
        self.binding_level = binding_level
        self.tool_execution_timeout = tool_execution_timeout
        self.max_agent_depth = max_agent_depth
        self.sandbox = StarlarkSandbox()
        self.server_factory = ServerFactory(registry)
        self._inject_tools()

    def _is_code_mode_server(self, name: str) -> bool:
        try:
            cfg = self.registry.get_config(name)
        except Exception:
            return False
        return bool(getattr(cfg, "is_code_mode_client", True))

    def _code_mode_servers(self) -> list[str]:
        return [n for n in self.registry.list() if self._is_code_mode_server(n)]

    def _inject_tools(self) -> None:
        """Inject MCP tool access into the sandbox.

        Adds:
        - Server structs for each CodeMode server with dual bindings
          (e.g., Filesystem.read_file(...) and backward-compatible filesystem.read_file(...)).
        """
        for server_name in self._code_mode_servers():
            try:
                struct = self.server_factory.make_server_struct(server_name)
                self.sandbox.inject_server(server_name, struct)
                cap_name = to_pascal_case_identifier(server_name)
                if cap_name != server_name:
                    self.sandbox.inject_server(cap_name, struct)
            except Exception as e:  # FEAT-007 (BR-114): degradation is visible
                self._record_skip(server_name, e)

    def _record_skip(self, server_name: str, exc: Exception) -> None:
        """FEAT-007 (BR-114): broken servers are skipped loudly, never silently.

        Emits a structured WARN and increments ``code_mode_servers_skipped_total``
        so a degraded registry is visible at a glance on /metrics.
        """
        logging.getLogger("mcp_gway.code_mode").warning(
            "code mode server skipped",
            extra={
                "server": server_name,
                "reason": "inject_error",
                "detail": f"{type(exc).__name__}: {exc}",
            },
        )
        metrics = getattr(self.sandbox, "_metrics", None)
        if metrics is not None:
            try:
                metrics.inc(
                    "code_mode_servers_skipped_total", {"reason": "inject_error"}
                )
            except Exception:
                # WHY narrow: telemetry must never break injection.
                pass

    def refresh(self) -> None:
        """Re-sync sandbox servers with the registry with automatic capitalization."""
        current_servers = self._code_mode_servers()
        # Build map of all active aliases -> original server_name
        current_aliases: dict[str, str] = {}
        for s in current_servers:
            current_aliases[s] = s
            cap = to_pascal_case_identifier(s)
            if cap != s:
                current_aliases[cap] = s

        known = set(self.sandbox._modules.keys())
        for gone in known - set(current_aliases.keys()):
            self.sandbox._modules.pop(gone, None)
        for name in list(
            known & set(self.registry.list()) - set(current_aliases.keys())
        ):
            self.sandbox._modules.pop(name, None)

        for name in current_servers:
            cap_name = to_pascal_case_identifier(name)
            needs_inject = (name not in self.sandbox._modules) or (
                cap_name != name and cap_name not in self.sandbox._modules
            )
            if needs_inject:
                try:
                    struct = self.server_factory.make_server_struct(name)
                    self.sandbox.inject_server(name, struct)
                    if cap_name != name:
                        self.sandbox.inject_server(cap_name, struct)
                except Exception as e:  # FEAT-007 (BR-114): degradation is visible
                    self._record_skip(name, e)

    def _tool_file_names(self, server: str) -> list[str]:
        """Sanitized per-tool file stems for tool-level VFS (callable names)."""
        try:
            tools = self.registry.get_pyi_tools(server)
        except Exception:
            return []
        try:
            cfg = self.registry.get_config(server)
            allow = getattr(cfg, "tools_to_execute", ["*"]) or ["*"]
        except Exception:
            allow = ["*"]
        names: list[str] = []
        for t in tools:
            safe = re.sub(r"[^A-Za-z0-9_]", "_", t.name)
            if safe and safe[0].isdigit():
                safe = f"_{safe}"
            if "*" in allow or t.name in allow or safe in allow:
                names.append(safe)
        return sorted(names)

    def list_tool_files(self, binding_level: str | None = None) -> str:
        level = binding_level or self.binding_level
        if level not in _VALID_BINDINGS:
            from mcp_gway.gateway import InvalidParamsError

            raise InvalidParamsError(
                "binding_level must be 'server' or 'tool' [reason=invalid_params]"
            )
        names = self._code_mode_servers()
        if not names:
            return "No servers connected."
        lines = ["servers/"]
        if level == "server":
            for name in names:
                lines.append(f"  {name}.pyi")
        else:
            for name in names:
                lines.append(f"  {name}/")
                for tool in self._tool_file_names(name):
                    lines.append(f"    {tool}.pyi")
        return "\n".join(lines)

    def _resolve_server(self, want: str) -> str:
        canonical = to_pascal_case_identifier(want)
        for name in self.registry.list():
            if name == canonical or name.lower() == want.lower():
                return name
        raise FileNotFoundError(f"Server '{want}' not found")

    def _resolve_tool(self, server: str, want: str) -> str:
        lowered = want.lower()
        try:
            tools = self.registry.get_pyi_tools(server)
        except Exception:
            raise FileNotFoundError(f"Server '{server}' not found") from None
        for t in tools:
            safe = re.sub(r"[^A-Za-z0-9_]", "_", t.name)
            if safe and safe[0].isdigit():
                safe = f"_{safe}"
            if t.name.lower() == lowered or safe.lower() == lowered:
                return t.name
        raise FileNotFoundError(f"Tool '{want}' not found on server '{server}'")

    def read_tool_file(
        self, fileName: str, startLine: int | None = None, endLine: int | None = None
    ) -> str:
        text = (fileName or "").strip()
        lowered = text.lower()
        if lowered.startswith("servers/"):
            text = text[len("servers/") :]
        if text.lower().endswith(".pyi"):
            text = text[: -len(".pyi")]
        text = text.strip().strip("/")
        if not text:
            from mcp_gway.gateway import InvalidParamsError

            raise InvalidParamsError(
                "readToolFile requires fileName [reason=invalid_params]"
            )
        parts = [p for p in text.split("/") if p]
        if len(parts) == 1:
            name = self._resolve_server(parts[0])
            content = self.registry.read_pyi(name)
        elif len(parts) == 2:
            name = self._resolve_server(parts[0])
            tool = self._resolve_tool(name, parts[1])
            content = self.registry.get_tool_docs(name, tool)
        else:
            from mcp_gway.gateway import InvalidParamsError

            raise InvalidParamsError(
                "readToolFile fileName must be servers/<server>.pyi or "
                "servers/<server>/<tool>.pyi [reason=invalid_params]"
            )
        if startLine is not None or endLine is not None:
            lines = content.splitlines()
            start = (startLine or 1) - 1
            end = endLine or len(lines)
            content = "\n".join(lines[start:end])
        return content

    def get_tool_docs(self, server: str, tool: str) -> str:
        name = self._resolve_server(server)
        actual_tool = tool
        try:
            actual_tool = self._resolve_tool(name, tool)
        except FileNotFoundError:
            pass
        return self.registry.get_tool_docs(name, actual_tool)

    def execute_tool_code(self, code: str, timeout: float | None = None) -> str:
        from mcp_gway.gateway import InvalidParamsError

        self.refresh()
        if not isinstance(code, str) or not code.strip():
            raise InvalidParamsError(
                "executeToolCode requires non-empty code [reason=invalid_params]"
            )
        _validate_code(code)
        result = self.sandbox.execute(
            code, timeout=timeout or self.tool_execution_timeout
        )
        logs = self.sandbox.get_logs()
        try:
            return json.dumps({"result": result, "logs": logs}, default=str)
        except Exception as e:
            raise RuntimeError(
                f"result serialization failed: {type(e).__name__}"
            ) from None

    # ── Bifrost Agent Mode ──────────────────────────────────────────────

    def classify_tool_calls(
        self, tool_calls: list[dict[str, object]]
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Bifrost Agent Mode: split tool calls into auto/manual buckets.

        Returns (auto_executable, manual) where each item is
        {"server": str, "tool": str, "arguments": dict, "id": str|None}.
        """
        auto: list[dict[str, object]] = []
        manual: list[dict[str, object]] = []
        for tc in tool_calls:
            server = str(tc.get("server", ""))
            tool = str(tc.get("tool", ""))
            if self.server_factory.is_auto_executable(server, tool):
                auto.append(tc)
            else:
                manual.append(tc)
        return auto, manual

    def execute_agent_tool(self, tc: dict[str, object]) -> Any:
        """Execute a single tool call (auto or manual) via MCP.

        Returns the raw MCP result dict.
        """
        server = str(tc.get("server", ""))
        tool = str(tc.get("tool", ""))
        arguments = dict(tc.get("arguments", {}))  # type: ignore[arg-type]
        config = self.registry.get_config(server)
        result = asyncio.run(
            self.server_factory._call_tool_async(config, tool, arguments)
        )
        return result

    def auto_execute(
        self, tool_calls: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Agent loop entry: auto-execute all auto-eligible tools, return results.

        Returns list of {"id", "server", "tool", "result"} for auto-executed
        calls. Non-auto calls are returned as-is in the manual list.
        """
        auto, _manual = self.classify_tool_calls(tool_calls)
        results: list[dict[str, object]] = []
        for tc in auto:
            try:
                result = self.execute_agent_tool(tc)
                results.append(
                    {
                        "id": tc.get("id"),
                        "server": tc.get("server"),
                        "tool": tc.get("tool"),
                        "result": result,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "id": tc.get("id"),
                        "server": tc.get("server"),
                        "tool": tc.get("tool"),
                        "error": {"type": type(e).__name__, "message": str(e)},
                    }
                )
        return results

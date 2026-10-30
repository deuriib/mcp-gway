"""Architectural Fitness Test (Hexagonal Architecture Boundary Verification).

Enforces Criterion 1:
Domain layer must have zero dependencies on `fastapi`, `starlette`, or `mcp` transport libs.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _extract_imported_modules(file_path: Path) -> set[str]:
    """Parse a python file with AST and return all top-level imported module names."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])

    return modules


def test_domain_layer_has_zero_framework_or_transport_dependencies() -> None:
    domain_dir = Path("src/mcp_gway/domain")
    assert domain_dir.is_dir(), "Domain directory must exist"

    forbidden_packages = {"fastapi", "starlette", "mcp"}
    domain_files = list(domain_dir.glob("*.py"))
    assert len(domain_files) >= 3, (
        f"Expected at least 3 domain files, found {len(domain_files)}"
    )

    violations: list[str] = []

    for py_file in domain_files:
        imported = _extract_imported_modules(py_file)
        forbidden_found = imported.intersection(forbidden_packages)
        if forbidden_found:
            violations.append(
                f"{py_file.name} violates hexagonal purity by importing: {forbidden_found}"
            )

    assert not violations, "\n".join(violations)


def test_domain_ports_are_protocols() -> None:
    from typing import Protocol

    from mcp_gway.domain.ports import (
        ExecutionSandboxPort,
        McpProxyPort,
        PolicyEnforcerPort,
        ServerRegistryPort,
        TokenStoragePort,
    )

    for port in (
        ServerRegistryPort,
        ExecutionSandboxPort,
        McpProxyPort,
        TokenStoragePort,
        PolicyEnforcerPort,
    ):
        assert issubclass(port, Protocol) or hasattr(port, "_is_protocol"), (
            f"{port} must be a Protocol"
        )

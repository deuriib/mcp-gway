from __future__ import annotations

import asyncio
import json

from click.testing import CliRunner

from mcp_gway import cli as C
from mcp_gway.admin import data as D
from mcp_gway.admin.pages.servers import server_row
from mcp_gway.code_mode import CodeMode
from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry


def _local(name: str, desc: str = "") -> MCPServerConfig:
    return MCPServerConfig(
        name=name, type="local", command=["npx", "-y", "pkg"], description=desc
    )


def test_model_description_defaults_and_normalizes() -> None:
    assert _local("A").description == ""
    assert _local("B", "  hello  ").description == "hello"
    assert len(_local("C", "x" * 600).description) == 500
    assert (
        MCPServerConfig(
            name="D", type="local", command=["npx"], description=None
        ).description
        == ""
    )


def test_registry_persists_description_and_rename_keeps_it(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Srv", "My desc"), [])
    assert (
        json.loads((reg.servers_dir / "Srv.json").read_text())["description"]
        == "My desc"
    )
    assert reg.get_config("Srv").description == "My desc"
    reg.rename("Srv", "Srv2")
    assert reg.get_config("Srv2").description == "My desc"


def test_registry_backward_compat_missing_description(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    (reg.servers_dir / "Old.json").write_text(
        '{"name":"Old","type":"local","command":["npx"],"enabled":true,"timeout":5000}'
    )
    (reg.servers_dir / "Old.pyi").write_text("# x")
    assert reg.get_config("Old").description == ""


def test_registry_pyi_header_description(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Srv", "Does things"), [ToolInfo(name="ping", description="Ping")])
    assert "# Description: Does things" in reg.read_pyi("Srv")
    reg2 = Registry(servers_dir=tmp_path / "servers2")
    reg2.add(_local("Bare"), [ToolInfo(name="ping", description="Ping")])
    assert "# Description:" not in reg2.read_pyi("Bare")


def test_code_mode_list_tool_files_shows_description(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Alpha", "Search stuff"), [ToolInfo(name="q", description="Q")])
    reg.add(_local("Bare"), [ToolInfo(name="q", description="Q")])
    cm = CodeMode(reg)
    server_listing = cm.list_tool_files("server")
    assert "Alpha.pyi" in server_listing and "Search stuff" in server_listing
    bare_line = next(line for line in server_listing.splitlines() if "Bare.pyi" in line)
    assert "#" not in bare_line
    tool_listing = cm.list_tool_files("tool")
    assert "Alpha/" in tool_listing and "Search stuff" in tool_listing


def test_code_mode_list_multiline_uses_first_line(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("M", "First line\nSecond line"), [])
    assert "First line" in CodeMode(reg).list_tool_files()
    assert "Second line" not in CodeMode(reg).list_tool_files()


def test_admin_rows_and_filter_include_description(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Alpha", "Search stuff"), [ToolInfo(name="q", description="Q")])
    rows = D.server_rows(reg)
    assert rows[0].description == "Search stuff"
    assert D.filter_rows(rows, "search")[0].name == "Alpha"
    assert D.filter_rows(rows, "alpha")[0].name == "Alpha"


def test_admin_row_renders_description_escaped(tmp_path) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Alpha", "<b>bold</b>"), [])
    html = str(server_row(D.server_rows(reg)[0]))
    assert "&lt;b&gt;" in html
    assert "<b>bold</b>" not in html


def test_cli_list_shows_description_second_line(tmp_path, monkeypatch) -> None:
    reg = Registry(servers_dir=tmp_path / "servers")
    reg.add(_local("Alpha", "Search stuff"), [ToolInfo(name="q", description="Q")])
    reg.add(_local("Bare"), [ToolInfo(name="q", description="Q")])
    monkeypatch.setattr("mcp_gway.cli._get_registry", lambda: reg)
    out = CliRunner().invoke(C.main, ["list"]).output
    assert "Search stuff" in out
    lines = out.splitlines()
    alpha_idx = next(i for i, line in enumerate(lines) if "Alpha" in line)
    assert "Search stuff" in lines[alpha_idx + 1]
    bare_idx = next(i for i, line in enumerate(lines) if "Bare" in line)
    assert "Search stuff" not in lines[bare_idx]


def test_resolve_server_description_manual_wins() -> None:
    from mcp_gway.core.client import resolve_server_description

    cfg = _local("S", "Manual")
    assert asyncio.run(resolve_server_description("Explicit", cfg)) == "Explicit"
    assert asyncio.run(resolve_server_description(None, cfg)) == "Manual"
    assert asyncio.run(resolve_server_description("   ", cfg)) == "Manual"


def test_fetch_server_description_fails_open() -> None:
    from mcp_gway.core.client import fetch_server_description

    cfg = MCPServerConfig(
        name="Nope", type="local", command=["definitely-not-a-binary-xyz"]
    )
    assert asyncio.run(fetch_server_description(cfg)) == ""

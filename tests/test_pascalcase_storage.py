"""SPEC-PASCALCASE-STORAGE-001 — canonical PascalCase storage tests.

REQ-F-001 → add canonicalization · REQ-F-002 → refresh auto-rename +
collision-skip · REQ-F-003 → Registry.rename unit tests ·
REQ-F-004 → refresh case-insensitive resolve · REQ-NF-001 → suite gate.
"""

from __future__ import annotations

from click.testing import CliRunner

from mcp_gway import cli as C
from mcp_gway.code_mode import to_pascal_case_identifier
from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry


def _registry(tmp_path, monkeypatch) -> Registry:
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir(exist_ok=True)
    reg = Registry(servers_dir=servers_dir)
    monkeypatch.setattr("mcp_gway.cli._get_registry", lambda: reg)
    return reg


def _local_add_env(monkeypatch) -> None:
    monkeypatch.setenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", "npx")
    monkeypatch.setattr(
        "mcp_gway.core.policy.resolve_binary", lambda basename: "/usr/bin/npx"
    )

    async def mock_discover(config, force_auth=False):
        return [ToolInfo(name="ping", description="Ping")]

    monkeypatch.setattr("mcp_gway.cli.discover_tools", mock_discover)
    monkeypatch.setattr("mcp_gway.core.discover_tools", mock_discover)


def _seed(reg: Registry, name: str) -> None:
    cfg = MCPServerConfig(
        name=name, type="local", command=["npx", "-y", "my-mcp"], enabled=True
    )
    reg.add(cfg, [ToolInfo(name="ping", description="Ping")])


# REQ-F-001 — normalizer
def test_to_pascal_case_variants() -> None:
    assert to_pascal_case_identifier("my-server") == "MyServer"
    assert to_pascal_case_identifier("my_server") == "MyServer"
    assert to_pascal_case_identifier("myServer") == "MyServer"
    assert to_pascal_case_identifier("Filesystem") == "Filesystem"
    assert to_pascal_case_identifier("GITHUB") == "Github"
    assert to_pascal_case_identifier("WEATHER_SERVICE") == "WeatherService"
    assert to_pascal_case_identifier("AWS_S3") == "AwsS3"
    assert to_pascal_case_identifier("weatherServiceApi") == "WeatherServiceApi"
    assert to_pascal_case_identifier("getHTTPResponse") == "GetHttpResponse"
    assert to_pascal_case_identifier("APIClient") == "ApiClient"
    assert to_pascal_case_identifier("123server") == "_123Server"
    assert to_pascal_case_identifier("server-1") == "Server1"
    assert to_pascal_case_identifier("") == "_Server"


# REQ-F-003 — Registry.rename
def test_registry_rename_moves_pair(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "my_server")
    reg.rename("my_server", "MyServer")
    assert (tmp_path / "servers" / "MyServer.json").exists()
    assert (tmp_path / "servers" / "MyServer.pyi").exists()
    assert not (tmp_path / "servers" / "my_server.json").exists()
    assert not (tmp_path / "servers" / "my_server.pyi").exists()
    assert reg.get_config("MyServer").name == "MyServer"
    assert "def ping(" in reg.read_pyi("MyServer")


def test_registry_rename_noop_equal(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "MyServer")
    reg.rename("MyServer", "MyServer")
    assert (tmp_path / "servers" / "MyServer.json").exists()


def test_registry_rename_missing(tmp_path, monkeypatch) -> None:
    import pytest

    reg = _registry(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError):
        reg.rename("ghost", "Ghost")


def test_registry_rename_collision(tmp_path, monkeypatch) -> None:
    import pytest

    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "my_server")
    _seed(reg, "MyServer")
    with pytest.raises(FileExistsError):
        reg.rename("my_server", "MyServer")
    assert (tmp_path / "servers" / "my_server.json").exists()
    assert (tmp_path / "servers" / "MyServer.json").exists()


# REQ-F-001 — cli add
def test_add_canonicalizes_local(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _local_add_env(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        C.main, ["add", "my_server", "--type", "local", "--command", "npx -y my-mcp"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "servers" / "MyServer.json").exists()
    assert (tmp_path / "servers" / "MyServer.pyi").exists()
    assert not (tmp_path / "servers" / "my_server.json").exists()


def test_add_already_canonical_noop(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _local_add_env(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        C.main, ["add", "Filesystem", "--type", "local", "--command", "npx -y my-mcp"]
    )
    assert result.exit_code == 0, result.output
    assert "Normalized" not in result.output
    assert (tmp_path / "servers" / "Filesystem.json").exists()


def test_add_collision_with_canonical(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _local_add_env(monkeypatch)
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(
        C.main, ["add", "my_server", "--type", "local", "--command", "npx -y my-mcp"]
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


# REQ-F-002 / REQ-F-004 — cli refresh
def _mock_refresh(monkeypatch):
    async def mock_refresh_server(cfg, srv_name, force_auth, oauth_port=8989):
        return [ToolInfo(name="ping", description="Ping")]

    monkeypatch.setattr("mcp_gway.cli.refresh_server", mock_refresh_server)


def test_refresh_renames_lowercase(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _mock_refresh(monkeypatch)
    from mcp_gway.registry import Registry as R

    reg = R(servers_dir=tmp_path / "servers")
    _seed(reg, "my_server")
    runner = CliRunner()
    result = runner.invoke(C.main, ["refresh"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "servers" / "MyServer.json").exists()
    assert not (tmp_path / "servers" / "my_server.json").exists()
    assert "Renamed" in result.output


def test_refresh_renames_tokens(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _registry(tmp_path, monkeypatch)
    _mock_refresh(monkeypatch)
    from mcp_gway.registry import Registry as R

    reg = R(servers_dir=tmp_path / "servers")
    _seed(reg, "my_server")
    tokens = tmp_path / ".config" / "mcp-gway" / "tokens"
    tokens.mkdir(parents=True)
    (tokens / "my_server.json").write_text('{"tok": "abc"}', encoding="utf-8")
    (tokens / "my_server_client.json").write_text('{"c": 1}', encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(C.main, ["refresh"])
    assert result.exit_code == 0, result.output
    assert (tokens / "MyServer.json").read_text(encoding="utf-8") == '{"tok": "abc"}'
    assert (tokens / "MyServer_client.json").exists()
    assert not (tokens / "my_server.json").exists()


def test_refresh_collision_skip(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _mock_refresh(monkeypatch)
    from mcp_gway.registry import Registry as R

    reg = R(servers_dir=tmp_path / "servers")
    _seed(reg, "my_server")
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(C.main, ["refresh"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "servers" / "my_server.json").exists()
    assert (tmp_path / "servers" / "MyServer.json").exists()
    assert "keeping original" in result.output


def test_refresh_case_insensitive_name(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _mock_refresh(monkeypatch)
    from mcp_gway.registry import Registry as R

    reg = R(servers_dir=tmp_path / "servers")
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(C.main, ["refresh", "myserver"])
    assert result.exit_code == 0, result.output
    assert "Refreshed MyServer" in result.output


# REQ-F-004 — case-insensitive CLI management commands
def test_remove_case_insensitive_and_delimiter(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(C.main, ["remove", "my-server"])
    assert result.exit_code == 0, result.output
    assert "Removed MyServer." in result.output
    assert not (tmp_path / "servers" / "MyServer.json").exists()


def test_inspect_case_insensitive_and_delimiter(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(C.main, ["inspect", "my_server"])
    assert result.exit_code == 0, result.output
    assert "def ping(" in result.output


def test_update_case_insensitive_and_delimiter(tmp_path, monkeypatch) -> None:
    reg = _registry(tmp_path, monkeypatch)
    _seed(reg, "MyServer")
    runner = CliRunner()
    result = runner.invoke(C.main, ["update", "myserver", "--tools", "pong"])
    assert result.exit_code == 0, result.output
    assert "Updated MyServer with 1 tools." in result.output
    assert "def pong(" in reg.read_pyi("MyServer")


# REQ-F-003 — refresh renames all-caps / UPPER_SNAKE stems
def test_refresh_renames_all_caps(tmp_path, monkeypatch) -> None:
    _registry(tmp_path, monkeypatch)
    _mock_refresh(monkeypatch)
    from mcp_gway.registry import Registry as R

    reg = R(servers_dir=tmp_path / "servers")
    _seed(reg, "GITHUB")
    runner = CliRunner()
    result = runner.invoke(C.main, ["refresh"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "servers" / "Github.json").exists()
    assert (tmp_path / "servers" / "Github.pyi").exists()
    # NOTE: on a case-insensitive FS `GITHUB.json` and `Github.json` are
    # the SAME directory entry — `os.listdir` is the ground truth.
    import os as _os

    listing = _os.listdir(tmp_path / "servers")
    assert "Github.json" in listing
    assert "GITHUB.json" not in listing
    assert "Renamed 'GITHUB' → 'Github'" in result.output

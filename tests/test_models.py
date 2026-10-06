"""Tests for MCP server config models."""

import pytest

from mcp_gway.models import MCPServerConfig, OAuthConfig


def test_remote_config_valid():
    config = MCPServerConfig(
        name="youtube",
        type="remote",
        url="https://mcp.example.com/mcp",
    )
    assert config.name == "youtube"
    assert config.type == "remote"
    assert config.url == "https://mcp.example.com/mcp"
    assert config.enabled is True
    assert config.timeout == 5000


def test_local_config_valid():
    config = MCPServerConfig(
        name="myserver",
        type="local",
        command=["npx", "-y", "my-mcp-server"],
    )
    assert config.type == "local"
    assert config.command == ["npx", "-y", "my-mcp-server"]


def test_local_requires_command():
    with pytest.raises(ValueError, match="command.*local|--command"):
        MCPServerConfig(name="myserver", type="local")


def test_remote_requires_url():
    with pytest.raises(ValueError, match="url.*remote|--url"):
        MCPServerConfig(name="myserver", type="remote")


def test_remote_with_headers():
    config = MCPServerConfig(
        name="myserver",
        type="remote",
        url="https://mcp.example.com/mcp",
        headers={"Authorization": "Bearer TOKEN"},
    )
    assert config.headers == {"Authorization": "Bearer TOKEN"}


def test_remote_with_oauth_object():
    cid = "550e8400-e29b-41d4-a716-446655440000"
    config = MCPServerConfig(
        name="myserver",
        type="remote",
        url="https://mcp.example.com/mcp",
        oauth=OAuthConfig(clientId=cid, clientSecret="secret"),
    )
    assert config.oauth.clientId == cid


def test_remote_with_oauth_false():
    config = MCPServerConfig(
        name="myserver",
        type="remote",
        url="https://mcp.example.com/mcp",
        oauth=False,
    )
    assert config.oauth is False


def test_local_with_environment():
    config = MCPServerConfig(
        name="myserver",
        type="local",
        command=["node", "server.js"],
        environment={"FOO": "bar", "BAZ": "qux"},
    )
    assert config.environment == {"FOO": "bar", "BAZ": "qux"}


def test_local_with_cwd():
    config = MCPServerConfig(
        name="myserver",
        type="local",
        command=["python", "-m", "server"],
        cwd="/path/to/workdir",
    )
    assert config.cwd == "/path/to/workdir"


def test_oauth_client_id_auto_uuid():
    import uuid

    cfg = MCPServerConfig(
        name="s", type="remote", url="https://x", oauth={"clientId": "not-a-uuid"}
    )
    assert cfg.oauth.clientId != "not-a-uuid"
    uuid.UUID(cfg.oauth.clientId)

    cfg2 = MCPServerConfig(
        name="s2", type="remote", url="https://x", oauth={"scope": "openid"}
    )
    assert cfg2.oauth.clientId is not None
    uuid.UUID(cfg2.oauth.clientId)


def test_oauth_client_id_valid_uuid_kept():
    import uuid

    cid = str(uuid.uuid4())
    cfg = MCPServerConfig(
        name="s3", type="remote", url="https://x", oauth=OAuthConfig(clientId=cid)
    )
    assert cfg.oauth.clientId == cid


def test_name_rejects_hyphens():
    with pytest.raises(ValueError, match="hyphens"):
        MCPServerConfig(name="my-tools", type="remote", url="https://x")


def test_name_rejects_leading_digit():
    with pytest.raises(ValueError, match="number"):
        MCPServerConfig(name="123tools", type="remote", url="https://x")


def test_name_rejects_non_ascii():
    with pytest.raises(ValueError, match="ASCII"):
        MCPServerConfig(name="café", type="remote", url="https://x")


def test_name_hyphen_human_message_no_pydantic_footer():

    from mcp_gway.models import format_validation_error

    try:
        MCPServerConfig(name="my-tools", type="remote", url="https://example.com/mcp")
        raise AssertionError("should have raised")
    except ValueError as e:
        msg = str(e)
        assert "underscores" in msg and "my_tools" in msg
        assert "errors.pydantic.dev" not in msg
        assert "^[A-Za-z" not in msg
        human = format_validation_error(e)
        assert human.startswith("name: ")
        assert "my_tools" in human
        assert "[reason=name_hyphens]" in human
        assert "errors.pydantic.dev" not in human


def test_https_only_human_message_keeps_token():
    from mcp_gway.models import format_validation_error

    try:
        MCPServerConfig(name="ok1", type="remote", url="http://example.com/mcp")
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "[reason=https_only]" in str(e)
        human = format_validation_error(e)
        assert "https://" in human
        assert "[reason=https_only]" in human


def test_format_validation_error_multi_error_lines():
    from pydantic import BaseModel, ValidationError

    from mcp_gway.models import format_validation_error

    class Two(BaseModel):
        a: int
        b: int

    try:
        Two(a="x", b="y")
        raise AssertionError("should have raised")
    except ValidationError as e:
        human = format_validation_error(e)
        lines = human.splitlines()
        assert len(lines) == 2
        assert lines[0].startswith("a: ") and lines[1].startswith("b: ")
        assert "errors.pydantic.dev" not in human

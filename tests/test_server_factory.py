"""Tests for ServerFactory — MCP tool bridge for sandbox."""

import pytest

from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry
from mcp_gway.server_factory import (
    ServerFactory,
    _bind_positional_arguments,
    _extract_result,
    _parse_signature_params,
)


@pytest.fixture
def registry(tmp_path):
    """Create a registry with a mock server."""
    reg = Registry(servers_dir=tmp_path / "servers")
    config = MCPServerConfig(
        name="youtube",
        type="remote",
        url="https://api.example.com/mcp",
    )
    tools = [
        ToolInfo(
            name="search",
            description="Search for videos",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        ToolInfo(
            name="get_video",
            description="Get video details",
            input_schema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        ),
    ]
    reg.add(config, tools)
    return reg


@pytest.fixture
def factory(registry):
    return ServerFactory(registry)


def test_get_tool_names(factory):
    """Should extract tool names from .pyi stub."""
    names = factory._get_tool_names("youtube")
    assert "search" in names
    assert "get_video" in names


def test_get_tool_names_not_found(factory):
    """Should raise FileNotFoundError for unknown server."""
    with pytest.raises(FileNotFoundError):
        factory._get_tool_names("nonexistent")


def test_make_server_struct(factory):
    """Should create a struct with tool methods."""
    struct = factory.make_server_struct("youtube")
    assert hasattr(struct, "search")
    assert hasattr(struct, "get_video")
    assert callable(struct.search)
    assert callable(struct.get_video)


def test_make_server_struct_not_found(factory):
    """Should raise FileNotFoundError for unknown server."""
    with pytest.raises(FileNotFoundError):
        factory.make_server_struct("nonexistent")


def test_extract_result_with_text():
    """Should extract text from MCP result with content."""

    class MockContent:
        def __init__(self, text):
            self.text = text

    class MockResult:
        def __init__(self, texts):
            self.content = [MockContent(t) for t in texts]

    result = _extract_result(MockResult(["hello", "world"]))
    assert result == "hello\nworld"


def test_extract_result_with_json():
    """Should parse JSON from MCP result text."""

    class MockContent:
        def __init__(self, text):
            self.text = text

    class MockResult:
        def __init__(self, text):
            self.content = [MockContent(text)]

    result = _extract_result(MockResult('{"key": "value"}'))
    assert result == {"key": "value"}


def test_extract_result_passthrough():
    """Should pass through non-MCP results."""
    result = _extract_result({"direct": "dict"})
    assert result == {"direct": "dict"}


def test_extract_result_without_content():
    """Should handle objects without content attribute."""

    class PlainResult:
        pass

    result = _extract_result(PlainResult())
    assert isinstance(result, PlainResult)


# --- Positional argument binding ---


def test_parse_signature_params_keeps_declared_order():
    line = "def search(query: str, limit: int = None) -> dict:  # Search"
    assert _parse_signature_params(line) == ("query", "limit")


def test_parse_signature_params_empty_signature():
    assert _parse_signature_params("def ping() -> dict:  # ping") == ()


def test_get_tool_signatures_keys_by_original_name(factory):
    signatures = factory._get_tool_signatures("youtube")
    assert signatures["search"] == ("query",)
    assert signatures["get_video"] == ("id",)


def test_bind_positional_arguments_maps_by_order():
    bound = _bind_positional_arguments("t", ("a", "b"), ("x",), {"c": 3})
    assert bound == {"a": "x", "c": 3}


def test_bind_positional_arguments_rejects_duplicate():
    with pytest.raises(TypeError, match="multiple values"):
        _bind_positional_arguments("t", ("a",), ("x",), {"a": "y"})


def test_bind_positional_arguments_rejects_overflow():
    with pytest.raises(TypeError, match="takes 1 positional"):
        _bind_positional_arguments("t", ("a",), ("x", "y"), {})


def test_struct_method_forwards_positional_arguments(factory, monkeypatch):
    captured = {}

    async def fake_call(config, tool_name, arguments):
        captured["tool"] = tool_name
        captured["arguments"] = arguments
        return {"ok": True}

    monkeypatch.setattr(factory, "_call_tool_async", fake_call)
    struct = factory.make_server_struct("youtube")
    assert struct.search("python") == {"ok": True}
    assert captured == {"tool": "search", "arguments": {"query": "python"}}


def test_struct_method_keeps_keyword_arguments(factory, monkeypatch):
    captured = {}

    async def fake_call(config, tool_name, arguments):
        captured["arguments"] = arguments
        return {"ok": True}

    monkeypatch.setattr(factory, "_call_tool_async", fake_call)
    struct = factory.make_server_struct("youtube")
    struct.get_video(id="abc")
    assert captured["arguments"] == {"id": "abc"}

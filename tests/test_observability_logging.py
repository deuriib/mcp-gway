from __future__ import annotations

import io
import json
import logging
import os
import stat

import pytest

from mcp_gway.observability import logging as obs
from mcp_gway.observability.logging import (
    JSONFormatter,
    request_id_ctx,
    sanitize_request_id,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _restore_gateway_handlers():
    """Drop handlers this test added so one test cannot leak into the next."""
    logger = logging.getLogger("mcp_gway")
    before = list(logger.handlers)
    yield
    for handler in list(logger.handlers):
        if handler not in before:
            logger.removeHandler(handler)
            handler.close()


def test_json_formatter_shape() -> None:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JSONFormatter())
    lg = logging.getLogger("mcp_gway.test.shape")
    lg.handlers = [h]
    lg.setLevel(logging.INFO)
    lg.propagate = False
    request_id_ctx.set("r-123")
    try:
        lg.info("hello")
        line = buf.getvalue().strip()
        data = json.loads(line)
        assert "timestamp" in data
        assert "level" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "mcp_gway.test.shape"
        assert data["message"] == "hello"
        assert data["request_id"] == "r-123"
        assert data["timestamp"].endswith("Z")
    finally:
        request_id_ctx.set(None)
        lg.handlers = []


def test_json_formatter_uses_extra_request_id_over_context() -> None:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JSONFormatter())
    lg = logging.getLogger("mcp_gway.test.extra")
    lg.handlers = [h]
    lg.setLevel(logging.INFO)
    lg.propagate = False
    request_id_ctx.set("ctx-id")
    try:
        lg.info("hello", extra={"request_id": "extra-id"})
        data = json.loads(buf.getvalue().strip())
        assert data["request_id"] == "extra-id"
    finally:
        request_id_ctx.set(None)
        lg.handlers = []


def test_json_formatter_includes_whitelisted_extras() -> None:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JSONFormatter())
    lg = logging.getLogger("mcp_gway.test.extras")
    lg.handlers = [h]
    lg.setLevel(logging.INFO)
    lg.propagate = False
    try:
        lg.info(
            "hello",
            extra={
                "method": "GET",
                "path": "/health",
                "status": 200,
                "duration_ms": 42,
            },
        )
        data = json.loads(buf.getvalue().strip())
        assert data["method"] == "GET"
        assert data["path"] == "/health"
        assert data["status"] == 200
        assert data["duration_ms"] == 42
    finally:
        lg.handlers = []


def test_sanitize_truncates_and_strips_crlf() -> None:
    assert "\n" not in sanitize_request_id("a\nb")
    assert "\r" not in sanitize_request_id("a\rb")
    assert len(sanitize_request_id("x" * 5000)) <= 64


def test_sanitize_filters_invalid_chars_and_respects_length() -> None:
    result = sanitize_request_id("a\nb\r\x00" + "x" * 5000)
    assert "\n" not in result
    assert "\r" not in result
    assert "\x00" not in result
    assert len(result) <= 64
    # must be allowed charset
    import re

    assert re.match(r"^[A-Za-z0-9_-]{1,64}$", result)


def test_sanitize_empty_returns_unknown() -> None:
    assert sanitize_request_id("") == "unknown"
    assert sanitize_request_id("---") == "unknown"


def test_setup_logging_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    setup_logging("info")
    setup_logging("info")

    logger = logging.getLogger("mcp_gway")
    stderr = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not getattr(handler, "_mcp_gway_file", False)
        and isinstance(handler.formatter, JSONFormatter)
    ]
    files = [h for h in logger.handlers if getattr(h, "_mcp_gway_file", False)]

    assert len(stderr) == 1
    assert len(files) == 1


def test_json_formatter_valid_json_per_line() -> None:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JSONFormatter())
    lg = logging.getLogger("mcp_gway.test.jsonline")
    lg.handlers = [h]
    lg.setLevel(logging.INFO)
    lg.propagate = False
    try:
        lg.info("line1")
        lg.warning("line2")
        lines = [line for line in buf.getvalue().strip().splitlines() if line]
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "level" in data
    finally:
        lg.handlers = []


# --- Persisted file logging ---


def _record_file_warnings(monkeypatch, sink: list[str]) -> None:
    def fake(message: str, *args: object, **kwargs: object) -> None:
        sink.append(message % args if args else message)

    monkeypatch.setattr(obs._LOGGER, "warning", fake)


def test_data_dir_honors_absolute_xdg(tmp_path, monkeypatch):
    from mcp_gway.domain.policy import data_dir, logs_dir

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    assert data_dir() == tmp_path / "xdg" / "mcp-gway"
    assert logs_dir() == tmp_path / "xdg" / "mcp-gway" / "logs"


def test_data_dir_ignores_relative_xdg(tmp_path, monkeypatch):
    from mcp_gway.domain.policy import data_dir

    monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert data_dir() == tmp_path / "home" / ".local" / "share" / "mcp-gway"


def test_setup_logging_writes_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    setup_logging("info")

    logging.getLogger("mcp_gway.test.file").info("hello-file")

    log_file = tmp_path / "xdg" / "mcp-gway" / "logs" / "gateway.log"
    assert log_file.exists()
    data = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert data["message"] == "hello-file"
    assert data["level"] == "INFO"
    assert data["logger"] == "mcp_gway.test.file"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_log_file_and_dir_modes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    setup_logging("info")
    logging.getLogger("mcp_gway.test.modes").info("x")

    log_dir = tmp_path / "xdg" / "mcp-gway" / "logs"
    log_file = log_dir / "gateway.log"
    assert stat.S_IMODE(log_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600


def test_file_logging_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("MCP_GWAY_LOG_TO_FILE", "0")

    setup_logging("info")
    logging.getLogger("mcp_gway.test.nofile").info("no file")

    logger = logging.getLogger("mcp_gway")
    assert not any(getattr(h, "_mcp_gway_file", False) for h in logger.handlers)
    assert not (tmp_path / "xdg" / "mcp-gway" / "logs").exists()


def test_log_dir_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom-logs"
    monkeypatch.setenv("MCP_GWAY_LOG_DIR", str(custom))

    setup_logging("info")
    logging.getLogger("mcp_gway.test.override").info("x")

    assert (custom / "gateway.log").exists()


def test_relative_log_dir_is_ignored(tmp_path, monkeypatch):
    warnings: list[str] = []
    _record_file_warnings(monkeypatch, warnings)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("MCP_GWAY_LOG_DIR", "relative/dir")

    setup_logging("info")
    logging.getLogger("mcp_gway.test.rel").info("x")

    assert any("relative MCP_GWAY_LOG_DIR ignored" in m for m in warnings)
    assert (tmp_path / "xdg" / "mcp-gway" / "logs" / "gateway.log").exists()


def test_unknown_log_to_file_value_keeps_default(tmp_path, monkeypatch):
    warnings: list[str] = []
    _record_file_warnings(monkeypatch, warnings)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("MCP_GWAY_LOG_TO_FILE", "maybe")

    setup_logging("info")

    assert any("unknown MCP_GWAY_LOG_TO_FILE value ignored" in m for m in warnings)
    logger = logging.getLogger("mcp_gway")
    assert any(getattr(h, "_mcp_gway_file", False) for h in logger.handlers)


def test_unwritable_log_dir_keeps_stderr_logging(tmp_path, monkeypatch):
    warnings: list[str] = []
    _record_file_warnings(monkeypatch, warnings)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    def boom(path):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(obs, "_build_file_handler", boom)

    setup_logging("info")
    logging.getLogger("mcp_gway.test.degraded").warning("still-alive")

    logger = logging.getLogger("mcp_gway")
    assert not any(getattr(h, "_mcp_gway_file", False) for h in logger.handlers)
    assert any("file logging disabled" in m for m in warnings)


def test_file_handler_rotation_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    setup_logging("info")

    handler = next(
        h
        for h in logging.getLogger("mcp_gway").handlers
        if getattr(h, "_mcp_gway_file", False)
    )
    assert handler.maxBytes == 10 * 1024 * 1024
    assert handler.backupCount == 5


def test_persisted_logs_never_contain_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("MCP_GWAY_LOG_LEVEL", "info")
    monkeypatch.setenv("MCP_GWAY_TOKEN", "super-secret-token-value")
    setup_logging("info")

    from mcp_gway.cli import _log_cli_event

    _log_cli_event("add", "success", server="alpha", detail="2 tools")

    content = (tmp_path / "xdg" / "mcp-gway" / "logs" / "gateway.log").read_text(
        encoding="utf-8"
    )
    assert "super-secret-token-value" not in content
    assert "cli add success" in content


def test_log_cli_event_persists_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    setup_logging("warning")

    from mcp_gway.cli import _log_cli_event

    _log_cli_event("remove", "failed", server="ghost", detail="not found")

    content = (tmp_path / "xdg" / "mcp-gway" / "logs" / "gateway.log").read_text(
        encoding="utf-8"
    )
    data = json.loads(content.strip().splitlines()[-1])
    assert data["message"] == "cli remove failed"
    assert data["action"] == "remove"
    assert data["status"] == "failed"
    assert data["server"] == "ghost"


@pytest.mark.parametrize("flag", ["--help", "--version"])
def test_cli_eager_flags_do_not_create_log_dir(tmp_path, monkeypatch, flag):
    from click.testing import CliRunner

    from mcp_gway.cli import main

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    result = CliRunner().invoke(main, [flag])

    assert result.exit_code == 0
    assert not (tmp_path / "xdg").exists()


def test_cli_group_initializes_file_logging(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from mcp_gway.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    result = CliRunner().invoke(main, ["list"])

    assert result.exit_code == 0
    logging.getLogger("mcp_gway.cli").warning("cli list probe")
    log_file = tmp_path / "xdg" / "mcp-gway" / "logs" / "gateway.log"
    assert log_file.exists()
    assert "cli list probe" in log_file.read_text(encoding="utf-8")

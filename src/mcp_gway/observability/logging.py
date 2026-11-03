from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from mcp_gway.domain.policy import logs_dir

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_SAN_RE = re.compile(r"[^A-Za-z0-9_-]")

LOG_FILE_NAME = "gateway.log"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_TO_FILE_ENV = "MCP_GWAY_LOG_TO_FILE"
LOG_DIR_ENV = "MCP_GWAY_LOG_DIR"

_FILE_MARKER = "_mcp_gway_file"
_ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})
_DISABLED_VALUES = frozenset({"0", "false", "no", "off"})

_LOGGER = logging.getLogger("mcp_gway.observability.logging")


class _PrivateRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that creates its file with mode 0o600 on POSIX.

    Rotation opens a fresh file through ``_open``; overriding it keeps the
    private mode instead of inheriting the process umask.
    """

    def _open(self) -> TextIO:
        fd = os.open(
            self.baseFilename,
            os.O_CREAT | os.O_APPEND | os.O_WRONLY,
            0o600,
        )
        return os.fdopen(
            fd,
            "a",
            encoding=self.encoding or "utf-8",
            errors=getattr(self, "errors", None),
        )


def sanitize_request_id(value: str) -> str:
    s = _SAN_RE.sub("-", value.strip())[:64]
    s = s.strip("-")
    return s if s else "unknown"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from mcp_gway.observability.tracing import get_tracer

        rid = getattr(record, "request_id", None)
        if rid is None:
            rid = request_id_ctx.get()
        tracer = get_tracer()
        trace_id = getattr(record, "trace_id", None) or tracer.current_trace_id()
        span_id = getattr(record, "span_id", None) or tracer.current_span_id()
        timestamp = (
            datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
        payload: dict[str, object] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": rid,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        for key in (
            "method",
            "path",
            "status",
            "duration_ms",
            "server",
            "tool",
            # FEAT-007: stdio access log (BR-108), CLI events (BR-109),
            # shutdown summary (BR-105) carry these on the record.
            "transport",
            "action",
            "reason",
            "detail",
            "uptime_seconds",
            "http_requests_total",
            "sessions_active",
            "sse_dropped_total",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def _level_from_str(level: str) -> int:
    mapping = {
        "trace": logging.DEBUG,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    return mapping.get(level.strip().lower(), logging.INFO)


def _file_logging_enabled() -> bool:
    """Read ``MCP_GWAY_LOG_TO_FILE``; unknown values keep the default (on)."""
    raw = os.environ.get(LOG_TO_FILE_ENV)
    if raw is None or not raw.strip():
        return True
    value = raw.strip().lower()
    if value in _ENABLED_VALUES:
        return True
    if value in _DISABLED_VALUES:
        return False
    _LOGGER.warning(
        "unknown %s value ignored",
        LOG_TO_FILE_ENV,
        extra={
            "reason": "invalid_env",
            "detail": f"{LOG_TO_FILE_ENV}={raw}",
        },
    )
    return True


def _resolve_log_file() -> Path:
    """Resolve the log file path, honoring an absolute ``MCP_GWAY_LOG_DIR``."""
    override = os.environ.get(LOG_DIR_ENV)
    if override and override.strip():
        candidate = Path(override.strip()).expanduser()
        if candidate.is_absolute():
            return candidate / LOG_FILE_NAME
        _LOGGER.warning(
            "relative %s ignored",
            LOG_DIR_ENV,
            extra={
                "reason": "invalid_env",
                "detail": f"{LOG_DIR_ENV}={override}",
            },
        )
    return logs_dir() / LOG_FILE_NAME


def _build_file_handler(log_file: Path) -> _PrivateRotatingFileHandler:
    directory = log_file.parent
    created = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if created and os.name == "posix":
        os.chmod(directory, 0o700)
    handler = _PrivateRotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(JSONFormatter())
    return handler


def _is_file_handler(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _FILE_MARKER, False))


def setup_logging(level: str) -> None:
    py_level = _level_from_str(level)
    logger = logging.getLogger("mcp_gway")
    logger.setLevel(py_level)
    logger.propagate = False

    stderr_handler = next(
        (
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and not _is_file_handler(handler)
            and isinstance(getattr(handler, "formatter", None), JSONFormatter)
        ),
        None,
    )
    if stderr_handler is None:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(JSONFormatter())
        logger.addHandler(stderr_handler)
    stderr_handler.setLevel(py_level)

    if _file_logging_enabled():
        desired = _resolve_log_file()
        file_handler = next(
            (handler for handler in logger.handlers if _is_file_handler(handler)),
            None,
        )
        if file_handler is not None and Path(file_handler.baseFilename) != desired:
            logger.removeHandler(file_handler)
            file_handler.close()
            file_handler = None
        if file_handler is None:
            try:
                file_handler = _build_file_handler(desired)
                setattr(file_handler, _FILE_MARKER, True)
                logger.addHandler(file_handler)
            except OSError as exc:
                # WHY broad: logging must never abort serve or a CLI command.
                _LOGGER.warning(
                    "file logging disabled",
                    extra={
                        "reason": "unwritable",
                        "detail": f"{desired}: {type(exc).__name__}",
                    },
                )
                file_handler = None
        if file_handler is not None:
            file_handler.setLevel(py_level)
    else:
        for handler in [h for h in logger.handlers if _is_file_handler(h)]:
            logger.removeHandler(handler)
            handler.close()

    for name in ("uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.setLevel(py_level)

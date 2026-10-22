"""Regression: a legacy console code page must not kill CLI output.

Windows redirects stdout through the ANSI code page (cp1252), which cannot
encode an arrow. Before the fix, `mcp-gway add` printed its normalization
notice and died with UnicodeEncodeError *after* writing the server.
"""

from __future__ import annotations

import io
import sys

import click

from mcp_gway import cli


def test_output_survives_a_strict_cp1252_stream(monkeypatch):
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    cli._harden_console_encoding()
    click.echo("normalized → done")
    stream.flush()

    assert buffer.getvalue().decode("cp1252").rstrip("\r\n") == "normalized ? done"


def test_hardening_tolerates_streams_that_cannot_reconfigure(monkeypatch):
    class _PlainStream:
        def write(self, text: str) -> int:
            return len(text)

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", _PlainStream())
    monkeypatch.setattr(sys, "stderr", _PlainStream())

    cli._harden_console_encoding()

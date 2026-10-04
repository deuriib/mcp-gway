"""Hermetic edge tests: allow-list / denylist / cwd / env."""

from __future__ import annotations

import pytest

from mcp_gway.core import policy as P


def test_allow_list_parsing(monkeypatch):
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "npx, uvx , python3")
    assert P.get_allow_list() == {"npx", "uvx", "python3"}
    # Empty string falls back to DEFAULT_ALLOW_LIST
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "")
    assert P.get_allow_list() == {"npx", "bunx", "uvx", "pipx"}
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "*, npx, /bin/x, .., bad!name, a/b\\c")
    assert P.get_allow_list() == {"npx"}
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "Npx")
    assert P.get_allow_list() == {"npx"}


@pytest.mark.parametrize(
    "command",
    [
        "notalist",
        [],
        ["a"] * 9,
        ["/bin/npx"],
        ["bad!bin"],
        ["npx", "a" * 81],
        ["npx", "a..b"],
        ["npx", "/"],
        ["npx", "a;b"],
        [123],
        ["npx", 123],
    ],
    ids=[
        "not-a-list",
        "empty",
        "too-many-tokens",
        "path-basename",
        "bad-basename",
        "arg-too-long",
        "dotdot",
        "slash",
        "semicolon",
        "non-string-basename",
        "non-string-arg",
    ],
)
def test_validate_command_syntax_edges(command):
    with pytest.raises(ValueError, match="reason=invalid_syntax"):
        P.validate_command_syntax(command)


def test_validate_command_syntax_ok():
    assert P.validate_command_syntax(["npx", "run"]) == "npx"


def test_check_local_command_branches(monkeypatch):
    d = P.check_local_command(None)
    assert d.reason_code == "invalid_syntax" and not d.allowed
    d = P.check_local_command(["bad!bin"])
    assert d.reason_code == "invalid_syntax"
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "")
    d = P.check_local_command(["somemissingbinary123"])
    assert not d.allowed and d.reason_code == "not_allowlisted"
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "npx")
    monkeypatch.setattr(P, "resolve_binary", lambda b: None)
    d = P.check_local_command(["npx"], require_binary=True)
    assert d.reason_code == "binary_not_found"
    monkeypatch.setattr(P, "resolve_binary", lambda b: "/usr/bin/npx")
    d = P.check_local_command(["npx"], require_binary=True)
    assert d.allowed is True
    assert d.reason_code == "allow_list"


def test_check_basename_allow_list(monkeypatch, tmp_path):
    monkeypatch.setenv(P.ALLOW_LIST_ENV, "okbin")
    monkeypatch.setattr(P, "resolve_binary", lambda b: "/x/okbin")
    d = P.check_basename_allowed("okbin", host_loopback=True)
    assert d.allowed is True
    assert d.reason_code == "allow_list"
    denied = P.check_basename_allowed("otherbin", host_loopback=True)
    assert denied.allowed is False
    assert denied.reason_code == "not_allowlisted"
    assert "MCP_GWAY_ALLOW_LOCAL_COMMANDS" in denied.message


def test_check_cwd_edges(tmp_path):
    assert P.check_cwd(None) is None
    with pytest.raises(ValueError, match="reason=invalid_cwd"):
        P.check_cwd("")
    with pytest.raises(ValueError, match="reason=invalid_cwd"):
        P.check_cwd("relative/path")
    with pytest.raises(ValueError, match="reason=invalid_cwd"):
        P.check_cwd("/nonexistent-dir-xyz-123")
    out = P.check_cwd(str(tmp_path))
    assert out is not None


def test_check_environment_denylist():
    assert P.check_environment(None) is None
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"PATH": "x"})
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"LD_PRELOAD": "x"})
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"DYLD_FOO": "x"})
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"NPM_CONFIG_X": "x"})
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"BUN_INSTALL": "x"})
    with pytest.raises(ValueError, match="reason=denied_env"):
        P.check_environment({"UV_CACHE": "x"})
    with pytest.raises(ValueError, match="reason=invalid_env"):
        P.check_environment("notadict")
    assert P.check_environment({"NODE_ENV": "prod", "MY_VAR": "1"}) == {
        "NODE_ENV": "prod",
        "MY_VAR": "1",
    }


def test_audit_does_not_raise():
    P.audit_local_action(
        "act", "na/me..", "bin;name", P.PolicyDecision(True, "allow_list", "ok")
    )
    assert P.resolve_binary("definitely-not-a-real-binary-xyz") is None

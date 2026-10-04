"""FEAT-006 harden loop — allow-list case-insensitive, strip-env."""

from __future__ import annotations


def test_allow_list_case_insensitive(monkeypatch) -> None:
    from mcp_gway.core.parsing import parse_envs, parse_headers
    from mcp_gway.core.policy import check_basename_allowed, get_allow_list

    assert parse_envs([" PATH = x "]) == {"PATH": "x"}
    assert parse_headers([" Authorization = Bearer t "]) == {
        "Authorization": "Bearer t"
    }
    monkeypatch.setenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", "MyBin, mybin , MYBIN")
    assert get_allow_list() == {"mybin"}
    monkeypatch.setattr(
        "mcp_gway.core.policy.resolve_binary", lambda b: "/usr/bin/mybin"
    )
    d = check_basename_allowed("MYBIN", host_loopback=True)
    assert d.allowed is True
    assert d.reason_code == "allow_list"

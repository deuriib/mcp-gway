"""Probe error detection: a 3xx/400 carrying `error=` is a failure."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PROBE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "probe_oauth_authorize.py"
)


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_oauth_authorize", _PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code: int, headers=None, text: str = "") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


def _metadata(endpoint: str) -> dict[str, str]:
    return {
        "authorization_endpoint": endpoint,
        "token_endpoint": "https://auth.test/oauth/token",
    }


async def test_probe_303_error_location_exits_1(monkeypatch, capsys):
    probe = _load_probe()
    calls: list[tuple[str, bool]] = []

    async def fake_meta(_url):
        return _metadata("https://auth.test/auth?resource=A")

    async def fake_get(url, *, follow_redirects=True):
        calls.append((url, follow_redirects))
        return FakeResponse(
            303,
            {
                "location": (
                    "http://127.0.0.1:8989/callback?error=invalid_request"
                    "&error_description=missing+required+parameter"
                    "+%27response_type%27&state=s"
                )
            },
        )

    monkeypatch.setattr(probe, "discover_oauth_metadata", fake_meta)
    monkeypatch.setattr(probe, "ssrf_get", fake_get)

    code = await probe._probe(probe._parse_args(["--client-id", "cid"]))
    output = capsys.readouterr().out
    assert code == 1
    assert "failure=invalid_request" in output
    assert "response_type" in output
    assert calls[0][1] is False


async def test_probe_400_error_body_exits_1(monkeypatch, capsys):
    probe = _load_probe()

    async def fake_meta(_url):
        return _metadata("https://auth.test/auth")

    async def fake_get(_url, *, follow_redirects=True):
        return FakeResponse(
            400,
            {},
            '{"error": "invalid_request", "error_description": "bad request"}',
        )

    monkeypatch.setattr(probe, "discover_oauth_metadata", fake_meta)
    monkeypatch.setattr(probe, "ssrf_get", fake_get)

    code = await probe._probe(probe._parse_args(["--client-id", "cid"]))
    output = capsys.readouterr().out
    assert code == 1
    assert "failure=invalid_request" in output
    assert "bad request" in output


async def test_probe_303_without_error_exits_0(monkeypatch, capsys):
    probe = _load_probe()

    async def fake_meta(_url):
        return _metadata("https://auth.test/auth")

    async def fake_get(_url, *, follow_redirects=True):
        return FakeResponse(303, {"location": "https://railway.com/login?state=x"})

    monkeypatch.setattr(probe, "discover_oauth_metadata", fake_meta)
    monkeypatch.setattr(probe, "ssrf_get", fake_get)

    code = await probe._probe(probe._parse_args(["--client-id", "cid"]))
    assert code == 0


async def test_probe_naive_mode_uses_unmerged_url(monkeypatch, capsys):
    probe = _load_probe()
    calls: list[str] = []

    async def fake_meta(_url):
        return _metadata("https://auth.test/auth?resource=A")

    async def fake_get(url, *, follow_redirects=True):
        calls.append(url)
        return FakeResponse(
            303,
            {"location": "http://127.0.0.1:8989/callback?error=invalid_request"},
        )

    monkeypatch.setattr(probe, "discover_oauth_metadata", fake_meta)
    monkeypatch.setattr(probe, "ssrf_get", fake_get)

    code = await probe._probe(probe._parse_args(["--client-id", "cid", "--naive"]))
    output = capsys.readouterr().out
    assert code == 1
    assert calls[0].count("?") == 2
    assert "failure=invalid_request" in output

"""Admin dashboard — full pages, htmx partials, security gates, parity mutations."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pytest
from httpx2 import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from mcp_gway.admin.routes import _ALLOWED_HOSTS, _exec_timeout, _normalize_host
from mcp_gway.core import policy
from mcp_gway.gateway import CSP, Gateway
from mcp_gway.models import MCPServerConfig, OAuthConfig, ToolInfo
from mcp_gway.observability.middleware import path_template
from mcp_gway.registry import Registry


def _gw(tmp_path: Path, transport: str = "http") -> Gateway:
    return Gateway(
        Registry(servers_dir=tmp_path / "srv"), host="127.0.0.1", transport=transport
    )


def _client(gateway: Gateway, **kwargs: Any) -> TestClient:
    """Shared admin TestClient — loopback base_url so the Host header passes
    the fail-closed admin gate (TestClient's default `testserver` is rejected)."""
    return TestClient(gateway.app, base_url="http://127.0.0.1", **kwargs)


def _seed_demo(registry: Registry) -> None:
    config = MCPServerConfig(
        name="Demo",
        type="remote",
        url="https://api.example.com/mcp",
        headers={"Authorization": "Bearer TOPSECRET123"},
    )
    registry.add(config, [ToolInfo(name="ping", description="ping the demo")])


def _seed_local(registry: Registry) -> None:
    config = MCPServerConfig(name="Loc1", type="local", command=["npx", "-y", "demo"])
    registry.add(config, [ToolInfo(name="ping", description="ping the local")])


def _csrf(client_gateway: Gateway) -> dict[str, str]:
    return {"X-CSRF-Token": client_gateway.app.state.csrf_token}


def test_index_serves_dashboard_with_cdn_assets(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/")
    assert r.status_code == 200
    assert "MCP Gateway" in r.text
    assert "cdn.tailwindcss.com" in r.text
    assert "cdn.jsdelivr.net" in r.text
    assert 'integrity="sha384-' in r.text
    assert "hx-boost" in r.text
    assert "X-CSRF-Token" in r.text
    assert "<svg" in r.text
    assert "▶" not in r.text and "⌕" not in r.text
    assert "color-scheme: dark" in r.text
    assert r.headers.get("content-security-policy") == CSP


def test_admin_alias_and_all_pages_200(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    for path in (
        "/",
        "/admin",
        "/admin/servers",
        "/admin/tools",
        "/admin/observability",
        "/admin/policy",
    ):
        r = c.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert "MCP Gateway" in r.text


def test_sse_transport_serves_dashboard(tmp_path: Path) -> None:
    gw = _gw(tmp_path, transport="sse")
    c = _client(gw)
    assert c.get("/").status_code == 200
    assert c.get("/admin/servers").status_code == 200


def test_status_partial_reports_live_state(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/partials/status")
    assert r.status_code == 200
    assert "LIVE" in r.text
    assert "http" in r.text


def test_servers_grid_partial(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.get("/admin/partials/servers")
    assert r.status_code == 200
    assert "row-Demo" in r.text
    filtered = c.get("/admin/partials/servers", params={"q": "nomatch"})
    assert filtered.status_code == 200
    assert "row-Demo" not in filtered.text


def test_metrics_partial_exposes_exposition(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/partials/metrics")
    assert r.status_code == 200
    assert "process_start_time_seconds" in r.text


def test_policy_page_renders_allow_list(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/policy")
    assert r.status_code == 200
    assert "Local command allow-list" in r.text


def test_codemode_partials(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/partials/codemode/list")
    assert r.status_code == 200
    _seed_demo(gw.registry)
    read = c.post(
        "/admin/partials/codemode",
        data={"mode": "read", "fileName": "Demo"},
        headers=_csrf(gw),
    )
    assert read.status_code == 200
    assert "<pre" in read.text
    assert "ping" in read.text


def test_mutation_requires_csrf(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.post("/admin/partials/refresh")
    assert r.status_code == 403
    assert "CSRF token mismatch" in r.text
    wrong = c.post("/admin/partials/refresh", headers={"X-CSRF-Token": "forged"})
    assert wrong.status_code == 403


def test_csrf_form_field_fallback(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.post("/admin/partials/refresh", data={"_csrf": gw.app.state.csrf_token})
    assert r.status_code == 200
    assert "No servers connected." in r.text


def test_loopback_gate_blocks_admin_when_exposed(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    gw.app.state.serve_host = "0.0.0.0"
    c = _client(gw)
    for path in ("/", "/admin", "/admin/servers", "/admin/partials/status"):
        r = c.get(path)
        assert r.status_code == 403, f"{path} -> {r.status_code}"
        assert "loopback" in r.text


def test_add_requires_name(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.post(
        "/admin/partials/servers",
        data={"name": "", "type": "local"},
        headers=_csrf(gw),
    )
    assert r.status_code == 200
    assert "Name is required." in r.text
    assert "f3727f" in r.text


def test_add_local_command_denied_by_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", raising=False)
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.post(
        "/admin/partials/servers",
        data={
            "name": "webadd",
            "type": "local",
            "command": "totallynotallowed --flag",
        },
        headers=_csrf(gw),
    )
    assert r.status_code == 200
    assert "f3727f" in r.text
    assert gw.registry.list() == []


def test_add_duplicate_name_rejected(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.post(
        "/admin/partials/servers",
        data={"name": "demo", "type": "local"},
        headers=_csrf(gw),
    )
    assert r.status_code == 200
    assert "already exists" in r.text


def test_detail_page_masks_header_secrets(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.get("/admin/servers/Demo")
    assert r.status_code == 200
    assert "Demo" in r.text
    assert "api.example.com/mcp" in r.text
    assert "TOPSECRET123" not in r.text
    assert "Authorization" in r.text


def test_detail_unknown_server_404(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/servers/DoesNotExist")
    assert r.status_code == 404


def test_toggle_enabled_returns_row_fragment(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.patch(
        "/admin/partials/servers/Demo/enabled",
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert 'id="row-Demo"' in r.text
    assert "Enable" in r.text
    assert gw.registry.get_config("Demo").enabled is False


def test_detail_config_unreadable_redirects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)

    def _boom(_name: str) -> None:
        raise ValueError("url host DNS failure")

    monkeypatch.setattr(gw.registry, "get_config", _boom)
    c = _client(gw, follow_redirects=False)
    r = c.get("/admin/servers/Demo")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/servers?notice=config-unreadable"


def test_toggle_config_unreadable_toasts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)

    def _boom(_name: str) -> None:
        raise ValueError("url host DNS failure")

    monkeypatch.setattr(gw.registry, "get_config", _boom)
    c = _client(gw)
    r = c.patch(
        "/admin/partials/servers/Demo/enabled",
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "unreadable" in r.text


def test_tools_have_no_web_mutation_path(tmp_path: Path) -> None:
    """Tools sync only on add/refresh — the web cannot add/remove them
    (CLI `update` stays the canonical tools mutation path)."""
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/tools",
        data={"tools": "ping, extra"},
        headers=_csrf(gw),
    )
    assert r.status_code == 405
    assert [t.name for t in gw.registry.get_pyi_tools("Demo")] == ["ping"]
    listing = c.get("/admin/partials/servers/Demo/tools")
    assert listing.status_code == 200
    assert "ping" in listing.text


def test_auth_guard_without_oauth_config(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.post(
        "/admin/partials/servers/Demo/auth",
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "requires a remote server with OAuth" in r.text


def test_remove_hx_redirect_and_plain_redirect(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    hx = c.delete(
        "/admin/partials/servers/Demo",
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert hx.status_code == 200
    assert hx.headers["HX-Redirect"] == "/admin/servers?notice=removed"
    assert gw.registry.list() == []

    _seed_demo(gw.registry)
    plain = c.delete("/admin/partials/servers/Demo", headers=_csrf(gw))
    assert plain.history, "expected the non-hx delete to redirect (client follows)"
    assert plain.history[0].status_code == 303
    assert plain.history[0].headers["location"] == "/admin/servers?notice=removed"


def test_notice_renders_server_side_toast(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/servers", params={"notice": "removed"})
    assert r.status_code == 200
    assert "Server removed." in r.text


def test_policy_unrestricted_routes_gone(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    hx = {**_csrf(gw), "HX-Request": "true"}
    assert c.get("/admin/partials/policy/unrestricted").status_code == 404
    assert c.post("/admin/partials/policy/unrestricted", headers=hx).status_code == 404
    assert (
        c.delete("/admin/partials/policy/unrestricted", headers=hx).status_code == 404
    )


def test_path_template_collapses_admin_cardinality() -> None:
    assert path_template("/") == "/"
    assert path_template("/admin") == "/admin"
    assert path_template("/admin/servers") == "/admin/servers"
    assert path_template("/admin/servers/demo") == "/admin/servers/{name}"
    assert path_template("/admin/partials/servers/demo/refresh") == "/admin/partials"
    assert path_template("/admin/tools") == "/admin/tools"
    assert path_template("/admin/observability") == "/admin/observability"
    assert path_template("/admin/policy") == "/admin/policy"
    assert path_template("/admin/anything-else") == "/admin"
    assert path_template("/health") == "/health"


def test_config_edit_roundtrip_preserves_secrets(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "9000", "enabled": "on", "url": "https://api.example.com/mcp"},
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "Config updated for Demo." in r.text
    cfg = gw.registry.get_config("Demo")
    assert cfg.timeout == 9000
    assert cfg.enabled is True
    assert cfg.headers == {"Authorization": "Bearer TOPSECRET123"}
    page = c.get("/admin/servers/Demo")
    assert "TOPSECRET123" not in page.text
    assert "Edit config" in page.text
    assert 'hx-put="/admin/partials/servers/Demo/config"' in page.text
    assert 'id="edit-config-modal"' in page.text
    assert "<details" not in page.text


def test_config_edit_returns_unescaped_html(tmp_path: Path) -> None:
    """Regression: _render of a child LIST must yield Markup — a plain str
    concatenated with the Markup toast got escaped by Markup.__radd__."""
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "5000", "url": "https://api.example.com/mcp"},
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert r.text.lstrip().startswith("<div")
    assert "&lt;div" not in r.text


def test_config_edit_error_keeps_card_and_reports(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    before = gw.registry.get_config("Demo").timeout
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "not-a-number", "url": "https://api.example.com/mcp"},
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert r.headers.get("hx-retarget") == "#toast"
    assert r.headers.get("hx-reswap") == "outerHTML"
    assert "Timeout must be an integer" in r.text
    assert "hx-swap-oob" not in r.text
    assert "Tools filter" not in r.text
    assert gw.registry.get_config("Demo").timeout == before


def test_config_edit_non_htmx_redirects_with_notice(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    ok = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "7000", "url": "https://api.example.com/mcp"},
        headers=_csrf(gw),
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert ok.headers["location"] == "/admin/servers/Demo?notice=config-saved"
    assert gw.registry.get_config("Demo").timeout == 7000
    bad = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "nope", "url": "https://api.example.com/mcp"},
        headers=_csrf(gw),
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert bad.headers["location"] == "/admin/servers/Demo?notice=config-not-saved"
    landing = c.get("/admin/servers/Demo?notice=config-saved")
    assert "Config updated." in landing.text


def test_config_edit_requires_csrf(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    before = gw.registry.get_config("Demo").timeout
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "9000", "url": "https://api.example.com/mcp"},
    )
    assert r.status_code == 403
    assert gw.registry.get_config("Demo").timeout == before


def test_local_config_put_allowed_command_saves_and_audits_admin_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    monkeypatch.setenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", "python3")
    monkeypatch.setattr(
        policy, "resolve_binary", lambda basename: f"/usr/bin/{basename}"
    )
    gw = _gw(tmp_path)
    _seed_local(gw.registry)
    c = _client(gw)
    with caplog.at_level(logging.INFO, logger="mcp_gway.core.policy"):
        r = c.put(
            "/admin/partials/servers/Loc1/config",
            data={
                "command": "python3 -m allowed_mod",
                "timeout": "7000",
                "enabled": "on",
            },
            headers={**_csrf(gw), "HX-Request": "true"},
        )
    assert r.status_code == 200
    assert "Config updated for Loc1." in r.text
    cfg = gw.registry.get_config("Loc1")
    assert cfg.command == ["python3", "-m", "allowed_mod"]
    assert cfg.timeout == 7000
    assert cfg.enabled is True
    audits = [
        rec.getMessage()
        for rec in caplog.records
        if "action=admin_update" in rec.getMessage()
    ]
    assert audits == [
        (
            "local action=admin_update name=Loc1 binary=python3 "
            "allowed=True reason=allow_list"
        )
    ]


def test_local_config_put_denied_command_rejected_registry_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    monkeypatch.delenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", raising=False)
    gw = _gw(tmp_path)
    _seed_local(gw.registry)
    before = gw.registry.get_config("Loc1")
    c = _client(gw)
    with caplog.at_level(logging.INFO, logger="mcp_gway.core.policy"):
        r = c.put(
            "/admin/partials/servers/Loc1/config",
            data={"command": "totallynotallowed --flag", "timeout": "1"},
            headers={**_csrf(gw), "HX-Request": "true"},
        )
    assert r.status_code == 200
    assert r.headers.get("hx-retarget") == "#toast"
    assert r.headers.get("hx-reswap") == "outerHTML"
    assert "command not allowed: totallynotallowed" in r.text
    assert "[reason=not_allowlisted]" in r.text
    assert "hx-swap-oob" not in r.text
    cfg = gw.registry.get_config("Loc1")
    assert cfg.command == before.command
    assert cfg.timeout == before.timeout
    audits = [
        rec.getMessage()
        for rec in caplog.records
        if "action=admin_update" in rec.getMessage()
    ]
    assert audits == [
        (
            "local action=admin_update name=Loc1 binary=totallynotallowed "
            "allowed=False reason=not_allowlisted"
        )
    ]


def test_active_servers_listed_first(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    gw.registry.add(
        MCPServerConfig(
            name="Alpha",
            type="remote",
            url="https://api.example.com/mcp",
            enabled=False,
        ),
        [],
    )
    c = _client(gw)
    r = c.get("/admin/servers")
    assert r.status_code == 200
    assert r.text.index('id="row-Demo"') < r.text.index('id="row-Alpha"')
    partial = c.get("/admin/partials/servers")
    assert partial.text.index('id="row-Demo"') < partial.text.index('id="row-Alpha"')


def test_responsive_drawer_and_checkbox_modal(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    page = c.get("/")
    assert 'id="nav-drawer"' in page.text
    assert "peer-checked/nav:block" in page.text
    assert 'for="nav-drawer"' in page.text
    assert "hidden shrink-0 md:flex" in page.text
    servers = c.get("/admin/servers").text
    assert 'type="checkbox"' in servers and 'id="add-server-modal"' in servers
    assert "peer-checked/modal:grid" in servers
    assert 'data-type-section="remote"' in servers
    assert 'data-type-section="local"' in servers
    assert 'for="add-server-modal"' in servers
    assert "Save tools" not in servers
    assert "md:flex-row md:items-end md:flex-wrap" in servers
    assert "flex gap-3 w-full md:w-auto shrink-0" in servers
    assert "w-full md:w-[320px]" in servers


def test_detail_readonly_tools_poll_and_signature_scroll(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    r = c.get("/admin/servers/Demo")
    assert r.status_code == 200
    assert 'id="detail-tools-list"' in r.text
    assert 'hx-trigger="every 5s"' in r.text
    assert "/admin/partials/servers/Demo/tools" in r.text
    assert "Save tools" not in r.text
    assert "max-h-[300px] overflow-y-auto" in r.text
    assert "Create a note" not in r.text or "ping the demo" in r.text


def test_probes_values_flush_right(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.get("/admin/observability")
    assert r.status_code == 200
    assert "flex items-center justify-end gap-2 min-w-0" in r.text
    assert "Refresh metrics" in r.text


def _seed_oauth(registry: Registry) -> None:
    config = MCPServerConfig(
        name="Demo",
        type="remote",
        url="https://api.example.com/mcp",
        headers={"Authorization": "Bearer TOPSECRET123"},
    )
    registry.add(config, [ToolInfo(name="ping", description="ping the demo")])
    stored = registry.get_config("Demo")
    stored.oauth = OAuthConfig(
        clientId="11111111-1111-4111-8111-111111111111",
        clientSecret="synthetic-oauth-secret-001",
        scope="openid",
    )
    registry.set_config(stored)


_OAUTH_CID = "11111111-1111-4111-8111-111111111111"
_OAUTH_SECRET = "synthetic-oauth-secret-001"


def test_oauth_scope_only_put_keeps_credentials_byte_identical(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_oauth(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={
            "timeout": "5000",
            "enabled": "on",
            "url": "https://api.example.com/mcp",
            "oauth_client_id": "",
            "oauth_client_secret": "",
            "oauth_scope": "profile",
        },
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "Config updated for Demo." in r.text
    oauth = gw.registry.get_config("Demo").oauth
    assert isinstance(oauth, OAuthConfig)
    assert oauth.clientId == _OAUTH_CID
    assert oauth.clientSecret == _OAUTH_SECRET
    assert oauth.scope == "profile"


def test_oauth_all_blank_fields_keep_stored_credentials(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_oauth(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={
            "timeout": "6000",
            "enabled": "on",
            "url": "https://api.example.com/mcp",
            "oauth_client_id": "",
            "oauth_client_secret": "",
            "oauth_scope": "",
        },
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    after = gw.registry.get_config("Demo")
    assert after.timeout == 6000
    oauth = after.oauth
    assert isinstance(oauth, OAuthConfig)
    assert oauth.clientId == _OAUTH_CID
    assert oauth.clientSecret == _OAUTH_SECRET
    assert oauth.scope == "openid"


def test_oauth_blank_fields_with_no_stored_oauth_stay_none(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    assert gw.registry.get_config("Demo").oauth is None
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={
            "timeout": "7000",
            "enabled": "on",
            "url": "https://api.example.com/mcp",
            "oauth_client_id": "",
            "oauth_client_secret": "",
            "oauth_scope": "",
        },
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    after = gw.registry.get_config("Demo")
    assert after.timeout == 7000
    assert after.oauth is None


def test_oauth_mask_sentinels_treated_as_blank(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_oauth(gw.registry)
    c = _client(gw)
    r = c.put(
        "/admin/partials/servers/Demo/config",
        data={
            "timeout": "5000",
            "enabled": "on",
            "url": "https://api.example.com/mcp",
            "oauth_client_id": "••••••••",
            "oauth_client_secret": "********",
            "oauth_scope": "",
        },
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    oauth = gw.registry.get_config("Demo").oauth
    assert isinstance(oauth, OAuthConfig)
    assert oauth.clientId == _OAUTH_CID
    assert oauth.clientSecret == _OAUTH_SECRET
    assert oauth.scope == "openid"


def test_evil_host_header_403_on_every_admin_surface(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    _seed_demo(gw.registry)
    c = _client(gw)
    evil = {"Host": "evil.example.com"}
    before = gw.registry.get_config("Demo").timeout
    index = c.get("/", headers=evil)
    assert index.status_code == 403
    assert "loopback" in index.text
    page = c.get("/admin/servers", headers=evil)
    assert page.status_code == 403
    assert "loopback" in page.text
    partial = c.get("/admin/partials/status", headers=evil)
    assert partial.status_code == 403
    empty = c.get("/admin/partials/empty", headers=evil)
    assert empty.status_code == 403
    mutation = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "1", "url": "https://api.example.com/mcp"},
        headers={**_csrf(gw), "HX-Request": "true", **evil},
    )
    assert mutation.status_code == 403
    assert "loopback" in mutation.text
    assert gw.registry.get_config("Demo").timeout == before
    without_csrf = c.put(
        "/admin/partials/servers/Demo/config",
        data={"timeout": "1", "url": "https://api.example.com/mcp"},
        headers=evil,
    )
    assert without_csrf.status_code == 403
    assert "loopback" in without_csrf.text
    assert "CSRF token mismatch" not in without_csrf.text


def test_loopback_host_variants_pass_admin_gate(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    for host in (
        "127.0.0.1",
        "localhost",
        "::1",
        "[::1]",
        "127.0.0.1:8080",
        "LOCALHOST:9999",
        "[::1]:8080",
    ):
        r = c.get("/admin/servers", headers={"Host": host})
        assert r.status_code == 200, f"{host} -> {r.status_code}"


def test_normalize_host_fails_closed_matrix() -> None:
    assert _normalize_host(None) == ""
    assert _normalize_host("") == ""
    assert _normalize_host("   ") == ""
    assert _normalize_host("127.0.0.1") == "127.0.0.1"
    assert _normalize_host("127.0.0.1:8080") == "127.0.0.1"
    assert _normalize_host("LOCALHOST:9999") == "localhost"
    assert _normalize_host("::1") == "::1"
    assert _normalize_host("[::1]") == "[::1]"
    assert _normalize_host("[::1]:8080") == "[::1]"
    assert _normalize_host("evil.example.com") == "evil.example.com"
    assert _normalize_host("[::1]evil") == ""
    assert _normalize_host("[::1]:abc") == ""
    assert _normalize_host("[evil") == ""
    assert set(_ALLOWED_HOSTS) == {"127.0.0.1", "localhost", "::1", "[::1]"}
    for bad in (
        "",
        "evil.example.com",
        "127.0.0.1.evil.com",
        "127.0.0.1.",
        "127.0.0.1:8080:9090",
        "testserver",
    ):
        assert bad not in _ALLOWED_HOSTS


def test_non_admin_routes_unaffected_by_host_gate(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    evil = {"Host": "evil.example.com"}
    health = c.get("/health", headers=evil)
    assert health.status_code == 200
    mcp = c.get("/mcp", headers=evil)
    assert mcp.status_code == 405
    assert "POST" in mcp.headers.get("allow", "")


def _aclient(gateway: Gateway, **kwargs: Any) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=gateway.app),
        base_url="http://127.0.0.1",
        **kwargs,
    )


async def test_execute_timeout_htmx_returns_prompt_toast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gw = _gw(tmp_path)

    def _slow(code: str) -> str:
        time.sleep(2.0)
        return '{"result": "late", "logs": []}'

    monkeypatch.setattr(gw.code_mode, "execute_tool_code", _slow)
    async with _aclient(gw) as ac:
        t0 = time.monotonic()
        r = await ac.post(
            "/admin/partials/codemode",
            data={"mode": "execute", "code": "loop_forever()", "timeout": "0.1"},
            headers={"X-CSRF-Token": gw.app.state.csrf_token, "HX-Request": "true"},
        )
        elapsed = time.monotonic() - t0
    assert r.status_code == 200
    assert r.headers.get("hx-retarget") == "#toast"
    assert r.headers.get("hx-reswap") == "outerHTML"
    assert "timed out after 0.1s" in r.text
    assert "hx-swap-oob" not in r.text
    assert elapsed < 1.5


async def test_execute_timeout_real_starlark_does_not_hang(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    code = "def f():\n    for _ in range(100000000):\n        pass\nresult = f()"
    async with _aclient(gw) as ac:
        t0 = time.monotonic()
        r = await ac.post(
            "/admin/partials/codemode",
            data={"mode": "execute", "code": code, "timeout": "0.1"},
            headers={"X-CSRF-Token": gw.app.state.csrf_token, "HX-Request": "true"},
        )
        elapsed = time.monotonic() - t0
    assert r.status_code == 200
    assert r.headers.get("hx-retarget") == "#toast"
    assert "timed out after 0.1s" in r.text
    assert elapsed < 8.0


async def test_execute_timeout_non_htmx_redirects_with_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gw = _gw(tmp_path)

    def _slow(code: str) -> str:
        time.sleep(1.0)
        return '{"result": "late", "logs": []}'

    monkeypatch.setattr(gw.code_mode, "execute_tool_code", _slow)
    async with _aclient(gw) as ac:
        r = await ac.post(
            "/admin/partials/codemode",
            data={"mode": "execute", "code": "loop_forever()", "timeout": "0.1"},
            headers={"X-CSRF-Token": gw.app.state.csrf_token},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/admin/tools?notice=exec-timeout"
        landing = await ac.get("/admin/tools?notice=exec-timeout")
    assert landing.status_code == 200
    assert "timed out" in landing.text


def test_exec_timeout_clamps_and_defaults() -> None:
    assert _exec_timeout(None) == 10.0
    assert _exec_timeout("") == 10.0
    assert _exec_timeout("not-a-number") == 10.0
    assert _exec_timeout("nan") == 10.0
    assert _exec_timeout("inf") == 10.0
    assert _exec_timeout("-inf") == 10.0
    assert _exec_timeout("0") == 0.1
    assert _exec_timeout("0.001") == 0.1
    assert _exec_timeout("999") == 30.0
    assert _exec_timeout("5.5") == 5.5


def test_execute_fast_path_returns_result_without_timeout(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    r = c.post(
        "/admin/partials/codemode",
        data={"mode": "execute", "code": "result = 42", "timeout": "5"},
        headers={**_csrf(gw), "HX-Request": "true"},
    )
    assert r.status_code == 200
    assert r.headers.get("hx-retarget") is None
    assert "42" in r.text
    assert "timed out" not in r.text


def test_toolbar_flex_children_share_identical_floors(tmp_path: Path) -> None:
    gw = _gw(tmp_path)
    c = _client(gw)
    servers = c.get("/admin/servers").text
    assert (
        '<div class="flex gap-3 w-full md:w-auto shrink-0">'
        '<div class="flex flex-1 md:flex-none">'
        "<button"
    ) in servers
    assert 'class="relative flex-1 md:flex-none"' in servers
    assert "flex-1 justify-center md:flex-none" in servers
    assert "px-4 py-2 text-[14px]" in servers
    assert 'hx-post="/admin/partials/refresh"' in servers
    assert 'for="add-server-modal"' in servers
    assert "md:flex-row md:items-end md:flex-wrap" in servers

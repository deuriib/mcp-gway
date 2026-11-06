"""R1: authorization URL merge — endpoint query preserved, caller params win."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from mcp_gway.oauth import authorization_endpoint_resource, build_authorization_url


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def test_existing_query_keeps_response_type():
    url = build_authorization_url(
        "https://as.test/oauth/auth?resource=https%3A%2F%2Fmcp.test%2Fmcp",
        {"response_type": "code", "client_id": "cid"},
    )
    assert url.count("?") == 1
    query = _query(url)
    assert query["response_type"] == ["code"]
    assert query["resource"] == ["https://mcp.test/mcp"]
    assert query["client_id"] == ["cid"]


def test_no_duplicate_question_mark():
    url = build_authorization_url(
        "https://as.test/oauth/auth?tenant=acme", {"state": "s1"}
    )
    assert url.count("?") == 1
    assert _query(url)["tenant"] == ["acme"]


def test_endpoint_params_preserved_and_not_duplicated():
    url = build_authorization_url(
        "https://as.test/oauth/auth?resource=A&tenant=acme",
        {"resource": "B", "state": "s1"},
    )
    query = _query(url)
    assert query["resource"] == ["A"]
    assert query["tenant"] == ["acme"]
    assert query["state"] == ["s1"]


def test_response_type_added_when_absent():
    url = build_authorization_url("https://as.test/oauth/auth", {"client_id": "cid"})
    assert _query(url)["response_type"] == ["code"]


def test_response_type_forced_to_code_when_endpoint_carries_token():
    url = build_authorization_url(
        "https://as.test/oauth/auth?response_type=token", {"state": "s1"}
    )
    assert _query(url)["response_type"] == ["code"]


def test_caller_params_override_endpoint_params():
    endpoint = (
        "https://as.test/oauth/auth?state=attacker&code_challenge=bad"
        "&code_challenge_method=plain&client_id=evil"
        "&redirect_uri=https%3A%2F%2Fevil.test%2Fcb&response_type=token"
    )
    url = build_authorization_url(
        endpoint,
        {
            "response_type": "code",
            "client_id": "ours",
            "redirect_uri": "http://127.0.0.1:8989/callback",
            "state": "ours-state",
            "code_challenge": "good-challenge",
            "code_challenge_method": "S256",
        },
    )
    query = _query(url)
    assert query["state"] == ["ours-state"]
    assert query["code_challenge"] == ["good-challenge"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["client_id"] == ["ours"]
    assert query["redirect_uri"] == ["http://127.0.0.1:8989/callback"]
    assert query["response_type"] == ["code"]


def test_fragment_preserved():
    url = build_authorization_url("https://as.test/oauth/auth?x=1#frag", {"state": "s"})
    assert url.count("?") == 1
    assert url.endswith("#frag")


def test_blank_endpoint_resource_is_treated_as_absent():
    assert (
        authorization_endpoint_resource("https://as.test/oauth/auth?resource=") is None
    )
    url = build_authorization_url(
        "https://as.test/oauth/auth?resource=", {"resource": "B", "state": "s"}
    )
    query = _query(url)
    assert query["resource"] == ["B"]
    assert url.count("?") == 1


def test_authorization_endpoint_resource():
    assert (
        authorization_endpoint_resource(
            "https://as.test/oauth/auth?resource=https%3A%2F%2Fmcp.test%2Fmcp"
        )
        == "https://mcp.test/mcp"
    )
    assert authorization_endpoint_resource("https://as.test/oauth/auth") is None

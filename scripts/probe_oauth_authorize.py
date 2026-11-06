"""Live probe: build the OAuth authorization URL and report the AS response.

Exit 0 only for a 3xx (login/interaction) response; 1 otherwise. No token
exchange, no callback server, no browser, no secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import secrets
import sys
from urllib.parse import parse_qs, urlencode

from mcp_gway.models import ssrf_get
from mcp_gway.oauth import (
    build_authorization_url,
    discover_oauth_metadata,
    generate_pkce,
    resolve_resource,
    resolve_scope,
)

DEFAULT_SERVER_URL = "https://mcp.railway.com/mcp"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8989/callback"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe an OAuth authorization endpoint without exchanging tokens."
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--scope")
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    parser.add_argument("--resource")
    parser.add_argument(
        "--auth-endpoint",
        help="replay a recorded authorization_endpoint shape",
    )
    parser.add_argument(
        "--naive",
        action="store_true",
        help="probe the unmerged URL (f'{endpoint}?{params}') instead of the merged one",
    )
    return parser.parse_args(argv)


def _params(args: argparse.Namespace, scope: str, resource: str) -> dict[str, str]:
    _, code_challenge = generate_pkce()
    return {
        "response_type": "code",
        "client_id": args.client_id,
        "redirect_uri": args.redirect_uri,
        "state": secrets.token_urlsafe(32),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": scope,
        "resource": resource,
    }


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_ERROR_CHARS = 200


def _clean(value: object) -> str:
    return _CONTROL_CHARS.sub("", str(value))[:_MAX_ERROR_CHARS]


def _query_error(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    query = value.split("?", 1)[1] if "?" in value else value
    params = parse_qs(query)
    error = (params.get("error") or [""])[0]
    if not error:
        return None
    description = (params.get("error_description") or [""])[0]
    return error, description


def _body_error(body: str) -> tuple[str, str] | None:
    if not body:
        return None
    try:
        payload = json.loads(body)
    except Exception:
        payload = None
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"]), str(payload.get("error_description") or "")
    found = _query_error(body)
    if found:
        return found
    match = re.search(r"error=([^&\s\"'<>]+)", body)
    if match:
        return match.group(1), ""
    return None


def _response_error(location: str, body: str) -> tuple[str, str] | None:
    return _query_error(location) or _body_error(body)


async def _probe(args: argparse.Namespace) -> int:
    metadata = await discover_oauth_metadata(args.server_url)
    if not metadata:
        print(f"error: OAuth metadata discovery failed for {args.server_url}")
        return 1
    endpoint = args.auth_endpoint or metadata.get("authorization_endpoint")
    if not endpoint:
        print("error: no authorization_endpoint in metadata")
        return 1
    if not metadata.get("token_endpoint"):
        print("error: no token_endpoint in metadata")
        return 1

    resource = args.resource or resolve_resource(
        auth_endpoint=endpoint,
        prm_resource=metadata.get("resource"),
        server_url=args.server_url,
    )
    scope = resolve_scope(
        configured=args.scope,
        client_metadata_scope=None,
        prm_scopes=metadata.get("prm_scopes_supported"),
        as_scopes=metadata.get("scopes_supported"),
    )
    params = _params(args, scope, resource)
    naive_url = f"{endpoint}?{urlencode(params)}"
    merged_url = build_authorization_url(endpoint, params)
    print(f"naive_url={naive_url}")
    print(f"merged_url={merged_url}")
    probe_url = naive_url if args.naive else merged_url

    try:
        response = await ssrf_get(probe_url, follow_redirects=False)
    except Exception as exc:
        print(f"error: request failed: {exc}")
        return 1

    status = getattr(response, "status_code", 0)
    headers = getattr(response, "headers", {}) or {}
    location = headers.get("location") or headers.get("Location") or ""
    try:
        body = getattr(response, "text", "") or ""
    except Exception:
        body = ""
    print(f"status={status}")
    print(f"location={location}")

    failure = _response_error(location, body)
    if failure is not None:
        error, description = failure
        print(f"failure={_clean(error)}")
        if description:
            print(f"error_description={_clean(description)}")
        return 1
    if 300 <= status < 400:
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_probe(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())

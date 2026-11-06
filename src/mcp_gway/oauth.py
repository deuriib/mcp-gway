"""OAuth2 support for MCP servers requiring authentication."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import secrets
import string
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

from mcp_gway.models import _validate_name_value


def _validate_server_name(name: str) -> None:
    _validate_name_value(name)


def _secure_atomic_write(path: Path, content: str) -> None:
    """Delegate to the shared secureio helper (single symlink-safe impl)."""
    from mcp_gway.secureio import secure_atomic_write_text

    secure_atomic_write_text(path, content)


import httpx2
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

from mcp_gway.models import SSRF_IDLE_TIMEOUT, SSRF_TIMEOUT

_OAUTH_HTTP_TIMEOUT = SSRF_TIMEOUT


class FileTokenStorage:
    """File-based token storage for OAuth tokens."""

    def __init__(self, server_name: str, storage_dir: Path | None = None) -> None:
        from mcp_gway.core.policy import home_dir

        _validate_server_name(server_name)
        self._storage_dir = (
            storage_dir or home_dir() / ".config" / "mcp-gway" / "tokens"
        )
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        token_path = self._storage_dir / f"{server_name}.json"
        try:
            if not token_path.resolve().is_relative_to(self._storage_dir.resolve()):
                raise ValueError("Invalid server name: path traversal")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError("Invalid server name") from e
        self._token_file = token_path

    async def get_tokens(self) -> OAuthToken | None:
        if not self._token_file.exists():
            return None
        try:
            data = json.loads(self._token_file.read_text(encoding="utf-8"))
            return OAuthToken(**data)
        except Exception:
            return None

    async def get_expires_at(self) -> int | None:
        if not self._token_file.exists():
            return None
        try:
            data = json.loads(self._token_file.read_text(encoding="utf-8"))
        except Exception:
            return None
        value = data.get("expires_at") if isinstance(data, dict) else None
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    async def set_tokens(
        self, tokens: OAuthToken, *, expires_at: int | None = None
    ) -> None:
        data = tokens.model_dump(mode="json", exclude_none=True)
        if expires_at is None:
            data.pop("expires_at", None)
        else:
            data["expires_at"] = int(expires_at)
        content = json.dumps(data, indent=2)
        _secure_atomic_write(self._token_file, content)

    async def clear_tokens(self) -> None:
        self._token_file.unlink(missing_ok=True)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        info_file = self._storage_dir / f"{self._token_file.stem}_client.json"
        if not info_file.exists():
            return None
        try:
            data = json.loads(info_file.read_text(encoding="utf-8"))
            return OAuthClientInformationFull(**data)
        except Exception:
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        info_file = self._storage_dir / f"{self._token_file.stem}_client.json"
        content = json.dumps(
            client_info.model_dump(mode="json", exclude_none=True), indent=2
        )
        _secure_atomic_write(info_file, content)


class OAuthCallbackServer:
    """Local HTTP server to handle OAuth callbacks."""

    def __init__(self, port: int = 8989) -> None:
        self._port = port
        self._server: asyncio.AbstractServer | None = None
        self._result: dict[str, str] | None = None
        self._event = asyncio.Event()

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single HTTP request."""
        try:
            data = await asyncio.wait_for(reader.read(65536), timeout=5.0)
            if not data:
                return

            request_line = data.split(b"\r\n")[0].decode("utf-8", errors="replace")
            parts = request_line.split(" ")
            if len(parts) < 2:
                return

            path = parts[1]
            if "?" in path:
                _, query_string = path.split("?", 1)
                params = parse_qs(query_string)
            else:
                params = {}

            # Extract code, state and RFC 6749 error fields from the callback
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]
            error_description = params.get("error_description", [None])[0]

            if error:
                self._result = {
                    "error": _sanitize(error),
                    "error_description": _sanitize(error_description or ""),
                    "state": state or "",
                }
                self._event.set()
                detail = self._result["error_description"]
                escaped = f"<p>{html.escape(detail)}</p>" if detail else ""
                response = (
                    "HTTP/1.1 400 Bad Request\r\n"
                    "Content-Type: text/html\r\n"
                    "\r\n"
                    "<html><body><h1>Authentication failed</h1>"
                    f"<p>{html.escape(self._result['error'])}</p>{escaped}"
                    "</body></html>"
                )
            elif code:
                self._result = {"code": code, "state": state or ""}
                self._event.set()

                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html\r\n"
                    "\r\n"
                    "<html><body>"
                    "<h1>Authentication successful!</h1>"
                    "<p>You can close this window and return to the terminal.</p>"
                    "</body></html>"
                )
            else:
                response = (
                    "HTTP/1.1 400 Bad Request\r\n"
                    "Content-Type: text/html\r\n"
                    "\r\n"
                    "<html><body><h1>No authorization code received</h1></body></html>"
                )

            writer.write(response.encode())
            await writer.drain()
        except Exception:  # noqa: S110
            pass
        finally:
            writer.close()

    async def start(self) -> None:
        """Start the local callback server, trying next ports if busy."""
        last_exc = None
        for try_port in [self._port, self._port + 1, self._port + 2, 0]:
            try:
                self._server = await asyncio.start_server(
                    self._handle_request, "127.0.0.1", try_port
                )
                if try_port == 0 and self._server.sockets:
                    self._port = self._server.sockets[0].getsockname()[1]
                elif try_port != self._port:
                    self._port = try_port
                return
            except OSError as e:
                last_exc = e
                if (
                    getattr(e, "winerror", None) == 10048
                    or "already in use" in str(e).lower()
                    or "address already in use" in str(e).lower()
                ):
                    continue
                raise
        if last_exc:
            raise last_exc

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def wait_for_callback(
        self, timeout: float = SSRF_IDLE_TIMEOUT
    ) -> dict[str, str] | None:
        """Wait for the OAuth callback."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return self._result
        except TimeoutError:
            return None
        finally:
            await self.close()

    @property
    def callback_url(self) -> str:
        return f"http://127.0.0.1:{self._port}/callback"


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = "".join(
        secrets.choice(string.ascii_letters + string.digits + "-._~")
        for _ in range(128)
    )
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = __import__("base64").urlsafe_b64encode(digest).decode().rstrip("=")
    return code_verifier, code_challenge


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_ERROR_CHARS = 200


def _sanitize(value: object, limit: int = _MAX_ERROR_CHARS) -> str:
    """Strip control chars and truncate attacker-influenced text for logs/HTML."""
    return _CONTROL_CHARS.sub("", str(value))[:limit]


def authorization_endpoint_resource(auth_endpoint: str) -> str | None:
    """The `resource` value embedded in the authorization endpoint query, if any."""
    values = parse_qs(urlparse(auth_endpoint).query).get("resource") or []
    return next((value for value in values if value.strip()), None)


def build_authorization_url(auth_endpoint: str, params: dict[str, str]) -> str:
    """Merge OAuth params into the endpoint query (one '?', '&' separators).

    Caller params override endpoint params, except `resource`: an
    endpoint-supplied resource is authoritative and never duplicated.
    `response_type` is always forced to "code". Fragment preserved.
    """
    parsed = urlparse(auth_endpoint)
    existing = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not (key == "resource" and not value.strip())
    ]
    endpoint_resource = any(key == "resource" for key, _ in existing)
    merged = [
        (key, value)
        for key, value in existing
        if key not in params or (key == "resource" and endpoint_resource)
    ]
    merged.extend(
        (key, value)
        for key, value in params.items()
        if not (key == "resource" and endpoint_resource)
    )
    merged = [(key, value) for key, value in merged if key != "response_type"]
    merged.append(("response_type", "code"))
    return urlunparse(parsed._replace(query=urlencode(merged)))


def resolve_resource(
    *, auth_endpoint: str, prm_resource: str | None, server_url: str
) -> str:
    """One RFC 8707 resource value shared by authorize, exchange and refresh."""
    return authorization_endpoint_resource(auth_endpoint) or prm_resource or server_url


def resolve_scope(
    *,
    configured: str | None,
    client_metadata_scope: str | None,
    prm_scopes: Sequence[object] | None,
    as_scopes: Sequence[object] | None,
) -> str:
    """Scope precedence plus `offline_access` when the AS advertises it."""
    prm_joined = " ".join(str(s) for s in prm_scopes or [] if str(s).strip())
    effective = ""
    for candidate in (configured, client_metadata_scope, prm_joined):
        if candidate and str(candidate).strip():
            effective = str(candidate).strip()
            break
    if not effective:
        effective = "openid profile email"
    advertised = {str(s) for s in as_scopes or []}
    if "offline_access" in advertised and "offline_access" not in effective.split():
        effective = f"{effective} offline_access"
    return effective


def _parse_resource_metadata_url(www_auth: str) -> str | None:
    """Extract resource_metadata URL from WWW-Authenticate header per RFC 8707."""
    if not www_auth:
        return None
    m = re.search(r'resource_metadata\s*=\s*"([^"]+)"', www_auth)
    if m:
        return m.group(1)
    m2 = re.search(r"resource_metadata\s*=\s*'([^']+)'", www_auth)
    if m2:
        return m2.group(1)
    m3 = re.search(r"resource_metadata\s*=\s*([^\s,;]+)", www_auth)
    if m3:
        return m3.group(1).strip("\"'")
    return None


def _require_https_or_none(url: str | None) -> str | None:
    """Return url when https, else None (fail-closed for OAuth discovery)."""
    if not url:
        return None
    try:
        from mcp_gway.models import _require_https

        _require_https(url)
    except ValueError:
        return None
    return url


async def discover_oauth_metadata(server_url: str) -> dict[str, Any] | None:
    """Discover OAuth metadata from the server.

    First checks Protected Resource Metadata (RFC 8707) for the authorization server,
    then discovers OAuth metadata from that server. Supports WWW-Authenticate
    header with resource_metadata per MCP spec. All URLs are https-only
    fail-closed ([reason=https_only]); http candidates are skipped, never fetched.
    """
    from mcp_gway.models import _require_https, avalidate_url_ssrf, ssrf_get

    try:
        _require_https(server_url)
    except ValueError:
        return None

    _discovery_timeout = SSRF_TIMEOUT
    _ = (_discovery_timeout, _OAUTH_HTTP_TIMEOUT)
    try:
        await avalidate_url_ssrf(server_url)
    except ValueError:
        return None
    # Step 0: Try WWW-Authenticate header from 401 as per MCP OAuth spec
    prm_from_header: str | None = None
    try:
        resp = await ssrf_get(server_url)
        if resp.status_code == 401:
            www_auth = resp.headers.get("www-authenticate", "") or resp.headers.get(
                "WWW-Authenticate", ""
            )
            prm_from_header = _parse_resource_metadata_url(www_auth)
            if prm_from_header is not None:
                try:
                    _require_https(prm_from_header)
                    await avalidate_url_ssrf(prm_from_header)
                except ValueError:
                    prm_from_header = None
    except Exception:  # noqa: S112
        pass

    # Step 1: Try to get Protected Resource Metadata
    parsed = urlparse(server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/mcp"

    prm_urls: list[str] = []
    if prm_from_header:
        prm_urls.append(prm_from_header)
    prm_urls.extend(
        [
            f"{base_url}/.well-known/oauth-protected-resource{path}",
            f"{base_url}/.well-known/oauth-protected-resource",
        ]
    )

    auth_server_url = None
    prm_data: dict[str, Any] | None = None
    for url in prm_urls:
        try:
            _require_https(url)
            await avalidate_url_ssrf(url)
            response = await ssrf_get(url)
            if response.status_code == 200:
                prm = response.json()
                auth_servers = prm.get("authorization_servers", [])
                if auth_servers:
                    cand = auth_servers[0]
                    try:
                        _require_https(cand)
                        await avalidate_url_ssrf(cand)
                    except ValueError:
                        continue
                    auth_server_url = cand
                    prm_data = prm
                    break
        except Exception:  # noqa: S112
            continue

    # Step 2: Discover OAuth metadata from authorization server
    if auth_server_url:
        discovery_urls = [
            f"{auth_server_url}/.well-known/oauth-authorization-server",
            f"{auth_server_url}/.well-known/openid-configuration",
        ]
    else:
        # Fallback to standard discovery on the server URL
        discovery_urls = [
            f"{base_url}/.well-known/oauth-authorization-server",
            f"{base_url}/.well-known/openid-configuration",
        ]

    for url in discovery_urls:
        try:
            _require_https(url)
            await avalidate_url_ssrf(url)
            response = await ssrf_get(url)
            if response.status_code == 200:
                as_metadata = response.json()
                if prm_data is None:
                    return as_metadata
                extra: dict[str, Any] = {}
                if prm_data.get("resource"):
                    extra["resource"] = prm_data["resource"]
                if prm_data.get("scopes_supported") is not None:
                    extra["prm_scopes_supported"] = prm_data["scopes_supported"]
                return {**as_metadata, **extra} if extra else as_metadata
        except Exception:  # noqa: S112
            continue

    return None


def _response_payload(response: Any) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _response_error(response: Any) -> str:
    """Status plus parsed RFC 6749 error fields; never the raw response body."""
    status = getattr(response, "status_code", "unknown")
    payload = _response_payload(response)
    if payload:
        error = payload.get("error")
        description = payload.get("error_description")
        if error or description:
            detail = ": ".join(str(part) for part in (error, description) if part)
            return f"status {status}: {_sanitize(detail)}"
    return f"status {status}"


def _token_from_response(
    token_response: dict[str, Any], previous: OAuthToken | None
) -> OAuthToken | None:
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        return None
    expires_in = token_response.get("expires_in")
    if expires_in is None and previous is not None:
        expires_in = previous.expires_in
    refresh_token = token_response.get("refresh_token")
    if not refresh_token and previous is not None:
        refresh_token = previous.refresh_token
    scope = token_response.get("scope")
    if not scope and previous is not None:
        scope = previous.scope
    try:
        return OAuthToken(
            access_token=access_token,
            token_type=token_response.get("token_type") or "Bearer",
            expires_in=expires_in,
            scope=scope,
            refresh_token=refresh_token,
        )
    except Exception:
        return None


def _expires_at_for(tokens: OAuthToken) -> int | None:
    if tokens.expires_in is None:
        return None
    try:
        return int(time.time()) + int(tokens.expires_in)
    except (TypeError, ValueError):
        return None


def _client_redirect_ok(
    client_info: OAuthClientInformationFull, callback_url: str
) -> bool:
    uris = client_info.redirect_uris or []
    if not uris:
        return True
    target = callback_url.rstrip("/")
    return any(str(uri).rstrip("/") == target for uri in uris)


def _extract_credentials(cfg: Any) -> tuple[str | None, str | None, str | None]:
    if cfg is None:
        return None, None, None
    if isinstance(cfg, dict):
        return (
            cfg.get("clientId") or cfg.get("client_id"),
            cfg.get("clientSecret") or cfg.get("client_secret"),
            cfg.get("scope"),
        )
    cid = getattr(cfg, "clientId", None) or getattr(cfg, "client_id", None)
    csec = getattr(cfg, "clientSecret", None) or getattr(cfg, "client_secret", None)
    return cid, csec, getattr(cfg, "scope", None)


async def _register_client(
    *,
    registration_endpoint: str,
    callback_url: str,
    storage: FileTokenStorage,
    output_callback: Any,
) -> tuple[str | None, str | None]:
    from mcp_gway.models import ssrf_post

    output_callback("Registering OAuth client...")
    request = {
        "client_name": "MCP Gateway",
        "redirect_uris": [callback_url],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    try:
        response = await ssrf_post(
            registration_endpoint,
            headers={"Content-Type": "application/json"},
            json=request,  # type: ignore[arg-type]
        )
    except Exception as e:
        output_callback(f"Warning: Client registration failed: {_sanitize(e)}")
        return None, None
    if response.status_code not in (200, 201):
        output_callback(
            f"Warning: Client registration failed ({response.status_code})."
        )
        return None, None
    data = _response_payload(response) or {}
    client_id = data.get("client_id")
    if not client_id:
        output_callback("Warning: Client registration returned no client_id.")
        return None, None
    client_secret = data.get("client_secret")
    try:
        client_info = OAuthClientInformationFull(
            client_id=str(client_id),
            client_secret=client_secret,
            **{
                key: value
                for key, value in data.items()
                if key not in ("client_id", "client_secret")
            },
        )
        await storage.set_client_info(client_info)
    except Exception:
        output_callback("Warning: Client registration response was invalid.")
        return None, None
    output_callback(f"Registered client: {str(client_id)[:16]}...")
    return str(client_id), client_secret


async def _exchange_code(
    *,
    token_endpoint: str,
    resource: str,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None,
    output_callback: Any,
) -> OAuthToken | None:
    from mcp_gway.models import ssrf_post

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "resource": resource,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        response = await ssrf_post(
            token_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except Exception as e:
        output_callback(f"Error during token exchange: {_sanitize(e)}")
        return None
    if response.status_code != 200:
        output_callback(f"Error: Token exchange failed ({_response_error(response)}).")
        return None
    tokens = _token_from_response(_response_payload(response) or {}, None)
    if tokens is None:
        output_callback("Error: Token exchange failed: no access token in response.")
    return tokens


async def _refresh_tokens(
    *,
    token_endpoint: str,
    resource: str,
    client_id: str,
    client_secret: str | None,
    previous: OAuthToken,
    output_callback: Any,
) -> OAuthToken | None:
    from mcp_gway.models import ssrf_post

    data = {
        "grant_type": "refresh_token",
        "refresh_token": previous.refresh_token or "",
        "client_id": client_id,
        "resource": resource,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        response = await ssrf_post(
            token_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except Exception as e:
        output_callback(f"Refresh failed: {_sanitize(e)}")
        return None
    if response.status_code != 200:
        output_callback(f"Refresh failed ({_response_error(response)}).")
        return None
    tokens = _token_from_response(_response_payload(response) or {}, previous)
    if tokens is None:
        output_callback("Refresh failed: no access token in response.")
    return tokens


async def _resolve_client(
    *,
    configured_cid: str | None,
    configured_csec: str | None,
    persisted: OAuthClientInformationFull | None,
    registration_endpoint: str | None,
    callback_url: str,
    storage: FileTokenStorage,
    output_callback: Any,
) -> tuple[str | None, str | None]:
    """Credential chain: configured → persisted (port-matched) → DCR → None."""
    if configured_cid:
        output_callback(
            f"Using pre-registered client: {configured_cid[:16]}... (manual)"
        )
        return configured_cid, configured_csec
    if persisted is not None and _client_redirect_ok(persisted, callback_url):
        output_callback(f"Using registered client: {persisted.client_id[:16]}...")
        return persisted.client_id, persisted.client_secret
    if registration_endpoint:
        return await _register_client(
            registration_endpoint=registration_endpoint,
            callback_url=callback_url,
            storage=storage,
            output_callback=output_callback,
        )
    return None, None


async def run_oauth_flow(
    server_url: str,
    server_name: str,
    client_metadata: OAuthClientMetadata | None = None,
    output_callback: Any = None,
    callback_port: int = 8989,
    oauth_config: Any | None = None,
) -> httpx2.AsyncClient | None:
    """Run the full OAuth flow.

    Configured client credentials are used verbatim; dynamic registration
    (RFC 7591) only runs when no client ID is configured or persisted. A valid
    stored token is reused; an expired one is refreshed before the browser flow.

    Args:
        server_url: The MCP server URL
        server_name: Name of the server for storage
        client_metadata: Optional OAuth client metadata
        output_callback: Optional callback for output messages
        callback_port: Local port for OAuth callback
        oauth_config: Optional OAuthConfig dict/object with clientId/clientSecret/scope

    Returns:
        Authenticated httpx client or None if flow fails
    """
    if output_callback is None:
        output_callback = lambda msg: None

    from mcp_gway.models import _require_https, avalidate_url_ssrf

    _flow_timeout = SSRF_TIMEOUT
    try:
        _require_https(server_url)
        await avalidate_url_ssrf(server_url)
    except ValueError as e:
        output_callback(f"Error: blocked server URL: {e}")
        return None

    storage = FileTokenStorage(server_name)

    async def _finish(tokens: OAuthToken) -> httpx2.AsyncClient | None:
        client = httpx2.AsyncClient(
            timeout=_flow_timeout,
            headers={"Authorization": f"Bearer {tokens.access_token}"},
            follow_redirects=False,
        )
        try:
            await storage.set_tokens(tokens, expires_at=_expires_at_for(tokens))
        except Exception:
            await client.aclose()
            output_callback("Error: could not persist the OAuth token.")
            return None
        return client

    existing_tokens = await storage.get_tokens()
    expires_at = await storage.get_expires_at()
    if (
        existing_tokens
        and existing_tokens.access_token
        and (expires_at is None or expires_at > int(time.time()))
    ):
        output_callback("Using existing token...")
        return httpx2.AsyncClient(
            timeout=_flow_timeout,
            headers={"Authorization": f"Bearer {existing_tokens.access_token}"},
            follow_redirects=False,
        )

    # Discover OAuth metadata
    output_callback(f"Discovering OAuth metadata for {server_url}...")
    metadata = await discover_oauth_metadata(server_url)

    if not metadata:
        output_callback("Warning: Could not discover OAuth metadata.")
        output_callback("Please provide a token manually:")
        output_callback(
            f'  echo \'{{"access_token": "YOUR_TOKEN"}}\' > ~/.config/mcp-gway/tokens/{server_name}.json'
        )
        return None

    # Get endpoints
    auth_endpoint = metadata.get("authorization_endpoint")
    token_endpoint = metadata.get("token_endpoint")
    registration_endpoint = metadata.get("registration_endpoint")

    if not auth_endpoint or not token_endpoint:
        output_callback("Error: Missing authorization or token endpoint in metadata.")
        return None
    try:
        _require_https(auth_endpoint)
        _require_https(token_endpoint)
        if registration_endpoint:
            _require_https(registration_endpoint)
        await avalidate_url_ssrf(auth_endpoint)
        await avalidate_url_ssrf(token_endpoint)
        if registration_endpoint:
            await avalidate_url_ssrf(registration_endpoint)
    except ValueError as e:
        output_callback(f"Error: blocked OAuth endpoint: {e}")
        return None

    resource = resolve_resource(
        auth_endpoint=auth_endpoint,
        prm_resource=metadata.get("resource"),
        server_url=server_url,
    )
    oauth_cid, oauth_csec, oauth_scope = _extract_credentials(oauth_config)
    configured_cid = (
        str(oauth_cid).strip() if oauth_cid and str(oauth_cid).strip() else None
    )
    configured_csec = oauth_csec or None
    persisted = None if configured_cid else await storage.get_client_info()

    if existing_tokens is not None:
        refresh_cid = configured_cid or (persisted.client_id if persisted else None)
        refresh_csec = (
            configured_csec
            if configured_cid
            else getattr(persisted, "client_secret", None)
        )
        refreshed = None
        if existing_tokens.refresh_token and refresh_cid:
            output_callback("Refreshing expired token...")
            refreshed = await _refresh_tokens(
                token_endpoint=token_endpoint,
                resource=resource,
                client_id=refresh_cid,
                client_secret=refresh_csec,
                previous=existing_tokens,
                output_callback=output_callback,
            )
        if refreshed is not None:
            client = await _finish(refreshed)
            if client is None:
                return None
            output_callback("Authentication successful!")
            return client
        await storage.clear_tokens()
        output_callback("Stored token is no longer valid; re-authentication required.")

    meta_scope = getattr(client_metadata, "scope", None) if client_metadata else None
    effective_scope = resolve_scope(
        configured=oauth_scope,
        client_metadata_scope=meta_scope,
        prm_scopes=metadata.get("prm_scopes_supported"),
        as_scopes=metadata.get("scopes_supported"),
    )

    callback_server = OAuthCallbackServer(port=callback_port)
    await callback_server.start()

    client_id, client_secret = await _resolve_client(
        configured_cid=configured_cid,
        configured_csec=configured_csec,
        persisted=persisted,
        registration_endpoint=registration_endpoint,
        callback_url=callback_server.callback_url,
        storage=storage,
        output_callback=output_callback,
    )
    if client_id is None:
        output_callback(
            "Error: no client_id configured and dynamic registration is unavailable."
        )
        await callback_server.close()
        return None

    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_server.callback_url,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": effective_scope,
        "resource": resource,
    }
    auth_url = build_authorization_url(auth_endpoint, auth_params)

    output_callback("Opening browser for authentication...")
    output_callback(f"If the browser doesn't open, visit:\n{auth_url}")

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    output_callback("Waiting for authentication callback...")
    callback_result = await callback_server.wait_for_callback(timeout=SSRF_IDLE_TIMEOUT)

    if not callback_result:
        output_callback("Error: Authentication timed out or no code received.")
        return None

    error = callback_result.get("error")
    if error:
        description = callback_result.get("error_description") or ""
        detail = f"{error}: {description}" if description else str(error)
        output_callback(f"Error: authorization failed: {detail}")
        return None

    if not callback_result.get("code"):
        output_callback("Error: Authentication timed out or no code received.")
        return None

    if callback_result.get("state") != state:
        output_callback("Error: OAuth state mismatch (possible CSRF).")
        return None

    output_callback("Exchanging authorization code for tokens...")
    tokens = await _exchange_code(
        token_endpoint=token_endpoint,
        resource=resource,
        code=callback_result["code"],
        code_verifier=code_verifier,
        redirect_uri=callback_server.callback_url,
        client_id=client_id,
        client_secret=client_secret,
        output_callback=output_callback,
    )
    if tokens is None:
        return None
    client = await _finish(tokens)
    if client is None:
        return None
    output_callback("Authentication successful!")
    return client


async def has_stored_tokens(server_name: str) -> bool:
    """True when a stored token with a non-empty access token exists."""
    tokens = await FileTokenStorage(server_name).get_tokens()
    return bool(tokens and tokens.access_token)


async def get_authenticated_client(server_name: str) -> httpx2.AsyncClient | None:
    """Get an authenticated httpx client if tokens exist.

    Returns an authenticated httpx client or None if no tokens are available.
    """
    storage = FileTokenStorage(server_name)
    tokens = await storage.get_tokens()

    if tokens and tokens.access_token:
        return httpx2.AsyncClient(
            timeout=SSRF_TIMEOUT,
            headers={"Authorization": f"Bearer {tokens.access_token}"},
            follow_redirects=False,
        )
    return None

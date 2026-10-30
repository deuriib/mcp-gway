"""Token storage adapter implementing TokenStoragePort."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp_gway.domain.policy import config_dir
from mcp_gway.domain.ports import TokenStoragePort
from mcp_gway.secureio import secure_atomic_write_text


class FileTokenStorageAdapter(TokenStoragePort):
    """Adapter storing OAuth / credentials tokens in filesystem."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._dir = base_dir or (config_dir() / "tokens")
        self._dir.mkdir(parents=True, exist_ok=True)

    def _token_path(self, server_name: str) -> Path:
        return self._dir / f"{server_name}.json"

    def get_token(self, server_name: str) -> dict[str, Any] | None:
        p = self._token_path(server_name)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save_token(self, server_name: str, token: dict[str, Any]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        p = self._token_path(server_name)
        secure_atomic_write_text(p, json.dumps(token, indent=2))

    def delete_token(self, server_name: str) -> bool:
        p = self._token_path(server_name)
        if p.exists():
            p.unlink()
            return True
        return False

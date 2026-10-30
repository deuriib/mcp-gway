"""Local command policy — allow-list + cwd/env gates (facade).

Re-exports domain policy definitions for backward compatibility.
"""

from __future__ import annotations

from mcp_gway.domain.policy import (
    ALLOW_LIST_ENV,
    DEFAULT_ALLOW_LIST,
    ENV_DENYLIST_EXACT,
    ENV_DENYLIST_PREFIXES,
    PolicyDecision,
    audit_local_action,
    check_basename_allowed,
    check_cwd,
    check_environment,
    check_local_command,
    config_dir,
    get_allow_list,
    home_dir,
    logger,
    resolve_binary,
    validate_command_syntax,
)

__all__ = [
    "ALLOW_LIST_ENV",
    "DEFAULT_ALLOW_LIST",
    "ENV_DENYLIST_EXACT",
    "ENV_DENYLIST_PREFIXES",
    "PolicyDecision",
    "audit_local_action",
    "check_basename_allowed",
    "check_cwd",
    "check_environment",
    "check_local_command",
    "config_dir",
    "get_allow_list",
    "home_dir",
    "logger",
    "resolve_binary",
    "validate_command_syntax",
]

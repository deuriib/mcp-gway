from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "antigravity"

MANIFEST_PATH = (
    REPO_ROOT / "plugin.json"
    if (REPO_ROOT / "plugin.json").exists()
    else PLUGIN_DIR / "plugin.json"
)
MCP_CONFIG_PATH = (
    REPO_ROOT / "mcp_config.json"
    if (REPO_ROOT / "mcp_config.json").exists()
    else PLUGIN_DIR / "mcp_config.json"
)
HOOKS_PATH = (
    REPO_ROOT / "hooks.json"
    if (REPO_ROOT / "hooks.json").exists()
    else PLUGIN_DIR / "hooks.json"
)
RULES_PATH = (
    REPO_ROOT / "rules" / "mcp-gway.md"
    if (REPO_ROOT / "rules" / "mcp-gway.md").exists()
    else (PLUGIN_DIR / "rules" / "AGENTS.md")
)
SKILL_PATH = REPO_ROOT / "skills" / "mcp-gway" / "SKILL.md"
REINJECT_SCRIPT = (
    REPO_ROOT / "scripts" / "reinject.mjs"
    if (REPO_ROOT / "scripts" / "reinject.mjs").exists()
    else (PLUGIN_DIR / "scripts" / "reinject.mjs")
)
INSTALL_PATH = (
    REPO_ROOT / "INSTALL.md"
    if (REPO_ROOT / "INSTALL.md").exists()
    else (PLUGIN_DIR / "INSTALL.md")
)


def test_bundle_structure():
    """REQ-F-001: Assert all required files exist in the Antigravity plugin bundle."""
    required_files = [
        MANIFEST_PATH,
        MCP_CONFIG_PATH,
        HOOKS_PATH,
        REINJECT_SCRIPT,
        RULES_PATH,
        SKILL_PATH,
        INSTALL_PATH,
    ]
    for file_path in required_files:
        assert file_path.exists(), f"Missing required bundle file: {file_path}"


def test_plugin_manifest():
    """REQ-F-002: Assert plugin.json is valid JSON and contains required manifest fields."""
    with MANIFEST_PATH.open() as f:
        data = json.load(f)

    assert data.get("name") == "mcp-gateway"
    assert data.get("version") == "4.3.0"
    assert "$schema" in data
    assert "description" in data


def test_skill_parity():
    """REQ-F-003: Assert skill SKILL.md exists and contains gateway management instructions."""
    assert SKILL_PATH.exists()
    content = SKILL_PATH.read_text()
    assert "mcp-gway" in content


def test_rules_content():
    """REQ-F-004: Assert rules contain Gateway Protocol guidance and marker."""
    content = RULES_PATH.read_text()

    assert "<!-- MCP-GWAY v4.3.0 -->" in content
    assert "gateway_listToolFiles" in content
    assert "gateway_readToolFile" in content
    assert "gateway_executeToolCode" in content
    assert "brackets, not dot" in content
    assert "Anti-Patterns" in content


def test_hooks_json_schema():
    """REQ-F-005: Assert hooks.json adheres to official Antigravity hook schema."""
    with HOOKS_PATH.open() as f:
        data = json.load(f)

    # Must be a map of hook names to event handlers
    assert isinstance(data, dict)
    assert "mcp-gateway-reinject" in data
    hook_config = data["mcp-gateway-reinject"]
    assert "PreInvocation" in hook_config
    assert isinstance(hook_config["PreInvocation"], list)
    assert len(hook_config["PreInvocation"]) >= 1

    handler = hook_config["PreInvocation"][0]
    assert handler.get("type") == "command"
    assert "reinject.mjs" in handler.get("command", "")
    # The hook must run through Node: no shell wrapper, no bash dependency.
    assert handler.get("command", "").startswith("node ")
    assert " sh " not in handler.get("command", "")


def test_reinject_script_execution(tmp_path: Path):
    """REQ-F-005: Assert reinject.mjs outputs ephemeralMessage when marker absent, and empty when present."""
    # 1. Without marker in transcript
    empty_transcript = tmp_path / "transcript_empty.jsonl"
    empty_transcript.write_text('{"stepIdx": 1, "content": "hello"}\n')

    payload = json.dumps({"transcriptPath": str(empty_transcript), "invocationNum": 0})
    res = subprocess.run(
        ["node", str(REINJECT_SCRIPT)],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    out = json.loads(res.stdout)
    assert "injectSteps" in out
    assert len(out["injectSteps"]) == 1
    assert "MCP-GWAY v4.3.0" in out["injectSteps"][0]["ephemeralMessage"]

    # 2. With marker already in transcript -> dedupe, empty injectSteps
    marked_transcript = tmp_path / "transcript_marked.jsonl"
    marked_transcript.write_text(
        '{"stepIdx": 1, "content": "<!-- MCP-GWAY v4.3.0 -->"}\n'
    )

    payload_marked = json.dumps(
        {"transcriptPath": str(marked_transcript), "invocationNum": 1}
    )
    res_marked = subprocess.run(
        ["node", str(REINJECT_SCRIPT)],
        input=payload_marked,
        text=True,
        capture_output=True,
        check=True,
    )
    out_marked = json.loads(res_marked.stdout)
    assert out_marked.get("injectSteps") == []

    # 3. Missing/unreadable transcript must degrade to an injection, never raise.
    res_missing = subprocess.run(
        ["node", str(REINJECT_SCRIPT)],
        input=json.dumps({"transcriptPath": str(tmp_path / "does-not-exist.jsonl")}),
        text=True,
        capture_output=True,
        check=True,
    )
    assert len(json.loads(res_missing.stdout)["injectSteps"]) == 1


def test_mcp_config_loopback_and_no_secrets():
    """REQ-F-006 & REQ-NF-002: Assert mcp_config is loopback and free of secrets."""
    with MCP_CONFIG_PATH.open() as f:
        data = json.load(f)

    assert "mcpServers" in data
    assert "gateway" in data["mcpServers"]
    gateway_conf = data["mcpServers"]["gateway"]
    assert "serverUrl" in gateway_conf
    assert "127.0.0.1" in gateway_conf["serverUrl"]

    raw_text = MCP_CONFIG_PATH.read_text().lower()
    for secret_word in ["password", "secret", "bearer", "token", "key"]:
        assert secret_word not in raw_text


def test_install_docs():
    """REQ-F-007: Assert INSTALL.md contains verification and rollback."""
    content = INSTALL_PATH.read_text()

    assert "Verification Matrix" in content
    assert "Rollback" in content
    assert "127.0.0.1:8080" in content


def test_no_pii_in_bundle():
    """REQ-NF-003: Ley 172-13 privacy minimization across bundle files."""
    bundle_files = [
        MANIFEST_PATH,
        MCP_CONFIG_PATH,
        HOOKS_PATH,
        RULES_PATH,
        SKILL_PATH,
        INSTALL_PATH,
        REINJECT_SCRIPT,
    ]
    for path in bundle_files:
        if path.is_file():
            text = path.read_text(errors="ignore")
            # Ensure no credentials / PII leak
            for pattern in ["@google.com", "api_key", "password=", "secret="]:
                assert pattern not in text, f"Potential PII/secret in {path}: {pattern}"

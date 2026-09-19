from __future__ import annotations

import json
from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "antigravity"


def test_bundle_structure():
    """REQ-F-001: Assert all required files exist in the Antigravity plugin bundle."""
    required_files = [
        PLUGIN_DIR / "plugin.json",
        PLUGIN_DIR / "mcp_config.json",
        PLUGIN_DIR / "hooks.json",
        PLUGIN_DIR / "scripts" / "reinject.sh",
        PLUGIN_DIR / "rules" / "AGENTS.md",
        PLUGIN_DIR / "skills" / "mcp-gway" / "SKILL.md",
        PLUGIN_DIR / "INSTALL.md",
    ]
    for file_path in required_files:
        assert file_path.exists(), f"Missing required bundle file: {file_path}"


def test_plugin_manifest():
    """REQ-F-002: Assert plugin.json is valid JSON and contains required manifest fields."""
    manifest_path = PLUGIN_DIR / "plugin.json"
    with manifest_path.open() as f:
        data = json.load(f)

    assert data.get("name") == "mcp-gateway"
    assert data.get("version") == "2.8.0"
    assert "$schema" in data
    assert "description" in data


def test_skill_parity():
    """REQ-F-003: Assert skill SKILL.md has parity with root skill."""
    root_skill = REPO_ROOT / "skills" / "mcp-gway" / "SKILL.md"
    plugin_skill = PLUGIN_DIR / "skills" / "mcp-gway" / "SKILL.md"

    assert root_skill.exists()
    assert plugin_skill.exists()
    assert plugin_skill.read_text() == root_skill.read_text()


def test_rules_content():
    """REQ-F-004: Assert rules/AGENTS.md contains Gateway Protocol guidance and marker."""
    rules_path = PLUGIN_DIR / "rules" / "AGENTS.md"
    content = rules_path.read_text()

    assert "<!-- MCP-GWAY v2.8.0 -->" in content
    assert "gateway_listToolFiles" in content
    assert "gateway_readToolFile" in content
    assert "gateway_executeToolCode" in content
    assert "brackets, not dot" in content
    assert "Anti-Patterns" in content


def test_hooks_json_schema():
    """REQ-F-005: Assert hooks.json adheres to official Antigravity hook schema."""
    hooks_path = PLUGIN_DIR / "hooks.json"
    with hooks_path.open() as f:
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
    assert "reinject.sh" in handler.get("command", "")


def test_reinject_script_execution(tmp_path: Path):
    """REQ-F-005: Assert reinject.sh outputs ephemeralMessage when marker absent, and empty when present."""
    reinject_script = PLUGIN_DIR / "scripts" / "reinject.sh"

    # 1. Without marker in transcript
    empty_transcript = tmp_path / "transcript_empty.jsonl"
    empty_transcript.write_text('{"stepIdx": 1, "content": "hello"}\n')

    payload = json.dumps({"transcriptPath": str(empty_transcript), "invocationNum": 0})
    res = subprocess.run(
        ["sh", str(reinject_script)],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
    )
    out = json.loads(res.stdout)
    assert "injectSteps" in out
    assert len(out["injectSteps"]) == 1
    assert "MCP-GWAY v2.8.0" in out["injectSteps"][0]["ephemeralMessage"]

    # 2. With marker already in transcript -> dedupe, empty injectSteps
    marked_transcript = tmp_path / "transcript_marked.jsonl"
    marked_transcript.write_text('{"stepIdx": 1, "content": "<!-- MCP-GWAY v2.8.0 -->"}\n')

    payload_marked = json.dumps({"transcriptPath": str(marked_transcript), "invocationNum": 1})
    res_marked = subprocess.run(
        ["sh", str(reinject_script)],
        input=payload_marked,
        text=True,
        capture_output=True,
        check=True,
    )
    out_marked = json.loads(res_marked.stdout)
    assert out_marked.get("injectSteps") == []


def test_mcp_config_loopback_and_no_secrets():
    """REQ-F-006 & REQ-NF-002: Assert mcp_config is loopback and free of secrets."""
    mcp_config_path = PLUGIN_DIR / "mcp_config.json"
    with mcp_config_path.open() as f:
        data = json.load(f)

    assert "mcpServers" in data
    assert "gateway" in data["mcpServers"]
    gateway_conf = data["mcpServers"]["gateway"]
    assert "serverUrl" in gateway_conf
    assert "127.0.0.1" in gateway_conf["serverUrl"]

    raw_text = mcp_config_path.read_text().lower()
    for secret_word in ["password", "secret", "bearer", "token", "key"]:
        assert secret_word not in raw_text


def test_install_docs():
    """REQ-F-007: Assert INSTALL.md contains verification and rollback."""
    install_path = PLUGIN_DIR / "INSTALL.md"
    content = install_path.read_text()

    assert "Verification Matrix" in content
    assert "Rollback" in content
    assert "127.0.0.1:8080" in content


def test_no_pii_in_bundle():
    """REQ-NF-003: Ley 172-13 privacy minimization across bundle files."""
    for path in PLUGIN_DIR.rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            # Ensure no credentials / PII leak
            for pattern in ["@google.com", "api_key", "password=", "secret="]:
                assert pattern not in text, f"Potential PII/secret in {path}: {pattern}"

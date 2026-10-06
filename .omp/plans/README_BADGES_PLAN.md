# Plan: README Badges — Product-Focused Improvement

## Context
Current README has 3 basic badges (PyPI version, Python versions, License). From a product perspective, badges should communicate: **maturity**, **trust signals**, **key differentiators**, and **adoption health** at a glance. The improvements add verifiable badges that reflect what this product actually delivers (Code Mode, single endpoint, observability, local-first security) while keeping noise low.

## Approach

### 1. Add CI/Tests badge (verifiable, builds trust)
- **Target**: Line 3-5 in README.md (badge block)
- **Action**: Add GitHub Actions "Tests" workflow status badge
- **Reason**: The test workflow runs on every push/PR for Python 3.12 and 3.13 — this is a real, passing signal
- **Badge**: `https://github.com/deuriib/mcp-gateway/actions/workflows/test.yml/badge.svg`
- **Link**: `https://github.com/deuriib/mcp-gateway/actions/workflows/test.yml`

### 2. Add Release workflow badge (shows automated publishing)
- **Target**: Same badge block
- **Action**: Add "Release" workflow badge
- **Reason**: Tag-triggered release with PyPI trusted publishing — signals professional release hygiene
- **Badge**: `https://github.com/deuriib/mcp-gateway/actions/workflows/release.yml/badge.svg`
- **Link**: `https://github.com/deuriib/mcp-gateway/actions/workflows/release.yml`

### 3. Add Code Style: Ruff badge (signals modern Python hygiene)
- **Target**: Same badge block
- **Action**: Add Ruff badge
- **Reason**: Project uses Ruff for linting + formatting (verified in test.yml and pyproject.toml)
- **Badge**: `https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json`
- **Link**: `https://github.com/astral-sh/ruff`

### 4. Add PyPI Downloads badge (adoption signal)
- **Target**: Same badge block
- **Action**: Add monthly downloads from pepy.tech
- **Reason**: Real adoption metric; product folks look for this
- **Badge**: `https://static.pepy.tech/badge/mcp-gway/month`
- **Link**: `https://pepy.tech/project/mcp-gway`

### 5. Add "MCP Protocol" badge (key differentiator — this IS an MCP gateway)
- **Target**: Same badge block
- **Action**: Add custom badge highlighting MCP compatibility
- **Reason**: Core product positioning — works with Pi, Antigravity, Claude Desktop, Cursor
- **Badge**: `https://img.shields.io/badge/MCP-Protocol-blue?logo=modelcontextprotocol`
- **Link**: `https://modelcontextprotocol.io/`

### 6. Add "Code Mode" badge (unique differentiator)
- **Target**: Same badge block
- **Action**: Add badge highlighting the 4 meta-tools lazy discovery feature
- **Reason**: This is THE unique feature — agents discover schemas on demand instead of loading all upfront
- **Badge**: `https://img.shields.io/badge/Code%20Mode-Lazy%20Discovery-purple`
- **Link**: `#code-mode` (anchor in same README)

### 7. Add "Local-First Security" badge (key trust signal for operators)
- **Target**: Same badge block
- **Action**: Add badge highlighting loopback-only default + allow-list
- **Reason**: Operators care about this; documented in README lines 89-104
- **Badge**: `https://img.shields.io/badge/Local--First-Security-green`
- **Link**: `#local-first-security` (anchor in same README)

### 8. Add "Observability Built-in" badge (health/metrics/probes)
- **Target**: Same badge block
- **Action**: Add badge for /health, /ready, /live, /metrics, correlation IDs
- **Reason**: Documented extensively in README lines 106-146; zero vendor lock-in
- **Badge**: `https://img.shields.io/badge/Observability-Built--in-orange`
- **Link**: `#observability---logs--metrics--health-approach-c-v240`

### 9. Reorder badges for product narrative
- **Order** (top to bottom, left to right):
  1. Tests (CI) — maturity
  2. Release — release hygiene
  3. PyPI version — current version
  4. Python versions — compatibility
  5. License — legal
  6. Code Style: Ruff — code quality
  7. PyPI Downloads — adoption
  8. MCP Protocol — ecosystem
  9. Code Mode — unique feature
  10. Local-First Security — trust
  11. Observability Built-in — production readiness

### 10. Keep badge block compact (max 2 rows visually)
- Use shields.io style consistency
- Group: CI/Release/Version/Python/License on row 1
- Group: Ruff/Downloads/MCP/CodeMode/Security/Observability on row 2

## Critical Files & Anchors
- `README.md` lines 1-8 — badge block to rewrite entirely
- `README.md` lines 220-229 — Code Mode section (anchor target)
- `README.md` lines 89-104 — Local-First Security section (anchor target)
- `README.md` lines 106-146 — Observability section (anchor target)

## Verification
- All badge URLs resolve (test with curl/HEAD)
- Links navigate to correct sections or external pages
- Visual rendering: open README in GitHub after edit, confirm 2-row layout, no broken images
- No badge makes a claim not backed by code/config (e.g., "Code Mode" = real feature, "Local-First" = documented behavior)

## Assumptions & Contingencies
- If any custom badge URL 404s → replace with generic shields.io equivalent
- If GitHub Actions badges show "unknown" initially → they'll resolve on next workflow run; keep them
- Anchor links (`#code-mode`, etc.) must match actual heading IDs in rendered README (GitHub auto-generates from headings)
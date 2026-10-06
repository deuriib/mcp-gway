# Development

```bash
# Install dependencies
uv sync --all-groups  # installs dev group with pre-commit
uv run pre-commit install  # once per clone — hooks already configured in .pre-commit-config.yaml

# Run checks
uv run pre-commit run --all-files  # ruff + ruff-format + hygiene (trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files)
uv run pytest -v  # 647 tests — CLI, MCP, Code Mode, stdio, OAuth, observability
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Verification probes (no Node, no build)
curl -s http://127.0.0.1:8080/health | jq .status             # "ok"
curl -s http://127.0.0.1:8080/ready | jq .status              # "ready"
curl -s http://127.0.0.1:8080/metrics | head -n 5             # # HELP mcp_gway_...

# Local-first check
mcp-gway serve --transport http --host 0.0.0.0 2>&1 | grep -q "requires MCP_GWAY_ALLOW_REMOTE" && echo "gate ok"
```

## Toolchain (mise)

```bash
mise install
uv sync --all-groups  # installs dev group with pre-commit
```

Pre-commit is already in place (`.pre-commit-config.yaml` — `ruff` v0.16.4, `ruff-format`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`).

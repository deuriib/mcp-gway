## Context

`mcp-gway refresh` prints a redundant `Try: mcp-gway refresh <name> --auth` hint when zero tools are discovered for a server (`src/mcp_gway/cli.py:990-992`). This guidance is often stale or unhelpful, as the user may already be using the correct command or have an issue that `--auth` does not solve.

## Approach

- Modify `src/mcp_gway/cli.py`: Remove the line `click.echo(f"Try: mcp-gway refresh {server_name} --auth")` inside the `if not discovered:` block in the `refresh` command implementation.
- Maintain the preceding warning message (`Warning: No tools discovered for {server_name}.`) and the associated telemetry logging to preserve existing observability.
- Add/update a test case in `tests/test_edgecases_cli.py` to verify that `refresh` with zero discovered tools emits only the warning and NOT the suggested hint.

## Critical files & anchors

- `src/mcp_gway/cli.py`: `refresh` command logic (around L990).
- `tests/test_edgecases_cli.py`: `test_refresh_remote_ok` or similar for verification.

## Verification

1. Create a test case in `tests/test_edgecases_cli.py` that mocks `refresh_server` to return `[]` (zero tools).
2. Run the test: `uv run pytest tests/test_edgecases_cli.py`.
3. Verify that the output contains "Warning: No tools discovered" but *does not* contain "Try: mcp-gway refresh".

## Assumptions & contingencies

- None; the behavior change is straightforward.

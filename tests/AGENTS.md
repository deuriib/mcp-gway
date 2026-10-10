# tests — AGENTS

`DOMAINS: Testing`

## OVERVIEW

Mirror of `src/` layout; hermetic DNS stub + shared fixtures; full suite <30s target.

## WHERE TO LOOK

| Task | Location | Notes |
| Shared fixtures | `conftest.py`, `fixtures/` + `helpers/` | `tmp_path` isolation |
| Unit scope | `test_*.py` per module | asyncio auto, monkeypatch mocks |
| Policy hardening | `test_policy_local_commands.py`, `test_feat006_harden.py` | bypass + regate cases |
| Node surface | `pi_extension.test.mjs` | 34 checks incl. declarative `mcp.json` `gateway` contract + `gw_add`/`gw_remove` argv + uv-missing notify |

## GUARDRAILS (THIS DIR)

- Every behavior/fix change ships with a test; docs-only exempt.
- Verify invariants/transitions/side-effects — count-only assertions fail.
- Zero flaky tolerance: quarantine + root-cause, never hide.

## ANTI-PATTERNS

- No wiring/forwarding/mock-echo tests; no re-pinning incidental behavior.

# REVIEW-RISK — SPEC-TRANSPORT-SEPARATION-001

**Reviewer role:** risk (blast radius, backward compatibility, operational/adoption risk — not code style, not exploit mechanics)
**Packet:** docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md (reference-only)
**Scope:** 88f47fd, bd2d11a, dedf480, d42085f on `feat/separate-mcp-transport` vs parent 531cf3c
**Date:** 2026-09-22

---

## Verdict: APPROVE (CONDITIONAL — 3 conditions must clear before merge)

The change itself is sound, tightly scoped, and reversible. Approval is conditional because the packet's own architecture sign-off box is unchecked, the release pipeline will auto-publish this behavior change as a MINOR with no consumer-facing warning, and one shipped consumer's client transport is unverified against the recommended config. None of these are code defects; all three are pre-merge decisions that belong to owners, not to the diff.

**Conditions (⚠️ → orchestrator maps to CONDITIONAL):**
1. Semver decision recorded before merge: `feat!` + `BREAKING CHANGE` footer (→ 3.0.0) **or** explicit accepted-risk for MINOR 2.12.0 with a CHANGELOG entry (R1, R4).
2. Architecture owner signs the public route-contract change; check `PROPOSED_CHANGES.md:53` (R5).
3. Confirm the Antigravity `serverUrl` client's transport; if SSE-only, fix `plugins/antigravity/INSTALL.md` pairing before release (R2).

---

## Consumer break analysis (checklist item 1)

Pre-change contract: **one dual app served GET + POST /mcp + /mcp/messages regardless of `--transport`** — documented in old help text (`git show 531cf3c:src/mcp_gway/cli.py:587` — *"http and sse share the same app"*) and old README (`531cf3c:README.md:159` — *"`http`/`sse` share `Gateway.app`"*). After: route set is exclusive per transport (`src/mcp_gway/gateway.py:320-337`), default `transport="http"` (`gateway.py:172`).

| # | Consumer (evidence) | Client transport | Config pairing | Breaks under default settings? |
|---|---|---|---|---|
| C1 | OpenCode plugin `plugins/opencode/mcp-gateway.ts:42,105-119` (`type: "remote"`, `url: http://127.0.0.1:8080/mcp`) | Streamable HTTP (POST) — per repo's own pairing `plugins/opencode/INSTALL.md:15,108` (`serve --transport http`) | `--transport http` (recommended) | **No** — POST /mcp works. Breaks only if operator overrides to `--transport sse` (POST → 405 `gateway.py:528-536`) |
| C2 | Claude Desktop example `README.md:135-147` (bare `"url"`, no `type`) | Unpinned — bare `url` has been SSE-era and streamable-era depending on client version | None documented (section never says which `serve --transport` to run) | **Conditional break** — worked before under any flag; now depends on (client transport × chosen flag). README gives no pairing → first-run failure risk. **Medium** |
| C3 | Antigravity plugin `plugins/antigravity/mcp_config.json` + root `mcp_config.json:4` (`serverUrl`), `plugins/antigravity/INSTALL.md:6,18,62,77,79` | **Unverified** — `serverUrl` (no `type`) is the SSE-era remote pattern per `docs/specs/50_archive/SPEC-ANTIGRAVITY-001.md:44-46` (contrasted with OpenCode's `type+url`); repo never states streamable support | Docs pin `serve --transport http` (`antigravity/INSTALL.md:18,77`) | **Unknown → potential High**: if the client is SSE-only, the *documented* config yields GET /mcp → 405 → total tool loss. Assumption flagged, not proven from repo (R2) |
| C4 | OpenCode `type: local` / stdio consumers (`README.md:160`, `mcp-gway mcp` alias) | stdio NDJSON | `serve --transport stdio` (CLI default, `cli.py:586-587`) | **No** — stdio serves no HTTP routes; `Gateway(registry)` at `cli.py:421` builds with default `http` but only `run_stdio_async` runs (REQ-TRANSPORT-007, `TEST_MATRIX.md:17,30`) |
| C5 | External watchdogs/synthetic probes using `GET /mcp` as liveness | SSE-shaped probe | any | **Breaks quietly** — 405 (not connection-refused); naive `2xx = up` checks flip to down on http-mode gateways. **Low** |
| C6 | Internal perf harness `docs/specs/30_delivery/perf_config.yaml:7` (`transport: "http"`) + `:10-18` (`mcp_get` = GET /mcp) ; `RUNBOOK-perf.md:29-39` (offers `--transport sse` then benchmarks POST paths) | mixed | mixed | **Yes (internal)** — mcp_get path returns 405 under http transport; POST paths return 405 under sse transport. Harness silently measures the 405 handler. **Medium→Low** (R6) |
| C7 | Pip users pinning `mcp-gway==2.11.3` | — | — | Rollback via version pin available (PyPI immutable only *after* publish — not yet published: master tip is 531cf3c = 2.11.3) |

**Checklist answer — `serve --transport sse` + HTTP-only client:** yes, this breaks. POST /mcp → `405 Allow: GET` with detail `"Streamable HTTP transport not enabled (serve --transport http)"` (`gateway.py:528-536`). Before the change this pairing worked because the flag was explicitly cosmetic (`531cf3c:cli.py:587`). Anyone who read the old docs and chose `sse` while using a modern HTTP client loses service on upgrade. Mitigating factor: the 405 body is self-remedial (names the exact flag to run), and `--transport sse` is now an honest opt-in, not a shared surface.

---

## Default `transport="http"` per entrypoint (checklist item 2)

**Right default.** Reasoning:
- `serve` default is `stdio` (`cli.py:586`) — no HTTP surface at all; http/sse are always explicitly chosen by the operator and the flag now drives the app 1:1 (`cli.py:638` → `cli.py:514` → `Gateway(..., transport=transport)`).
- Programmatic default `Gateway(registry)` → `"http"` matches the streamable-HTTP-first MCP spec direction; rationale recorded in alternatives table (`PROPOSED_CHANGES.md:46-48`).
- stdio path constructs the gateway without transport (`cli.py:421`) but never exposes routes — harmless, covered by REQ-TRANSPORT-007.
- The breakage is confined to *cross* pairings (sse-flag × http-client, http-flag × sse-client) that only worked by documented accident.

---

## Semver + auto-release behavior (checklist item 3)

- Parser config `pyproject.toml:43-46`: `minor_tags = ["feat"]`, `patch_tags` includes `fix`,`perf`,...; no `major_tags` override → python-semantic-release default detects `feat!` subject / `BREAKING CHANGE` footer as major.
- **As committed (`feat(transport): ...`), merge to `master` auto-publishes 2.12.0 (MINOR):** chain is push → Tests (`test.yml:4-7`) → workflow_run → Release (`release.yml:6-10,20,50-79`) → PSR version → build + PyPI publish (`release.yml:81-93`). No manual tag gate.
- **Does `feat` avoid an accidental breaking auto-release?** Only partially. It keeps the change out of the *patch* lane (`fix`/`perf` → 2.11.4 would be strictly worse), but it does **not** prevent auto-publication: the minor release fires deterministically on merge.
- **MINOR or MAJOR?** Strict semver says **MAJOR**: this removes previously-working, *documented* public behavior (`531cf3c:cli.py:587`, old README) — SSE clients on http-mode gateways and POST clients on sse-mode gateways now get 405, and `/mcp/messages` disappears under http (404). Default recommendation: **`feat!` + `BREAKING CHANGE` footer → 3.0.0**, unless the CTO records an explicit accepted-risk to ship as 2.12.0 (allowed breaks: serve default is stdio; error messages are self-remedial; rollback = pin 2.11.3). Decision owner: CTO/vasquez (release owner). Condition 1.

---

## Rollback (checklist item 4)

**`git revert` of the four commits is sufficient — verified.**

- `git diff --name-only 531cf3c..d42085f` = exactly 16 files: `src/` (2: `cli.py`, `gateway.py`), `tests/` (8), `docs/` (6: 4 contract docs + 3 packet files... 7 total docs incl. packet; no others).
- **No persisted state touched:** no `servers/*.json`/`*.pyi` registry format, no `models.py` schema, no `pyproject.toml` version, no env-var renames, no token/config migrations. Registry stays single-source with identical shape (`AGENTS.md` Registry section unchanged by dedf480).
- Revert order: `d42085f → dedf480 → bd2d11a → 88f47fd` (reverse) applies cleanly; reverting only src without tests leaves the suite red — revert all four together.
- Caveats: (a) `6fff6cc` (uv.lock 2.11.3 sync) sits atop the branch — independent, harmless, do not bundle into the revert; (b) PyPI is one-way: once 2.12.0 publishes, source revert requires a forward release. Today master = 531cf3c = 2.11.3 → not yet published, so revert path is fully open.

---

## ADR-010 AC-05 amendment discoverability (checklist item 5)

**Adequate, with a named gap.** No ADR file exists to amend — `docs/architecture/` does not exist (`ls` fails); the only ADR artifact in-tree is `docs/specs/12_adr/ADR-013-*.md`, and ADR-009/010 pointers were already dangling pre-change. The amendment *is* discoverable:
- `AGENTS.md` docs-tree line: *"(referenciado, ausente en repo; enmienda ADR-010 AC-05 2026-09-22: http/sse comparten el entrypoint `_serve_http`, NO la app — rutas `/mcp` separadas por transporte, sin fallback)"* — a maintainer following the ADR-010 pointer hits the amendment note immediately.
- `AGENTS.md` "Endpoints vivos" line carries the dated amendment + per-transport route sets.
- `docs/specs/10_design/API_CONTRACTS.md:15-23` — dated *"amended 2026-09-22 ... supersedes the previous 'unchanged'"* header, explicit route tables.

**Gap:** `PROPOSED_CHANGES.md:53` — `[ ] Architecture: cambio de contrato público de rutas → ADR-010 nota de enmienda en docs` is **unchecked**: the packet itself declares architecture sign-off outstanding while dedf480 already rewrote the public contract. A checkbox left open in a "gates green" packet (`d42085f` subject) is an accountability hole, not just bookkeeping (R5). Recommended: architecture owner signs → check the box; optionally drop a dated stub `docs/specs/12_adr/ADR-010-amendment.md` so the pointer resolves to an artifact.

---

## Residual risk table (checklist item 6)

| ID | Risk | Severity | Likelihood | Mitigation | Owner |
|----|------|----------|-----------|------------|-------|
| R1 | Plain `feat` → PSR auto-publishes behavior-breaking change as 2.12.0 on merge (`pyproject.toml:43-46`, `release.yml:6-10,81-93`) with no manual tag gate | **High** | High (deterministic on merge to master) | Decide pre-merge: `feat!` + `BREAKING CHANGE` footer (→3.0.0) **or** written accepted-risk for MINOR with CHANGELOG warning | CTO / release owner (vasquez) |
| R2 | Antigravity client (`serverUrl`, transport unverified) against docs-pinned `--transport http` (`antigravity/INSTALL.md:18`) → possible GET /mcp 405 = total tool loss for that consumer | **High** (if SSE-only; conditional) | Unknown → Medium pending confirmation | Verify Antigravity remote transport pre-merge; if SSE, repoint INSTALL pairing to `--transport sse`; record result in packet | Engineering owner |
| R3 | Mixed pairings break on upgrade (sse-flag × HTTP client, http-flag × SSE client) — old docs said the flag was cosmetic (`531cf3c:cli.py:587`) | Medium | Medium | CHANGELOG + upgrade note naming the pairing rule; 405 detail already self-remedial (`gateway.py:521-536`) | Engineering owner |
| R4 | No CHANGELOG `Unreleased` entry for this change (`CHANGELOG.md:3-6` has only perf/casing) → consumers get zero warning | Medium | High | Add breaking entry before merge (guardrail: Keep a Changelog) | Engineering owner |
| R5 | Public route contract rewritten while packet's Architecture approval box is unchecked (`PROPOSED_CHANGES.md:53`); no ADR artifact for the amendment | Medium | High | Architecture sign-off + check box; optional dated ADR-010 amendment stub in `docs/specs/12_adr/` | Architecture owner / orchestrator |
| R6 | Internal perf harness measures 405 handlers: `perf_config.yaml:7,10-18` (http transport + GET /mcp path), `RUNBOOK-perf.md:29-39` (sse then POST) | Medium→Low | High (whenever run) | Split harness paths per transport before next perf run; no release impact (bench script not yet in `scripts/`) | Engineering owner |
| R7 | Liveness probes using GET /mcp flip to 405 on http-mode gateways | Low | Low | Document probes must use `/health` (already the canonical probe) | Engineering owner |
| R8 | Future maintainer greps ADR-010, finds only AGENTS.md inline note (no canonical ADR doc) | Low | Medium | Amendment note at pointer site (done) + optional ADR stub | Architecture owner |

---

## Findings index (evidence)

- F1 — Exclusive route sets + default http: `src/mcp_gway/gateway.py:172,320-337,349,519-536`; propagation `src/mcp_gway/cli.py:514,638`; commit 88f47fd.
- F2 — Pre-change dual-app contract (breaking baseline): `git show 531cf3c:src/mcp_gway/cli.py:587`, `git show 531cf3c:README.md:159`.
- F3 — Consumer configs: `plugins/opencode/mcp-gateway.ts:42,105-119`, `plugins/opencode/INSTALL.md:15,118`, `plugins/antigravity/mcp_config.json`, `mcp_config.json:4`, `plugins/antigravity/INSTALL.md:18,77`, `README.md:135-147,160`.
- F4 — Semver: `pyproject.toml:27-46`, `.github/workflows/release.yml:6-10,50-93`, `.github/workflows/test.yml:4-7`; branch tip `6fff6cc` (chore, out of scope); master = 531cf3c = 2.11.3 (unreleased).
- F5 — Rollback surface: `git diff --name-only 531cf3c..d42085f` → 16 files (src 2 / tests 8 / docs 6); zero registry/schema/pyproject changes.
- F6 — ADR-010: `ls docs/architecture/` → absent; `find` → only `docs/specs/12_adr/ADR-013-*`; amendment recorded in `AGENTS.md` (docs tree + vivos lines) and `docs/specs/10_design/API_CONTRACTS.md:15-23`; `PROPOSED_CHANGES.md:53` unchecked.
- F7 — Test traceability present: `tests/test_transport_separation.py:38-141` (9 contract tests), `TEST_MATRIX.md:20-31`; suite claim 570 passed (`TEST_MATRIX.md:50`) — consumed by QA reviewer, not re-run here.

**Scope discipline observed:** no changes to `src/`, `tests/`, or packet files; no commit made.

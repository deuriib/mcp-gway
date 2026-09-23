# ARCHIVE-RECORD: admin-ui-3.1.0

**Spec:** no source file existed (`20_backlog` empty — interactive lane; canonical record = GATE_REPORT + TEST_MATRIX promoted below)
**Date:** 2026-09-23
**Gate verdict:** OPEN
**Commit(s):** `91dd912` (first-run CLOSED record), `fa2f404` (OPEN + C3 waivers W-01..W-13), `c5938d7` (handoff), `4a24a1d` (notes + archive), **release `eb8d5df`**
**Tag:** `v3.1.0` — annotated, **local, unpushed** (push = `uv build` + `pypi-publish` via `release.yml`, needs an explicit go)
**Ship type:** deploy

## Promoted (survive in `50_archive/admin-ui-3.1.0/`)

- [x] `GATE_REPORT.md` — from `40_workspace/quality-gate/admin-ui-3.1.0/`
- [x] `quality-gate/` — all 8 reviewer artifacts (quality-assurance, review-data, review-readability, review-refuter, review-reliability, review-resilience, review-risk, security-reviewer) moved wholesale — precedent: `SPEC-TRANSPORT-SEPARATION-001/quality-gate/` keeps reviewers live-cited from release notes
- [x] `HANDOFF.md` — from `40_workspace/engineering/` (this lane's file only; the sibling `PROPOSED_CHANGES.md` / `IMPLEMENTATION_PLAN.md` / `TEST_MATRIX.md` in that dir belong to SPEC-TEST-PERF-001, untouched)
- [x] `TEST_MATRIX.md` — from `40_workspace/execute/admin-ui-3.1.0/` — **promoted, not purged**: deliberate deviation from the template purge list, rationale = HANDOFF/DoD C4 links cite it as the REQ→test trace (dead-link = FAIL rule) + transport precedent keeps the full lane
- [x] `IMPLEMENTATION_PLAN.md` — same rationale as TEST_MATRIX
- [ ] `ADR-014-admin-surface-and-csp.md` — linked, not copied (`docs/specs/12_adr/` stays canonical)

## Purged (allowlist only, this `<spec-id>`)

- **None** — allowlist empty; full-lane promotion per transport precedent. Nothing deleted.

## Rollback plan

Per `RELEASE_NOTES.md` (v3.1.0): post-ship `git revert <release-commit>` restores the v3.0.1 tree (additive package, no registry schema/env/token changes — verified by risk + data reviews); pre-ship discard of the working tree per the W-04 inventory, preserving out-of-inventory untracked (`.impeccable/`, `PRODUCT.md`); consumers pin `pip install mcp-gway==3.0.1`. Owner: engineering. ETA <10 min.

## Notes

- Other SPEC lanes present in `40_workspace` during this archive: `architecture/` (antigravity/perf/mgw-alias reviews), `backend/` (SPEC-TEST-PERF-001 + READY-001), `quality-gate/{SPEC-MGW-001, SPEC-PERF-001, SPEC-SERVER-CAPS-001, SPEC-TEST-PERF-001}`, `verify-handoff/*` — none in-flight (specs already shipped/stalled; newest sibling write Sep 22; no concurrent session) → archive not aborted; purge allowlist = `admin-ui-3.1.0` only, zero sibling files touched.
- Residual risk / open conditions: waivers **W-01..W-13** — full three-block records, owners and expiries in `quality-gate/GATE_REPORT.md` C3 (default expiry 2026-12-22; pre-tag: W-02 CDN vendoring, W-04 release commit (**satisfied** by `eb8d5df`), W-05 doc mirror; GA: W-13 multi-user auth; core-release: W-01 sandbox interrupt/step-limit).
- Lows stay backlog (not waived): 320px toolbar Δ5.4 cosmetic, ragged button heights band, 404-vs-405 tools PUT, no `pytest-timeout`, empty-state copy, toast auto-dismiss.
- Feature tree shipped in release commit `eb8d5df`; out-of-inventory untracked (`.impeccable/`, `PRODUCT.md`) excluded and still untracked — **W-04 expiry condition satisfied** (commit + tag landed together, before any push).

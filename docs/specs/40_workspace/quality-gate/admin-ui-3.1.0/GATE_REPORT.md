# Quality Gate Report: admin-ui-3.1.0

**Date:** 2026-09-23
**Gate Status:** CLOSED
**Domains Touched:** engineering, security (+ data lens)

## Reviewer Verdicts

| Domain          | Reviewer (actual agent)  | Verdict     | Findings | Artifact                          |
| --------------- | ------------------------ | ----------- | -------- | --------------------------------- |
| engineering     | review-readability       | conditional | 17       | `review-readability.md`           |
| engineering     | review-reliability       | closed      | 13       | `review-reliability.md`           |
| engineering     | review-resilience        | conditional | 6        | `review-resilience.md`            |
| engineering     | review-risk              | conditional | 7        | `review-risk.md`                  |
| engineering     | review-refuter           | conditional | 5        | `review-refuter.md`               |
| engineering     | quality-assurance        | conditional | 6        | `quality-assurance.md`            |
| engineering     | review-data (data lens)  | conditional | 7        | `review-data.md`                  |
| security        | security-reviewer        | closed      | 6        | `security-reviewer.md`            |

## Blocking Findings (drive CLOSED)

1. **RL-001 / SEC-002 / DAT-001 — High — OAuth partial edit destroys stored credentials.**
   `admin/routes.py:888-896`: any non-blank OAuth field replaces the whole `oauth`
   object → stored `clientSecret` dropped, `clientId` re-minted, while the form
   promises per-field "blank keeps current" (`pages/servers.py:550-569`).
   Proven live by three independent reviewers (scope-only save → secret gone).
   Owner: engineering (admin routes).

2. **SEC-001 — High — `_gate` never validates the `Host` header.**
   `admin/routes.py:94-109` (0 host checks in `src/`): `curl -H
   'Host: evil.attacker.example' 127.0.0.1:8090/` → 200. DNS-rebinding chain to
   same-origin CSRF-token read (`layout.py:255`) + URL-swap keeping stored
   Authorization (`routes.py:875-896`) → credential forwarding to attacker.
   Owner: engineering (gateway).

3. **RL-002 — High — Code Mode execute timeout never fires; process-wide starvation.**
   `admin/routes.py:1065-1075` + pre-existing root cause `sandbox.py:110-119`:
   GIL monopoly starves the uvicorn loop (probes 2/135 ticks under load);
   `_validate_code` does not block loops; nominal `timeout=1.0` ran 6.8s.
   Owner: engineering (admin trigger) + core owner (sandbox).

## Conditions for Opening (from conditional reviewers; summary)

- [ ] COND-RD: readability Mediums RD-001..RD-004 fixed or accepted (module
      shadowing `routes.py:846`; dead `oauth_port` field `servers.py:286`;
      oversized handlers; 4× copy-paste) — Lows to backlog.
- [ ] COND-RES: resilience Mediums F-1..F-3 addressed or accepted-risk logged
      with owner+expiry (Tailwind/htmx CDN-only no local fallback;
      refresh-all aggregate up to N×300s `routes.py:667-686`; false-green
      `/health` on corrupt registry `observability/health.py:13-27`).
- [ ] COND-RK: risk conditions — (1) pin/vendor or formally accept Tailwind CDN
      unpinned/no-SRI (`layout.py:40`, CSP `gateway.py:39-47`); (2) one atomic
      commit as rollback artifact + inventory-exclusion confirmation.
- [ ] COND-CE: refuter CE-001 — mobile REFRESH ALL/ADD SERVER not equal-width
      (constant Δ32px from padded button vs zero-basis wrapper,
      `servers.py:211-228`); CE-002 tools PUT path returns 404 (page path)
      not 405 (only partials path) — align behavior or documentation.
- [ ] COND-DAT: data lens — DAT-002/003 `retry_on_transport_error` dropped by
      `registry._config_data` (`registry.py:83-111,123-129`); DAT-004 declare
      purpose/TTL/deletion/owner for credential fields in `servers/*.json`.
- [ ] COND-QA: QA F-01 — test local branch of `PUT …/config` incl. update-time
      allow-list re-gate (`admin_update` untested); F-04 attach browser
      measurements for REQ-14 pixel claims (session evidence exists:
      bottoms=91 flush, add.r=1416 ≤ header, 900px wrap, overflowX false).

## C3 — CONDITIONAL/waiver review record (surgical, security-owned)

Not invoked — no waiver requested at this time. Gate is CLOSED on reviewer ❌
verdicts; remediation is the primary path. If a waiver path is elected, every
CONDITIONAL row above (6 conditional reviewers) is interrogated against the
three-block bar in `references/waiver-template.md`, one row each.

**Residual-risk (pending decision):** stored-OAuth credential loss on partial
admin edit + DNS-rebinding read of admin surface — owner: engineering;
expiry: before any release/tag of v3.1.0.

### PII checkpoint (co-sign)

Zero PII/secrets/tokens in this report or any reviewer artifact; secret values
quoted by reviewers are masked/placeholder-only; test data synthetic; evidence
is allowlisted (file:line, command output, verdicts) per Ley 172-13
minimization.

## Load Evidence (HARD STOP)

- [x] Stage skill loaded: `skill(quality-gate)` cited (trigger: "complete your
      workflow" → gate after execute-spec)
- [x] Domain owner/specialist role understood: orchestrator + dispatched
      reviewer roles cited per prompt (readability, reliability, resilience,
      risk, refuter, quality-assurance, data, security)
- [x] Execution mode declared: `subagents` (8 read orders in prompts)
- [x] Reviewer independence verified: strictly 1 dedicated subagent per
      reviewer; zero bundled reviews (refuter before quality-assurance honored)
- [x] Packet intact: `SPEC:<requirements #REQ> / HARD:<mode+constraints> /
      GATE:<verdicts> / DOMAINS:<engineering, security, data-lens>` — no
      full-context paste

## Escalations

- Defect convergence: RL-001 (High) = SEC-002 (Medium) = DAT-001 (High) — one
  root cause, three independent proofs → treated as High (data loss on admin
  action), single remediation ticket.
- RL-002 root cause predates this batch (`sandbox.py`); admin route adds a new
  trigger → split ownership: engineering (trigger) + core owner (sandbox).
- CE-003/CE-004/CE-005 contested Low findings (cross-page bottom flush, edit
  form has no Type select by design — server-side type rendering, md=rail not
  drawer) → backlog, not gate-blocking.

## Sign-off

- [ ] All reviewers pass or conditions met
- [ ] Gate Keeper: engineering owner
- [ ] Final authority (if waived): domain owners + orchestrator

**Gate verdict: CLOSED** — handoff (`verify-handoff`) and release
(`ship-release`) blocked until blocking findings are remediated and the gate is
re-run, or a three-block waiver is recorded by domain owners + orchestrator.

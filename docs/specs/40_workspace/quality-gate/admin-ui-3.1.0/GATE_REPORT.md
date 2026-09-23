# Quality Gate Report: admin-ui-3.1.0

**Date:** 2026-09-23
**Gate Status:** OPEN (2026-09-23 — re-gate flipped from CLOSED after approved
remediation; conditions cleared via C3 three-block waivers W-01..W-13 +
Round-2 fixes; first-run CLOSED verdict preserved below as history)
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

## Conditions for Opening — all cleared 2026-09-23

- [x] COND-RD → waived via **W-12** (RD-001..004 deferral with owner/expiry);
      Lows + RD-018..020 → backlog.
- [x] COND-RES → F-1 via **W-02**, F-2 via **W-09**, F-3 via **W-10**;
      F-6 chaos-gap → backlog Low.
- [x] COND-RK → RK-001 via **W-02**; RK-004 via **W-04** (reclassified
      fix→waiver-by-design, pre-tag expiry); RK-008 via **W-01**; Lows →
      backlog (incl. API_CONTRACTS count + missing ADR → docs backlog).
- [x] COND-CE → CE-001 **remediated in Round-2** (wrapper flex container;
      Δ=0 at 375/390/414/600, independently measured by refuter +
      orchestrator; md+ Δ7.34 ruled outside mobile/tablet scope); CE-007
      **retracted** (docstring truthful); CE-006 via **W-03**; CE-002 →
      backlog Low.
- [x] COND-DAT → DAT-002/003 via **W-11**; DAT-004 declaration recorded in
      **W-05** (mirror to docs = pre-tag condition); DAT-008 via **W-03**.
- [x] COND-QA → F-01 **remediated Round-2** (T-F01-1/2, mutation-proven);
      F-07 **remediated Round-2** (exact-set host test); F-04 **closed**
      (session measurements accepted as evidence per QA's own ruling);
      F-02/03/05/06 confirmed backlog Lows, not conditions.

## C3 — CONDITIONAL/waiver review record (surgical, security-owned)

Invoked 2026-09-23: domain owner (user, in-session election: "C3 waiver batch →
OPEN now") + orchestrator. Every CONDITIONAL interrogated against the
three-block bar in `references/waiver-template.md`; rows = conditionals; no
sample-of-one. Expiry default orchestrator-confirmed: 90 days = **2026-12-22**
or next release, whichever first; stricter pre-tag expiries noted per row.

| Waiver | Accepted-risk | Compensating-controls + owner | Expiry + re-review owner | Verdict |
|--------|---------------|-------------------------------|--------------------------|---------|
| W-01 F-7/RK-008/RL-002-partial (High — core GIL timeout + abandoned worker) | pass | pass | pass | **PASS** |
| W-02 SEC-003/RK-001/F-1 (CDN unpinned, no form-action/base-uri) | pass | pass | pass | **PASS** |
| W-03 CE-006/DAT-008/OBS-1 (uuid4 clientId coercion) | pass | pass | pass | **PASS** |
| W-04 RK-004 (uncommitted working tree) | pass | pass | pass | **PASS** |
| W-05 DAT-004 (credential-field purpose/TTL/deletion) | pass | pass | pass | **PASS** |
| W-06 RL-003/RL-004 (raw-500 error surfaces) | pass | pass | pass | **PASS** |
| W-07 RL-005 (oauth_port dead field) | pass | pass | pass | **PASS** |
| W-08 RL-006 (absent-field semantics divergence) | pass | pass | pass | **PASS** |
| W-09 F-2 (refresh-all N×300s aggregate) | pass | pass | pass | **PASS** |
| W-10 F-3 (false-green /health on corrupt registry) | pass | pass | pass | **PASS** |
| W-11 DAT-002/DAT-003 (registry schema drift, no versioning) | pass | pass | pass | **PASS** |
| W-12 RD-001..004 (readability hygiene deferral) | pass | pass | pass | **PASS** |
| W-13 SEC-006 (no auth beyond loopback, multi-user hosts) | pass | pass | pass | **PASS** |

### Three-block records (normative, one per waiver)

- **W-01** Accepted-risk: CPU-bound/looping Starlark can delay the execute
  response and briefly stall the local event loop; post-timeout worker may keep
  burning CPU — root pre-exists in `sandbox.py`, trigger is admin-only.
  Compensating-controls: loopback `_gate` + per-process CSRF + Host-gate
  (SEC-001 fixed) + clamp [0.1,30]s + honest docstring `routes.py:1091-1098`;
  owner: core owner (sandbox) + engineering owner (admin); evidence:
  `review-resilience.md` F-7, `review-risk.md` RK-008, `review-refuter.md`
  CE-007 retracted. Expiry: core step-limit/interrupt release or 2026-12-22,
  whichever first; re-review owner: core owner. Backlog: sandbox
  interrupt/step-limit + executor shutdown(wait=False) disposition.
- **W-02** Accepted-risk: unpinned `cdn.tailwindcss.com` (no SRI possible —
  runtime compiler) compromise could run script in the admin origin until
  vendored; `form-action`/`base-uri` absent from CSP.
  Compensating-controls: htmx pinned+SRI, CSP single constant limits
  script-src to 2 CDNs, loopback gate + CSRF + Host-gate now blocks the
  rebinding delivery path; owner: engineering; evidence: `security-reviewer.md`
  SEC-003, `review-risk.md` RK-001. Expiry: vendor/pin Tailwind + add
  `form-action`/`base-uri` before first v3.1.0 tag, else 2026-12-22; re-review
  owner: security owner.
- **W-03** Accepted-risk: non-UUID user-typed OAuth clientIds silently
  uuid4-coerced (`models.py:692-701`) → manual pre-registered OAuth uses wrong
  id; pre-existing at HEAD (enforced by `test_models.py`), no credential
  exposure (auth fails, no leak). Compensating-controls: identical CLI/web
  parity (no new surface), REQ-H1 merge safe (stored ids UUID-shaped);
  owner: models/core owner; evidence: `review-data.md` DAT-008 P4,
  `review-refuter.md` CE-006, `review-reliability.md` OBS-1. Expiry: v3.1.1 or
  2026-12-22, whichever first; re-review owner: engineering owner. Backlog:
  preserve manual clientIds or relax coercion.
- **W-04** Accepted-risk: batch has no atomic rollback commit; blanket
  `git clean` would hit out-of-inventory untracked (`.impeccable/`,
  `PRODUCT.md`, execute docs) — standing instruction keeps work uncommitted
  until ship. Compensating-controls: gate docs committed (`91dd912` + this
  record), full inventory enumerated in report + `git status`, selective
  rollback documented; owner: engineering/user; evidence: `review-risk.md`
  RK-004. Expiry: **before first v3.1.0 release tag** (no ship from dirty
  tree); re-review owner: orchestrator at `verify-handoff`/`ship-release`.
- **W-05** Accepted-risk: credential fields in `servers/*.json` lacked a
  declared purpose/TTL/deletion (REQ-NF-005). Declaration (this record =
  minimization): purpose = gateway server config display/update (machine
  config, not PII); TTL = gateway lifetime; deletion = `mcp-gway remove`
  (JSON) + token unlink `routes.py:988-1011` (separate 0o600 store, never
  rendered — masking verified); tests synthetic only.
  Compensating-controls: read-time masking + atomic writes + zero secrets in
  logs; owner: engineering; evidence: `review-data.md` DAT-004. Expiry: mirror
  this declaration into repo docs before first v3.1.0 tag, else 2026-12-22;
  re-review owner: engineering owner.
- **W-06** Accepted-risk: registry write IO failures surface as raw 500
  without htmx toast on add/refresh/toggle paths (config-save path already
  toasts); operator-local, atomic writes prevent corruption.
  Compensating-controls: atomic paired writes, probes unaffected, owner:
  engineering; evidence: `review-reliability.md` RL-003/RL-004. Expiry:
  2026-12-22; re-review owner: engineering. Backlog: extend `_reject` pattern.
- **W-07** Accepted-risk: add-form OAuth port input silently dropped (model
  lacks field, refresh uses 8989 default) → non-default-port AS fails visibly;
  no data loss. Compensating-controls: default 8989 standard, CLI parity (no
  flag either), owner: core/models; evidence: `review-reliability.md` RL-005,
  `review-readability.md` RD-002. Expiry: v3.1.1 or 2026-12-22; re-review
  owner: engineering. Backlog: wire field or remove input.
- **W-08** Accepted-risk: partial PUT semantics diverge (timeout→keep,
  enabled→False, tools_filter→"*") — web forms always send the complete field
  set, so the gap only bites API-style partial PUTs; loopback+CSRF still
  required. Compensating-controls: full-form UI path (evidence:
  `servers.py` form fields), gate + CSRF, owner: engineering;
  evidence: `review-reliability.md` RL-006. Expiry: 2026-12-22; re-review
  owner: engineering. Backlog: absent-field = keep-stored, align all three.
- **W-09** Accepted-risk: refresh-all runs sequential per-server refreshes
  (each ≤300s) → N slow remotes can hang one tab N×300s worst case; single
  path bounded + graceful (live 7.8s). Compensating-controls: loopback
  operator-initiated only, per-server timeouts bounded, navigation cancels the
  htmx request; owner: engineering; evidence: `review-resilience.md` F-2.
  Expiry: 2026-12-22; re-review owner: engineering. Backlog: aggregate budget
  or background task like `p_auth`.
- **W-10** Accepted-risk: corrupt registry → `/health checks.registry` stays
  "ok" (false green) while admin shows `config unreadable`; delayed detection,
  local only. Compensating-controls: admin UI surfaces the corruption on first
  visit, /ready /live semantics unchanged; owner: engineering/observability;
  evidence: `review-resilience.md` F-3 (live RS-104). Expiry: 2026-12-22;
  re-review owner: engineering. Backlog: `check_registry` counts read failures.
- **W-11** Accepted-risk: `retry_on_transport_error` checkbox is a no-op
  (whitelist omits it, 200 OK) and unknown/legacy JSON keys are destroyed on
  first dashboard save; no `schema_version` — data-loss class, mitigated by
  the fact no writer emits the key at HEAD. Compensating-controls: atomic
  writes, loopback+CSRF, current schema = known keys only; owner:
  registry/engineering; evidence: `review-data.md` DAT-002/DAT-003 (proof A1/A3).
  Expiry: 2026-12-22 **or immediately if any writer for
  `retry_on_transport_error` lands**; re-review owner: engineering. Backlog:
  whitelist key + preserve unknown keys or add `schema_version`.
- **W-12** Accepted-risk: module shadow (latent), oversized handlers
  (159/122 lines), 4× copy-paste, dead constants persist → maintainability
  debt, zero live runtime defect (RD-001 latent proven). Compensating-controls:
  ruff green, tests 621, naming/docstring discipline; owner: engineering;
  evidence: `review-readability.md` addendum. Expiry: 2026-12-22; re-review
  owner: engineering. Backlog: RD-001..004 + RD-018..020.
- **W-13** Accepted-risk: admin surface has no auth beyond loopback —
  multi-user host users share admin trust. Compensating-controls: loopback
  gate + CSRF + Host-gate + masked secrets (all re-proven this cycle); owner:
  engineering + product; evidence: `security-reviewer.md` SEC-006.
  Expiry: **v3.1.0 GA** (escalate to High if a shared-host deployment model
  appears before then); re-review owner: security owner.

**Residual-risk:** gateway freeze possible under operator-triggered runaway
Starlark until core sandbox gains interrupt/step-limit (W-01) — owner: core
owner; CDN script execution trust until vendored (W-02) — owner: engineering;
manual-OAuth clientId persistence broken until models fix (W-03) — owner:
models owner. Everything else: none beyond the recorded backlogs.

**Lows not waived (backlog per severity policy, confirmed by QA as
non-conditions):** CE-001@320 cosmetic Δ5.4, CE-009 ragged heights band,
CE-002/003/005/008, RK-002/003/005/006/007/009, SEC-004/005, DAT-005/006/007,
RL Lows, F-02/03/05/06, F-6 chaos-test gap, O-1 (pytest-timeout), QA class-only
pixel coverage gap, API_CONTRACTS 16/23-vs-17/24 doc mismatch, missing ADR for
`/` contract shift (RK-003 → docs backlog).

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

- [x] All reviewers pass or conditions met (2 pass + 6 conditional with ALL
      conditions cleared: Round-2 remediation + C3 waivers W-01..W-13)
- [x] Gate Keeper: engineering owner — user, in-session election
      "C3 waiver batch → OPEN now" (2026-09-23)
- [x] Final authority (waived conditions): domain owner (user, same election)
      + orchestrator; security waivers (W-01/W-02/W-13) co-signed under the
      same single-operator ownership (user = product + security owner)

**Gate verdict: OPEN** → handoff (`frame-ship:verify-handoff`) unblocked.

**Gate verdict (first run, 2026-09-23): CLOSED** — handoff (`verify-handoff`)
and release (`ship-release`) blocked until blocking findings are remediated and
the gate is re-run, or a three-block waiver is recorded by domain owners +
orchestrator.

## Re-gate addendum (2026-09-23, after approved remediation)

**Approved scope executed:** REQ-H1 per-field OAuth merge · REQ-H2 fail-closed
Host gate · REQ-H3 execute timeout (wait_for/to_thread, clamp [0.1,30]s) ·
REQ-CE-001 toolbar floors — then Round-2: CE-001 wrapper→flex container,
CE-007 docstring truth, QA F-01 local-branch PUT tests (T-F01-1/2), QA F-07
exact-set host test. Suite **621 passed** (orchestrator independently ×2,
reviewers ×3 more), coverage **82.79%**, ruff check+format clean,
fails-before/mutation proofs: /tmp/opencode/{h1,h2,h3,ce,r2_*}_{before,after}.txt.

**Evidence highlights:** evil Host → 403 on all 24 admin surfaces (original
proof was 200) — rebinding exfil chain proven DEAD (25 hostile Host probes,
CSRF token in zero non-admin bodies, /mcp read-only) · scope-only OAuth PUT
byte-identical clientId+clientSecret (sha256-verified, 30/30 data checks) ·
button Δ=0 at 375/390/414/600 (both refuter and orchestrator independently) ·
timeout contract docstring now matches measured behavior.

| Domain          | Reviewer            | First verdict | Re-gate verdict | Fixed | Key residuals                          |
| --------------- | ------------------- | ------------- | --------------- | ----- | -------------------------------------- |
| engineering     | review-readability  | conditional   | **pass**        | 1     | deferrals documented (RD Mediums/Lows) |
| engineering     | review-reliability  | closed        | conditional     | 1+1 partial | RL-003..006, OBS-1 (uuid4)        |
| engineering     | review-resilience   | conditional   | conditional     | 0     | F-7 (High, core GIL), F-1..F-3         |
| engineering     | review-risk         | conditional   | conditional     | 0     | RK-001, RK-004 (waiver-by-design), RK-008 |
| engineering     | review-refuter      | conditional   | conditional     | 3/3 Highs + CE-007 retracted | CE-006 (uuid4), CE-001/009 Low |
| engineering     | quality-assurance   | conditional   | **pass**        | 2     | F-02/03/05/06 = backlog Lows            |
| data            | review-data         | conditional   | conditional     | 1     | DAT-002/003/004, DAT-008 (uuid4)        |
| security        | security-reviewer   | closed        | conditional     | 2     | SEC-003 (CDN waiver candidate), 3 Low   |

**Re-gate verdict: CONDITIONAL** (0 CLOSED) → **C3 invoked same day: all 13
condition-waivers PASS three-block bar → GATE OPEN.** New High F-7
(core sandbox GIL bound) waived under W-01 with compensating controls:
loopback+CSRF-only trigger, honest docstring, core-backlog ticket, expiry
2026-12-22/core release.

**Round-2 reviewer closures:** QA pass (F-01, F-07 closed) · refuter CE-007
retracted, CE-001 Medium→Low.

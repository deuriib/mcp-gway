# CHANGELOG
## [4.6.0] — 2026-10-10

- **feat(pi)**: native gateway registration — `.pi/extensions/mcp-gateway.ts` now calls `pi.registerMcpServer("gateway", { command: "uvx", args: ["mcp-gway", "serve"] })` inside `try/catch` (name clash with another extension degrades to a stderr warning, tools keep working). `.mcp.json` is deleted and dropped from the `files` whitelist in `package.json`; a same-named server in a user's project `mcp.json` still takes precedence.
- **feat(pi)**: `gw_add` / `gw_remove` model-callable tools wrapping top-level `mcp-gway add` / `mcp-gway remove` via a new `runRoot` helper (same never-throws `{ ok, text }` contract and `MAX_OUTPUT_CHARS` truncation as `runTools`). `runAdd` builds the exact CLI argv (`--command` for local, `--url` for remote, repeatable `--env`/`--header`, `--cwd`, `--no-enabled`, `--timeout`) and validates before shelling: local without `command` or remote without `url` returns a usage error with zero subprocess spawns. Deliberately no OAuth flags — `add` falls back to an interactive OAuth flow that cannot complete headless, so OAuth servers are added from a real terminal.
- **feat(pi)**: `uv` guard at `session_start` — the handler probes `uvx --version` (5 s timeout) before the inventory call; on missing `uv` it warns always and notifies (UI only) with the install URL plus reload instruction, then returns early skipping inventory. Tool `execute` paths keep returning today's `mcp-gway is not available` error text.
- **tests(pi)**: `tests/pi_extension.test.mjs` grows from 27 to 34 checks — `registerMcpServer`/`unregisterMcpServer` stubs on `makePi`, native registration args assertion, meta-tool count bumped to 6, `gw_add` local/remote argv (raw name passed through; PascalCase normalization stays server-side in the CLI), both usage-error cases with zero exec calls, `gw_remove` argv, `uvx --version` probe ordering in the inventory test, and the uv-missing notify test (install URL asserted, no inventory message). Verified `ALL GREEN`.
- **docs(pi)**: `plugins/pi/INSTALL.md` Configuration paragraph rewritten (no `.mcp.json` shipped, native registration shape, `uv` prerequisite with reload path), meta-tools and session-inventory bullets updated, host-map row corrected; stale `.mcp.json` contract note in `tests/AGENTS.md` updated.
- **chore(omp)**: `.gitignore` now ignores `.omp/plugins/` (oh-my-pi local plugin installs).
## [4.5.7] — 2026-10-06

- **docs(readme)**: restructure the front door — README.md drops from 389 lines to 75 (badges, tagline, Why/Who, corrected Quick Start, features, documentation index, dev pointer, license) and the depth moves to eight focused guides under `docs/` (configuration, cli, code-mode, security, observability, integrations, architecture, development). The three section badges now target files instead of GitHub slugs (0 in-page anchors left) and all 20 local links were verified to resolve. Also removes the duplicate `## Quick Start` heading and the invented `mcp-gway add --name files --local` syntax — replaced with the real signature `mcp-gway add files --type local --command`.
- **docs(facts)**: fix stale references while moving sections — `Options for add` is 14 options at `cli.py:97-136` (was "13 flags" at `cli.py:45-95`; the `--retry-on-transport-error` row was missing from the table), `cli.py:50` → `cli.py:97-102`, `/health` sample `"version":"3.1.0"` → `4.5.6`, test count `570` → `647` (verified for this release: 645 passed + 2 skipped), SSRF ref `models.py:115-163` → `models.py:301-540`, both dead `MIGRATION.md` links → `CHANGELOG.md`, dead `docs/architecture/adr-009-dynamic-local-commands.md` link and stale `rm ~/.config/mcp-gway/catalog.json` hint dropped (neither exists), ASCII-art `reutilizado` → `reused`.

## [4.5.6] — 2026-10-06

- **ci(npm)**: publish to npm via OIDC trusted publishing — the release pipeline now publishes `mcp-gway` to npm alongside PyPI, authenticated by short-lived OIDC instead of a long-lived registry token. `id-token: write` was already declared, and both publishes are now secretless (no `secrets.*`, no `NODE_AUTH_TOKEN` anywhere in the workflows). Node pinned to `24.21.0` exactly because npm trusted publishing requires npm >= 11.5.1 and Node 22 only ships npm 10.9.9 — the previous `node-version: "22"` could never have published. Adds `repository`/`homepage`/`bugs` metadata that npm renders on the package page. The first publish (`mcp-gway@4.5.5`) was a manual bootstrap, since npm requires a package to exist before a trusted publisher can be configured.
- **ci(hardening)**: pin every action and runner to an exact version — `test.yml` was using floating major tags (`checkout@v4`, `setup-python@v5`, `setup-uv@v6`), now the exact versions already proven in `release.yml` (`v4.2.2`/`v5.6.0`/`v6.8.0`); `runs-on: ubuntu-latest` → `ubuntu-24.04` in both workflows, because `latest` is a moving alias rather than a reproducible reference.
- **ci(pr-only)**: tests run on `pull_request` only, the `push` trigger is gone (CI is the PR gate, so the master push run was redundant — verified: 0 Tests runs on the merge commit vs 3 before). `release.yml` cannot be PR-triggered because a tag is not a PR, so it gains a `Verify tag points at merged code` guard requiring the tagged commit to be an ancestor of `master` — releases can only come from merged PR code, never a stray branch tag. The guard runs immediately after checkout, before any build or publish step.
- **docs(workflow)**: correct the documented release command — `git push --follow-tags` only pushes ANNOTATED tags and this repo tags lightweight, so it silently failed to push `v4.5.5` and no release ran despite `exit 0`.

## [4.5.5] — 2026-10-06

- **chore(packaging)**: add `files` whitelist to `package.json` — npm was shipping the whole git-tracked tree (2,058,620 B unpacked: `.github/workflows/`, `.omp/`, `docs/`, `tests/`, `AGENTS.md`, `DESIGN.md`, `.pre-commit-config.yaml`). The whitelist holds the five runtime contracts only: `.mcp.json` (Pi gateway discovery), `plugins/opencode/mcp-gateway.ts` (`main`/`exports`), `.pi/extensions/` (`pi.extensions`), `skills/` (`pi.skills` — four cross-referencing SKILL.md files) and `rules/mcp-gway.md`, which `.pi/extensions/mcp-gateway.ts` reads at runtime and would otherwise have degraded silently to the embedded fallback card. Evidence: `npm pack --dry-run` 605 KB → 25 KB packed, 2,058,620 → 81,278 B unpacked, 11 files (`package.json`, `README.md`, `LICENSE` are always included by npm regardless).

## [4.5.4] — 2026-10-06

- **chore(pypi)**: declare license expression + Python classifiers — PyPI metadata shipped empty (`classifiers: []`, no `license`), so the README's dynamic Python and License badges rendered red `missing`. `license = "MIT"` + `license-files` now emit `License-Expression: MIT` / `License-File: LICENSE` in wheel METADATA (the LICENSE file ships inside the dist), and 3.12/3.13 classifiers match the CI matrix so both badges derive real data. Evidence: `uv build` clean (deprecated license classifier dropped — PEP 639 warning gone), `uv lock --check` clean, ruff probe confirms shields reads `license_expression`.

## [4.5.3] — 2026-10-06

- **docs(readme)**: product-focused badge set — CI/Release status, Ruff code style, PyPI downloads, MCP Protocol, Code Mode, Local-First Security, Observability Built-in. Anchor links to corresponding sections. 11 badges total, 2-row visual layout. No code/logic change.
- **chore(omp)**: add .omp/ directory with README badges plan artifact.
## [4.5.2] — 2026-10-06

- **fix(pi-ext)**: card injection fallback for omp — `oh-my-pi` 18.6.1 emits `before_agent_start` without `systemPromptOptions`, so the section write threw and the UI warned `Gateway Protocol card not injected`. The handler now returns a `systemPrompt` override (card appended, deduped by marker) when sections are absent; the Pi section path is unchanged. Regression test in `tests/pi_extension.test.mjs` + troubleshooting row in `plugins/pi/INSTALL.md`.
## [4.5.1] — 2026-10-06

- **docs(scrub)**: remove retired product names from live surfaces — README, AGENTS, PRODUCT, all four skill files, source docstrings/comments, one served `listToolFiles` description, and test names reworded. Wording-only: no logic, packaging, plugin, or history change. Zero live mentions remain; scoped sweep + 645 tests + ruff clean.
- **docs(context)**: hierarchical `AGENTS.md` via init-deep — root refresh (178 → 87 lines) with evidence-backed domain table and commands copied from `mise.toml`; new domain-scoped files for `src/mcp_gway/core`, `src/mcp_gway/observability`, `src/mcp_gway/admin`, `tests`.

## [4.5.0] — 2026-10-06

- **feat(pi)**: gateway over stdio — `.mcp.json` declares `gateway` as `uvx mcp-gway serve` (loopback by construction, no TCP surface, no port, no token). Extension drops programmatic registration; Pi discovers the server declaratively. Extension surface: Gateway Protocol card injection (`rules/mcp-gway.md` at runtime, deduped by marker), 4 meta-tools (`gw_list`, `gw_read`, `gw_docs`, `gw_exec` via `pi.registerTool` shelling out to `mcp-gway tools`), hidden `session_start` server inventory. 27 checks in `tests/pi_extension.test.mjs` incl. `.mcp.json` contract test.
- **feat(pi)**: Pi packages upgraded to 1.0.4 (`@earendil-works/pi-coding-agent`, `pi-ai`) — `ExtensionContext` typing on the `before_agent_start` handler, no implicit/explicit `any`.
- **fix(antigravity)**: `mcp_config.json` moves to stdio (`command: uvx`, `args: [mcp-gway, serve]`); `test_mcp_config_loopback_and_no_secrets` asserts the stdio shape.

- **feat(tracing)**: stdlib-only distributed tracing completes logs → metrics → traces. New `observability/tracing.py` (`Tracer` + `Span`, contextvars propagation, W3C `traceparent` in/out, 256-span ring buffer, zero deps). `TracingMiddleware` wraps every HTTP request as a `server` span (`METHOD /route`, status + error capture, `traceparent` response header). Every upstream tool call gets a nested `client` span (`tool server.name`, `mcp.server/tool/status`, retry flag); `sandbox.execute` gets its own span. `JSONFormatter` now always emits `trace_id` + `span_id` for log correlation. New `GET /admin/partials/traces?limit=50` (loopback-gated) exposes the recent span tail; observability page links it. 7 new tests in `test_observability_tracing.py`.
## [4.3.1] — 2026-10-05

- **fix(gateway)**: silence benign Windows accept noise + harden global error handlers. `install_asyncio_exception_handler()` downgrades transient client-abort accept errors (WinError 64/121/995/1236, `ConnectionResetError`, "Accept failed on a socket") to debug — wired via `new_event_loop` patch in `serve` (uvicorn owns the loop), `Gateway.__init__`, and lifespan. New `_ClientDisconnectMiddleware` answers mid-request hangups with a quiet 204; `Exception`/`HTTPException` handlers guarantee JSON 500s (secret-safe via `_safe_error_data`, never HTML tracebacks); `LoggingMiddleware` logs disconnects at debug, real failures with context. 3 new regression tests in `test_edgecases_gateway.py`.

## [4.3.0] — 2026-10-05

- **feat(models)**: native pydantic validation errors with human-friendly messages. Validators raise `PydanticCustomError` with a distinct `type=` per failure and the `[reason=...]` token preserved in `msg` + structured `ctx.reason`; `format_validation_error` renders one `field: sentence` line per error. CLI `add` remote branch wrapped in try/except (exit 1, no traceback) and admin add/save surfaces share the helper. `https-only` now enforced at config validation; SSRF bypass fixtures moved to `https://` URLs.

## [4.2.0] — 2026-10-04

- **docs(skills)**: product-first rewrite of all four skills with per-command variants and live examples. `skills/cli` → `skills/mcp-gway-cli` (via `git mv`, history preserved): every command gets its own section — `add` documents all 12 flags with remote/local/OAuth variants, `tools exec` shows three variants (`--code` inline, `--file` script, `refresh && read && exec` chain). `skills/mcp` → `skills/mcp-gway-mcp`: transport picker table, four `serve` variants, three agent-wiring variants (OpenCode stdio, Claude HTTP, Pi `.mcp.json`), 4-step protocol with real Context7/ParallelSearch output, Starlark DO/DON'T cookbook. `skills/core` → `skills/mcp-gway-core`: config-files table (`servers/*.json|pyi`, `tokens/`), complete six-var `MCP_GWAY_*` table, three policy gates with allow/deny examples, execution stack, OAuth, observability series, admin-backend route table. `skills/mcp-gway` becomes a routing table (task → skill → coverage). All frontmatter bumped to v4.2.0; `plugins/pi/INSTALL.md` naming aligned; `README.md` LICENSE link corrected to `LICENSE`.

## [4.1.0] — 2026-10-04

- **feat(admin)**: toast lifecycle, form reset, actionable errors. Success toasts (green/blue/white) auto-dismiss after ~4s via htmx `load delay:4s` self-swap to `/admin/partials/empty` (no inline script, strict CSP holds); red/orange persist with a close control. Add-server and Code Mode execute forms OOB-swap a fresh copy on success and keep user input on error. Every error keeps its searchable head and appends the next action (`test_admin_dashboard.py` 54 tests).

## [4.0.0] — 2026-10-04

- **feat(cli)!**: BREAKING — full break-glass kill. `mcp-gway local-unrestricted [enable|disable|status]` is gone (`No such command`); the marker engine is deleted from `core/policy.py` (`UNRESTRICTED_ENV`, `MARKER_NAME`, `UnrestrictedStatus`, `create/remove/unrestricted_status/is_unrestricted_active`, `marker_path`), and the admin `GET/POST/DELETE /admin/partials/policy/unrestricted` routes plus panel are removed. Local commands are gated by the explicit allow-list only (`MCP_GWAY_ALLOW_LOCAL_COMMANDS`, unset/blank → `npx,bunx,uvx,pipx`) — no bypass exists. Deny messages now point at the allow-list instead of `local-unrestricted enable`.
- **feat(cli)**: `mcp-gway --version` / `-v` prints `mcp-gway <version>` via root-group `click.version_option` (`mgw` inherits it).
- **docs(product)**: outcome-first positioning — README opens with one-endpoint/on-demand-schemas, adds Why/Who sections, drops the unverified 92% token claim, EN-only, diagram at v4.0.0. `pyproject`/`package.json`/`plugin.json` one-liners aligned; skill frontmatter at v4.0.0; `PRODUCT.md` gateway-first with the corrected parity list.

## [3.2.0] — 2026-10-04

- **feat(pi)**: soporte del harness Pi (tercero tras OpenCode y Antigravity) — el repo queda cargable como Pi package (`package.json` declara `pi.{extensions,skills}`) y `.pi/extensions/mcp-gateway.ts` inyecta la Gateway Protocol card en `systemPromptOptions.sections` en cada `before_agent_start`, dedupeado por marker, leyendo el texto de `rules/mcp-gway.md` en runtime (fuente única compartida con Antigravity, sin copias que divergan). El registro MCP es **declarativo** vía `.mcp.json` en la raíz, autodescubierto por pi-mcp-adapter — no runtime `registerMcpServer()`, que fuerza `directTools: false` y lanza en nombres duplicados. La extensión es fail-soft: lee un archivo local acotado, no abre socket, no spawnea nada y traga sus propios errores, así no puede abortar un turno. Nueva guía `plugins/pi/INSTALL.md`.
- **fix(manifest)**: `package.json` era JSON inválido — el bloque `pi` en el working copy tenía `"./.pi/prompts/"` como propiedad suelta fuera del array `prompts`, lo que invalidaba el JSON y rompía la carga del paquete. La clave `pi` se añade declarando solo los paths que existen (`extensions`, `skills`).
- **fix(antigravity)**: el hook `PreInvocation` estaba roto y nunca ejecutó — `hooks.json` invocaba `sh /plugins/antigravity/scripts/reinject.sh`, una ruta POSIX absoluta que no existe en Windows ni resuelve al repo. Reescrito como `plugins/antigravity/scripts/reinject.mjs` (Node ESM; sin shell, sin `eval`, sin red, sin escrituras, degrada a no-op) e invocado como `node ./plugins/antigravity/scripts/reinject.mjs`. El `.sh` se elimina.
- **chore(antigravity)**: `plugin.json` sincronizado a `3.1.0` con `package.json` (was `2.8.0`); marker de `rules/mcp-gway.md` y contratos de hook marcados a `MCP-GWAY v3.1.0`; `INSTALL.md` sin el `chmod +x` de un script que ya no existe.

## [v3.1.0] — 2026-09-23

- **feat(admin)**: complete admin web dashboard (htpy 26.5.1 + htmx 2.0.10 + Tailwind, ambos CDN, estética Spotify de `DESIGN.md`) — revierte el "CLI-only, no UI" de v2.0.0 solo para gestión; CLI sigue canónico y `/dashboard`+catalog permanecen retirados. Nuevo paquete `src/mcp_gway/admin/` (theme/components/icons SVG authored/layout/data/routes + pages de status, overview, servers, tools, observability, policy) spliced en `Gateway` para ambos transports: páginas `/` (índice), `/admin` (alias), `/admin/servers[/{name}]`, `/admin/tools` (explorador Code Mode: list/read/docs/execute con `asyncio.to_thread` en el sandbox), `/admin/observability`, `/admin/policy` + 17 endpoints `/admin/partials/*` (status cada 5s, grid/CRUD/refresh/auth de servers, config edit `PUT .../{name}/config`, tools read-only `GET .../{name}/tools`, break-glass enable/disable, metrics). Paridad con CLI (add/remove/list/inspect/refresh/local-unrestricted) — `update` (tools) permanece solo CLI: la web NO muta tools (solo add/refresh); edición de config en web con secretos write-only (blank = conserva valor). Seguridad: admin loopback-only (`_gate` → 403 si `serve_host` no es loopback), CSRF por proceso (`app.state.csrf_token`, header `X-CSRF-Token` o campo `_csrf`) en toda mutación, CSP único relajado en constante `CSP` de `gateway.py` (script-src jsDelivr+Tailwind, style-src `unsafe-inline`, `frame-ancestors 'none'`; test `<=2` literales intacto), OAuth nunca inline (task en background con paridad `refresh --auth`), headers/OAuth enmascarados en detalle, allow-list de comandos locales aplicada vía `check_local_command` + audit en add/refresh, `path_template` colapsa `/admin/*` (cardinalidad acotada). Host header fail-closed en `_gate` (solo `{127.0.0.1, localhost, ::1, [::1]}` → evil Host 403 en las 24 rutas admin, anti-DNS-rebinding), execute con timeout real clamp [0.1,30]s default 10 (toast/notice `exec-timeout`), merge OAuth per-field (blank conserva, sentinela de máscara = blank). Serve banner añade línea `Dashboard → http://host:port/`. Evidence: `tests/test_admin_dashboard.py` (50 tests) + 3 asserts CSP migrados a la constante `CSP`.
- **perf(tests)**: optimize test suite execution and eliminate SSE disconnect hang (SPEC-TEST-PERF-001). Monkeypatched `MAX_IDLE_SECONDS` to 0.05s in `test_ac005_sse_disconnect_counted` to remove a 300-second ASGI idle wait. Bounded mock thread sleeps in sandbox timeout tests (`test_sandbox.py`, `test_edgecases_sandbox.py`) from 10s to 0.8s/0.5s to prevent `ThreadPoolExecutor` shutdown lag. Fixed DNS timeout monkeypatch target to `SSRF_DNS_TIMEOUT` in `test_p0_round2_hardening.py`. Total test suite execution time reduced from >340s to ~8.9s across all 562 tests (100% pass rate, zero production code changes).
- **feat(casing)**: universal casing ingestion, auto-migration on refresh, and canonical PascalCase exposure (SPEC-CASING-001, ADR-013). Upgraded `to_pascal_case_identifier` to cleanly parse `camelCase`, `ALL_CAPS` acronyms (`GITHUB` → `Github`, `WEATHER_SERVICE` → `WeatherService`), delimiters, and numbers. Implemented case-insensitive server lookup across `remove`, `inspect`, `update`, and `refresh`. `mcp-gway refresh` automatically migrates legacy and non-canonical servers to canonical PascalCase files and tokens.

## v3.0.0 (2026-09-22)

- **feat(transport)!**: BREAKING — `/mcp` routes are now per-transport with no cross-fallback (SPEC-TRANSPORT-SEPARATION-001, gate OPEN 2026-09-22, 7 reviews). One process no longer serves both transports: `serve --transport http` exposes only `POST /mcp` (`GET /mcp` → `405 Allow: POST`; `/mcp/messages` → 404, 6 routes) and `serve --transport sse` only `GET /mcp` + `POST /mcp/messages` (`POST /mcp` → `405 Allow: GET`, 7 routes). Probes (`/health`, `/ready`, `/live`, `/metrics`) remain on both; `app.state.transport` exposed; `Gateway(transport=...)` rejects unknown values. **Migration:** SSE-only clients must use `--transport sse` (see `plugins/antigravity/INSTALL.md` troubleshooting); streamable-HTTP (POST) clients are unaffected. Strict semver: `feat!` → major (3.0.0). Evidence: `tests/test_transport_separation.py` 9/9 + suite 570 passed; amends ADR-010 AC-05 inline (`AGENTS.md`, `API_CONTRACTS.md`).

## v2.5.0 (2026-09-17)

- **feat(cli)**: expose `mgw` as a 1:1 shortcut for `mcp-gway` (verified 2026-09-17, same `cli.main`, SPEC-MGW-001); `mcp-gway` stays canonical, both shims ship on install (`pyproject.toml:20-21`). Evidence: `tests/test_cli_alias.py` 3/3 green + README/AGENTS.md shortcut callouts.
- **fix(ready)**: event-loop drift threshold 3s → 35s (30s heartbeat + 5s buffer, SPEC-READY-001) — `/ready` returned 503 false-positive; now 200 when healthy, p99=16ms. Change: `src/mcp_gway/observability/health.py:88`.
- **docs(perf)**: internal-only performance audit tooling (verified 2026-09-17, SPEC-PERF-001, engineering). Benchmark script (`bench_perf.py`), runbook (`RUNBOOK-perf.md`), findings baseline v2.4.0 (`PERF-FINDINGS-v2.4.0.md` + `reports/baseline_20260917_*.json`, all 5 SLO hypotheses PASS), architecture NFRs (`ARCHITECTURE.md`), ADR-011. No user-facing impact, no src/ changes.
- **docs(release)**: reconcile v2.4.0 tag collision — remote annotated tag stays the 2026-09-16 automation (`0cdcfe8`); local lightweight tag (`6601767`) deleted locally, never pushed; `RELEASE_NOTES.md` rollback corrected (never `tag -d`/push-delete a published tag; published recovery is `git revert` + PyPI yank via devops + vasquez).
- **docs(verify)**: FEAT-007 verification evidence 2026-09-17 — `tests/test_obsfeat007.py` 11/11 core ACs green (AC-001/003/004/008/009/013/014/015/016/017/018), `ruff check` + `format --check` clean; `--retry-on-transport-error` evidence `test_ac014/015/016` green (`server_factory.py:101-148`, `models.py:720`, `cli.py:107-112`).

### Residual risks (accepted, owners tracked)

- AC-004 (`discovery_duration_seconds`) dead code — no production caller passes `metrics=`. Owner: vasquez.
- Raw error messages in CLI/CodeMode logs (M-01..M-04) — hygiene, not network-facing. Owner: vasquez.
- Code mode refresh dead code (reliability F-1) — informational overlap, harmless. Owner: vasquez.

## v2.4.0 (2026-09-16)

- **note**: published automation tag (remote annotated `07b3b05…` → `0cdcfe8`, semantic-release 2026-09-16). Post-v2.4.0 delta (09-16/17: `mgw` feat, `/ready` fix, perf docs) rides `## Unreleased` above and ships with the next version — it is NOT part of this v2.4.0 entry.
- **cleanup**: remove legacy env-based log-level inference — `_resolve_log_level` now reads only `MCP_GWAY_LOG_LEVEL` (`--log-level` overrides; default `info`). Dropped `MCP_GWAY_ENV`, `ENV`, `ENVIRONMENT`, `APP_ENV`, `DEBUG`, `LOG_LEVEL` fallbacks and the serve banner `env <hint>` echo. Purged inert `MCP_GWAY_ALLOW_LOCAL_VIA_DASHBOARD` from docs (code already removed in v2.0.0; AGENTS.md/README.md updated).
- **feat(cli)**: unified `serve --transport [stdio|http|sse]` (default `stdio`); `--registry-dir` is now a common `serve` option; `--host/--port` only apply to `http|sse` (with `stdio` → `Error: --host/--port only apply to --transport http|sse` + exit 2, never warn-and-ignore).
- **deprecation**: `mcp-gway mcp` is now a hidden alias (`hidden=True`): `serve --transport stdio` equiv `mcp` — mismo loop NDJSON y mismos args a `_serve_stdio()`, modulo aviso de deprecacion `[mcp] deprecated, use serve --transport stdio` en stderr (solo `mcp`, sin logica propia). Use `command: [mcp-gway, serve, --transport, stdio]` for OpenCode `type: local`.
- **compat**: local-first intact (`127.0.0.1` default, non-loopback without `MCP_GWAY_ALLOW_REMOTE=1` → exit 2 legacy text); `http`/`sse` share the same `Gateway.app`; stdio keeps stdout pure NDJSON (banners `err=True`).
- **feat(observability)**: FEAT-007 hardening — process/build lifecycle metrics (`build_info`, `process_start_time_seconds`, `uptime_seconds` via 30s heartbeat, `lifetime_seconds` set at shutdown + JSON `gateway shutdown summary`); SSE disconnects counted by reason (`gateway_sse_disconnects_total`); stdio per-request metrics + JSON access log (`transport:"stdio"`); `discovery_duration_seconds{server,status}` revived via injected registry; upstream CodeMode telemetry (`upstream_tool_calls_total{server,tool,status}` with `timeout` classification, `upstream_tool_duration_seconds`, `upstream_retries_total`); `code_mode_servers_skipped_total{reason}` + WARN + degraded serve banner when server injection fails; label-cardinality cap (`_MAX_LABEL_COMBOS=200`, overflow coalesces to `_other`); slow-request WARN (threshold 1000ms); CLI structured events (WARNING always, INFO gated by `MCP_GWAY_LOG_LEVEL`). No prod deps added — stdlib + vendored registry only.
- **feat(cli)**: opt-in `--retry-on-transport-error` for `mcp-gway add` — retries exactly once only when the transport/connect+initialize phase fails, never after `session.call_tool` starts (non-idempotency-safe, ADR-012 decision 9). Default off → zero behavior change for existing configs.

## v2.2.0 (2026-09-11)

- **feat**: add `AI` directory to `.gitignore` so local Claude skills are never committed (`a559bbc`). Version bump only — no runtime changes.

## v2.1.2 (2026-09-11)

- **fix(policy)**: harden break-glass marker create/remove/status with explicit CLI (`mcp-gway local-unrestricted enable|disable|status`) — marker ops distinguish missing vs failure and fail closed (`416ef38`).

## v2.1.1 (2026-09-11)

- **fix(mcp)**: typed JSON-RPC errors `-32602` (invalid params) / `-32603` (internal) with `data` carrying safe `[reason=...]` tokens; `.pyi` stub sanitization; parameter validation on tool calls (`dd8e52b`).

## v2.1.0 (2026-09-11)

- **feat(mcp)**: stdio local mode — `mcp-gway mcp` serves NDJSON JSON-RPC over stdin/stdout (usable as an OpenCode `type: local` server via `command: [mcp-gway, mcp]`), with hardened client-side transport (`filtered_stdio_client`) that drops non-JSON noise from child servers (`cec3277`).

## v2.0.1 (2026-09-10)

- **fix(policy)**: expand environment denylist — exact `PATH, PATHEXT, SYSTEMROOT, COMSPEC, LD_PRELOAD, LD_LIBRARY_PATH, PYTHONPATH, PYTHONHOME, NODE_OPTIONS, NODE_PATH, NODE_EXTRA_CA_CERTS, NODE_TLS_REJECT_UNAUTHORIZED` + prefixes `DYLD_, NPM_CONFIG_, BUN_, UV_` (`e9d4d5f`).
- **docs**: allow-list wording sync — exact denylist and `bunx` opt-in CISO note (pin + owner + regate 90d; runtime stays out) (`2b26b3d`, `218148f`).
- **docs(release)**: sync ADR-007 to `python-semantic-release` v10 (`ce89db7`).
- **tests**: drop legacy monkeypatch paths in transport tests (`814c0db`).

## v2.0.0 (2026-09-10)

- **breaking**: removed dashboard (`/dashboard`, `/api/servers`, `/static`, `/` alias) and catalog (`/api/catalog`, `/dashboard/catalog`, Bifrost fetch, `~/.config/mcp-gway/catalog.json` cache). Gateway serves `/mcp`, `/health`, `/ready`, `/live`, `/metrics` only; management is CLI-only. Dropped `htpy` dependency (`httpx` kept). Delete stale cache manually: `rm ~/.config/mcp-gway/catalog.json`.

- **feat-006**: Dynamic-no-static local allow-list + 72h break-glass ([ADR-009](docs/architecture/adr-009-dynamic-local-commands.md))
  - Default-deny: empty `MCP_GWAY_ALLOW_LOCAL_COMMANDS` denies all `local`; CSV basenames, `*` invalid.
  - Operative CISO values: default-deny BR-002..BR-016 (single syntax rule, allow-list, 72h TTL, VIA+loopback gate, `which`-only spawn, `cwd`/env gates, audit `***`), break-glass `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL=1` + marker `~/.config/mcp-gway/.local_unrestricted` (epoch, `0o600`, 72h TTL).
  - Closes PATCH `from_edit` bypass; re-gates POST/PATCH/refresh/catalog + CLI `add`/`refresh`; Dashboard `ALLOW = VIA=1 AND (unrestricted OR in allow-list) AND serve-host loopback`.
  - Env vars (do not rename): `MCP_GWAY_ALLOW_LOCAL_COMMANDS`, `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL`, `MCP_GWAY_ALLOW_LOCAL_VIA_DASHBOARD`.

### Migration

- Endpoints servidos solo `/mcp`, `/health`, `/ready`, `/live`, `/metrics`; gestión CLI-only.
- Delete stale cache: `rm ~/.config/mcp-gway/catalog.json`.
- Vars: `MCP_GWAY_ALLOW_LOCAL_COMMANDS` / `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL` / `MCP_GWAY_ALLOW_LOCAL_VIA_DASHBOARD`.

## v0.9.1 (2026-08-25)

### Bug Fixes

- **dashboard**: Filter, type toggle, hover, pill centering, tooltips and spacing
  ([`bca81a6`](https://github.com/deuriib/mcp-gateway/commit/bca81a608b63c6c482d0f87edb4cc76cc55f1ed8))

- Extract inline script to vendored dashboard.js to fix CSP blocking (filter by name and
  remote/local toggle now work, re-hydrates on htmx:load) - Fix table row buttons blocked by capture
  stopPropagation in dialog.js (remove capture listener) - Fix search icon alignment (inset-y-0 flex
  centering vs translate) - Fix stats cards too close to header (pt-8 gap-8) - Fix healthy pill
  centering and size (justify-center gap-1 px-2 leading-none) - Fix row hover missing
  (hover:bg-slate-50 vs purged /80) - Add native tooltips via title on
  View/Toggle/Delete/Refresh/Reveal/Copy/Close for accessibility

## v0.9.0 (2026-08-25)

### Chores

- **lock**: Sync uv.lock to 0.8.0
  ([`9aaef3f`](https://github.com/deuriib/mcp-gateway/commit/9aaef3fbd2643edbfb6bf3b9678d7fe8f301ef8b))

Match pyproject.toml and src/mcp_gway/**init**.py after 0.8.0 semantic release; previous lock at
0.7.1 causing inconsistent build metadata.

### Features

- **dashboard**: Expose dashboard at root path
  ([`7686d48`](https://github.com/deuriib/mcp-gateway/commit/7686d4855c165474047147ce3452f45fcaca181e))

Serve the same SSR dashboard on both root and dashboard via handle_dashboard alias. Keeps
local-first gating, CSP and X-Warning behaviour identical so index path fulfils product
requirement that root must load the dashboard, not 404. Single handler reuse avoids duplication
and preserves bounded-context purity.

## v0.8.0 (2026-08-25)

### Features

- **dashboard**: Swiss minimal redesign with micro-interactions for lazy-person UX
  ([`333180b`](https://github.com/deuriib/mcp-gateway/commit/333180b8da6c451d87a6d99cc5919a5b07d6bee7))

Redesign dashboard under ui-ux-pro-max minimalism-and-swiss-style: header glass + stats grid, row
stagger 28ms with reduced-motion, badges with dot/status, filter, progressive disclosure form,
drawer and empty state polish. Vendored Tailwind expanded to 14KB covering new utilities while
staying local-first and <100KB. 188 tests pass, ruff clean.

## v0.7.2 (2026-08-25)

### Bug Fixes

- **dashboard**: Harden dialog resilience and clean architecture
  ([`70c64df`](https://github.com/deuriib/mcp-gateway/commit/70c64df6cffe8b599d180fbafae52097d2efbef8))

Resilience C1: dialog.js now handles htmx:responseError/sendError/ timeout/swapError with
handleDialogError -> toast + fallback aside panel inside dialog, reuses server error HTML and
htmx.process. Set htmx.config.timeout=7000 so offline/slow doesn't hang.

Resilience I1: hx-indicator #global-spinner on tr and View button, global timeout, indicator wiring.

Readability/Reliability: extract _DIALOG_ID/_DIALOG_TARGET/_CLOSE_ATTRS, _BASE_BADGE/_BADGE_COLORS,
split server_drawer 210 lines into _drawer_header/_drawer_metadata/_drawer_actions/_tool_panel,
fix nested role dialog -> region inside native dialog, delegate stopPropagation via single
document click listener (survives #server-table-body swaps), dedup openDialog/clearDialog helpers,
isEmpty robust via childElementCount, documented delays.

Tests: add 7 hardening tests for dialog contract (layout has dialog no drawer, row targets dialog +
indicator, drawer returns aside region, dialog.js resilient tokens, detail panel, close clears, no
inline onclick) -> 188 passed, ruff clean.

- **dashboard**: Migrate drawer to native dialog with vendored style
  ([`129654b`](https://github.com/deuriib/mcp-gateway/commit/129654be5fc196da06dde0f694f3f8f39483e2ac))

Drawer inline was rendered at page bottom (screenshot shandcn below footer, truncated) instead of
overlay â€” broke UX and a11y. Replace div#drawer fixed overlay with native <dialog
  id=server-dialog> using existing Tailwind vendored style (backdrop blur, shadow-xl, border-l).

- views.py: hx-target #drawer -> #server-dialog, remove inline onclick stopPropagation (CSP
  default-src 'self'), drawer_error/ server_drawer now return aside only, layout hosts <dialog> +
  script /static/dialog.js external - static/dialog.js: showModal/close, backdrop click, ESC cancel,
  htmx:afterSwap/afterSettle open/close, delegated stopPropagation for row buttons without inline
  handlers - static/tailwind.css: vendor missing utilities for dialog (m-0 p-0 max-w-none w-screen
  h-screen backdrop:* open:flex etc) <7.6KB, htmx 2.3KB, dialog 2.8KB, no Node

Verified 181/181 pytest, ruff ok, layout contains <dialog> and no id=drawer, /static/dialog.js
served with showModal.

## v0.7.1 (2026-08-25)

### Chores

- **release**: Expand semantic-release triggers to automate patch releases
  ([`abf3beb`](https://github.com/deuriib/mcp-gateway/commit/abf3beb218b7250c041e4e9186ff3c6c8a8ec35b))

Expand patch_tags from [fix, perf] to include refactor, docs, build, chore, style, test, ci, revert
so workflow_run Tests + python-semantic-release triggers automated patch on any conventional
commit. Add revert to allowed_tags for completeness. Keeps minor_tags=[feat] and BREAKING
CHANGE->major intact to preserve semver; hybrid workflow push v* + workflow_run Tests +
concurrency:release prevents duplicate versions. No Node, pure ruff/uv.

### Documentation

- **dashboard**: Sync v0.7.0 GA specs and polish dashboard bottom UI
  ([`23c6f8b`](https://github.com/deuriib/mcp-gateway/commit/23c6f8b017dcf701d48814b9ddc851a3e5b615c9))

Sync AGENTS.md, README.md and SPEC-UI-001 with shipped v0.7.0 GA so docs match code and close the
SBTDD verification gate (Registry single source, htpy+htmx bounded context, local-first 127.0.0.1,
masking ***).

Polish src/mcp_gway/dashboard/views.py bottom area: sticky table header, action group
(View/Toggle/Delete) with hx-* handlers, footer, drawer/header and spacing refinements with
transition/shadow polish for visual completeness. No logic change, only presentation.

Verified: ruff check/format pass, 181 pytest pass, dashboard SSR/API intact. Keeps history atomic
before push per CEO GO.

## v0.7.0 (2026-08-25)

### Bug Fixes

- **dashboard**: P0 refuter fixes - form double-read, htmx load, payload OOM, hide 405 actions
  ([`1dad496`](https://github.com/deuriib/mcp-gateway/commit/1dad49629a15da5ac2cdce49ce293a4cfb4f00ad))

- api.handle_create: check Content-Type before consuming body; Content-Length pre-check before read
  prevents OOM; JSON branch reads body only when application/json else uses form without prior
  body() to avoid empty form (fixes H-01). Enforce 413 for both branches.

- htmx.min.js stub: add DOMContentLoaded loader for hx-trigger load so GET /dashboard/servers
  auto-fetches; support hx-swap outerHTML, keep <20KB, no Node.

- views.server_row: hide Wave1-unimplemented hx-delete/hx-patch (would 405); Wave1 demo shows only
  inspect. Keeps js handlers for Wave2.

- local gating: retain MCP_GWAY_ALLOW_LOCAL_VIA_DASHBOARD default 1 (dashboard allows local unless 0) - documented.

Verified: ruff clean, 171 pytest green, manual form hx POST 201, content-length 413.

- **security**: P0 hardening for dashboard and registry (BR-UI-003/004/009, HC-03/05, EC-01..04,
  AC-09)
  ([`c3216df`](https://github.com/deuriib/mcp-gateway/commit/c3216dff0268b7c346d61d217e648d72bf42ee44))

- models: strict regex ^[A-Za-z_][A-Za-z0-9_]{0,63}$ + reserved (con,prn,aux,nul,com1-9,lpt1-9) +
  reject / \ . .. and < > ; ensures ../../evil, /absolute, a/b, .. etc 400 - registry: _safe_path
  with regex + resolve().is_relative_to() defense-in-depth, atomic write via .tmp replace, guard all
  servers_dir usages - oauth: FileTokenStorage validates server_name with same regex and traversal
  check - dashboard/api: html.escape for all toasts/detail, form vs json content-type handling,
  payload limit 1M ->413, semaphore(3) for discovery, validate via MCPServerConfig before existence,
  generic validation_error without secret leak, delegate to Registry only, local via dashboard gated
  by env - dashboard/views: urllib.parse.quote for detail/delete URLs, htpy auto-escape kept -
  cli/gateway: serve defaults 127.0.0.1, gate non-loopback behind MCP_GWAY_ALLOW_REMOTE=1 else exit
  2, X-Warning header for non-loopback - tests: existing 171 green, manual curl checks for
  traversal, XSS, form hx, masking ***

### Chores

- Add pre-commit hook enforcing ruff check+format locally
  ([`1eee823`](https://github.com/deuriib/mcp-gateway/commit/1eee82390a89d3194187759dd58cd18ae9f7c696))

Prevent future CI failures like run 32782781915 where ruff F401+I001 blocked pipeline and caused
Release skip. Add deterministic local gate so git commit fails fast if lint not clean - haces las
cosas con excelencia desde el commit 1.

- .pre-commit-config.yaml pinned to astral-sh/ruff-pre-commit v0.16.4 with ruff --fix and
  ruff-format plus hygiene hooks (trailing-whitespace, end-of-file-fixer, check-yaml,
  check-added-large-files) - pyproject.toml dev group adds pre-commit>=4.0.0 - AGENTS.md documents
  uv run pre-commit install and run --all-files with CI parity ruff commands - Fix trailing
  whitespace in spec uncovered by new hook - Verified: uv run pre-commit run --all-files, ruff
  check/format, and pytest 152 passed exit 0

- Sync uv.lock to 0.6.0
  ([`2963e8b`](https://github.com/deuriib/mcp-gateway/commit/2963e8b72b1b63019c964b299d2abaf1411ad5fc))

Co-authored-by: Vasquez <deuriib@gmail.com>

- **ci**: Bump workflows to latest Node24 (checkout v7, setup-python v7, setup-uv v10)
  ([`a407e8f`](https://github.com/deuriib/mcp-gateway/commit/a407e8f29e2f79f24dfd17d4ddeef2d8fecc851b))

Opcion B (latest estable) sobre A (minimo). CTO pidio explicitamente B: llevar todo a latest Node24
nativo con security hardening y sin warnings Node20. Preserva logica de jobs, solo bump de tags.

Bumps: - actions/checkout@v5.0.1 -> @v7.0.1 (latest Node24 immutable, publicado 20-jul-2026, ESM,
fix SHA-256 repos y fork-PR blocking; action.yml using: node24 verificado) -
actions/setup-python@v6.3.0 -> @v7.0.0 (latest Node24 ESM, publicado 20-jul-2026; action.yml
using: node24 verificado) - astral-sh/setup-uv@v7.0.0 -> @v10.0.1 immutable via SHA
20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1 (latest Node24 immutable desde v8.0.0,
publicado 14-ago-2026; action.yml using: node24 verificado; SHA pin es ideal immutable, tag
@v10.0.1 tambien immutable)

Trade-offs vs A: - A = higiene minima (primer major Node24: checkout v5, setup-python v6, setup-uv
v7) minimo bump, minimo riesgo. - B = latest estable: mas fixes/security hardening (checkout v7
SHA-256 + ESM + allow-unsafe-pr-checkout), setup-python v7 ESM, setup-uv v10 ultimas
features/perf. Mayor churn de major pero still Node24 native y elimina deuda futura. Elegido por
decision explicita CTO.

Compatibilidad runner: - checkout@v7 y setup-python@v7 (ESM) requieren runner >=v2.327.1.
ubuntu-latest actual es v2.330+ -> OK.

Breakings documentados (no mitigados, comportamiento seguro deseado): - setup-uv@v10: enable-cache
auto ahora deshabilita cache en workflow_run y release (seguridad #984). Nuestro release.yml es
workflow_run -> cache se deshabilitara por defecto. Es el comportamiento seguro deseado, no se
hace override. - checkout@v7: nuevo allow-unsafe-pr-checkout=false bloquea checkout de fork PR en
workflow_run/pull_request_target. Nuestro release.yml corre sobre workflow_run de Tests en
main/master (no fork) -> sin impacto, pero documentado.

No toca semver, no toca uv.lock, no mezcla otros chores. Tags completos pinned para
reproducibilidad.

Validacion local: - uv run ruff check src/ tests/ -> All checks passed - uv run ruff format --check
src/ tests/ -> 25 files already formatted - uv run pytest -v -> 152 passed - python yaml.safe_load
ambos workflows -> YAML valid OK - grep confirma solo v7.0.1/v7.0.0/v10.0.1 (SHA), sin
v5.0.1/v6.3.0/v7.0.0 residuales

- **ci**: Hybrid release workflow for v0.7.0 GA
  ([`b45dbc0`](https://github.com/deuriib/mcp-gateway/commit/b45dbc0cf23734bd7af9c79b9899aafa15c406a0))

- **ci**: Migrate workflows from Node20 to Node24 native
  ([`a3b78ee`](https://github.com/deuriib/mcp-gateway/commit/a3b78ee9d70c73febc9615c337be23d2ce0d2e6d))

GitHub deprecated Node20 (EOL Apr 2026, runners default Node24 since 2026-06-16). Workflows
test.yml/release.yml used checkout@v4, setup-python@v5 and setup-uv@v4 (all Node20) causing
'Node.js 20 is deprecated' warnings. FORCE_JAVASCRIPT_ACTIONS_TO_NODE24 only masks.

Migrate to minimal native Node24 majors (higiene minima, no logic change): - actions/checkout@v4 ->
@v5.0.1 (first Node24; v5.0.1 chosen over v6.1.0/ v7.0.1 which are also Node24 to minimize major
bump; v5.1.0 also Node24 but v5.0.1 matches ticket example and is stable patch) -
actions/setup-python@v5 (Node20) -> @v6.3.0 (first Node24 major is v6; ticket incorrectly says @v5
is Node24 - corrected: v5=Node20, v6=Node24; v6.3.0 is latest v6 patch for fixes, verified
v6.0.0..v6.3.0 and v7.0.0 all Node24; v7 exists but v6 is minimal) - astral-sh/setup-uv@v4
(Node20) -> @v7.0.0 (v5/v6 still Node20, v7 first Node24; verified v4/v5/v6=Node20,
v7.0.0/v7.6.0/v10.0.1=Node24; v7.0.0 is minimal Node24, v7.6.0+ also Node24 but minimal chosen)

Verified python-semantic-release@v9 uses: docker and pypa/gh-action-pypi-publish@release/v1 uses:
composite (no Node, no change).

Compatibility: Node24 requires runner >=2.327.1, ubuntu-latest cumple. Tags pinned con version
completa para reproducibilidad.

Evidencia action.yml using: node24 consultada: - checkout@v5.0.1, v6.0.3, v7.0.0 -> node24 -
setup-python@v5 -> node20, @v6.3.0/@v7.0.0 -> node24 - setup-uv@v4/v5/v6 -> node20, @v7.0.0 ->
node24 - psr@v9 -> docker, pypi-publish@release/v1 -> composite

Validacion local: uv run ruff check/format OK, pytest 152 passed, YAML syntax OK, grep sin
checkout@v4/setup-python@v5/setup-uv@v4, solo Node24.

- **release**: Bump version 0.6.0 -> 0.7.0 for GA
  ([`5f96c44`](https://github.com/deuriib/mcp-gateway/commit/5f96c449005a366e77cccc98759131662802a961))

### Documentation

- Promote OpenCode remote/local as primary, deprecate http/stdio/sse, document pre-commit
  ([`e4a6745`](https://github.com/deuriib/mcp-gateway/commit/e4a6745f3bac834916671e5058e097dfd97906c1))

- README: primary remote/local examples with --header/--oauth/--timeout/--enabled/--env/--cwd,
  deprecated http/stdio/sse section kept for compat, Commands table updated to remote|local, Options
  table expanded to 12+ flags including --args/--tools/--oauth-port (deprecated compat noted),
  refresh/serve signatures clarified, registry description corrected to .pyi signatures + .json
  config, Development reflects uv sync --all-groups and pre-commit hygiene hooks (6 hooks) -
  AGENTS.md: CLI primary remote/local with full options pointer, deprecated note, Development with
  pre-commit, registry pattern updated - Fixes reliability findings F-01/F-02/F-03/F-11/F-12/F-13;
  --docs-url marked as deprecated not persisted per refuter

### Features

- **dashboard**: Management MCPs dashboard GA
  ([`e1d52eb`](https://github.com/deuriib/mcp-gateway/commit/e1d52ebc6c101bde6fa408c8fb88b3e4eac862b1))

## v0.6.0 (2026-08-25)

### Bug Fixes

- Address final review critical findings
  ([`1341949`](https://github.com/deuriib/mcp-gateway/commit/13419499769f593c902dcf0bba7f0e11016b9237))

- **cli**: Correct timeout None guard ordering
  ([`8b4c5e4`](https://github.com/deuriib/mcp-gateway/commit/8b4c5e49b121734b353c190e74cb8612051a1342))

- **tests**: Remove unused StdioConfig and sort imports (F401, I001)
  ([`426ff62`](https://github.com/deuriib/mcp-gateway/commit/426ff62ded5e24a854f337371f3673ffcf86f777))

Unblocks CI run 32782781915 which failed on ruff check (F401 in conftest.py:9, I001 in
test_transport.py:3) causing Release 32782803712 to skip. No functional change â€” 152 tests pass,
ruff check/format clean.

### Chores

- Sync uv.lock to 0.5.2
  ([`e195a1f`](https://github.com/deuriib/mcp-gateway/commit/e195a1fb01418a948635afcc6fb92e6bac15834c))

### Documentation

- Add OpenCode schema adoption spec and plan
  ([`98b857f`](https://github.com/deuriib/mcp-gateway/commit/98b857fccfbce94c35b6d0a2d2837d7816229565))

Co-Authored-By: Vasquez CTO <vasquez@mcp-gateway>

### Features

- **cli**: Integrate transport auto-detection
  ([`6b9d1e6`](https://github.com/deuriib/mcp-gateway/commit/6b9d1e6594dffaec07d2c16756c508fdcdf7f9c7))

- **cli**: Opencode-style options with backward compat
  ([`69163bd`](https://github.com/deuriib/mcp-gateway/commit/69163bd5cca7de3119aeee86273b55652fe07526))

- **models**: Add MCPServerConfig with OpenCode schema
  ([`a1771f0`](https://github.com/deuriib/mcp-gateway/commit/a1771f048bfbfebbb45c14b6984c5f0a0d24d5bd))

- **registry**: Opencode JSON format with auto-migration
  ([`4489f97`](https://github.com/deuriib/mcp-gateway/commit/4489f9792c41969ef168419737c6289daf9fbd3f))

- **transport**: Auto-detect streamable-http/sse/http
  ([`50bd03e`](https://github.com/deuriib/mcp-gateway/commit/50bd03edbd163e9282aac9ca52201497f62451c4))

### Refactoring

- Update fixtures to MCPServerConfig and fix lint
  ([`0fb1a32`](https://github.com/deuriib/mcp-gateway/commit/0fb1a321f715530a6a0673bf845e07fa6278b203))

## v0.5.2 (2026-08-24)

### Bug Fixes

- **sandbox**: Inject print as no-op to prevent Variable not found error
  ([`7064975`](https://github.com/deuriib/mcp-gateway/commit/70649759664c3e5945d1b911d2d54dd809a0d731))

Starlark sandbox lacked a print builtin, causing cryptic errors when users wrote print() in
executeToolCode. Inject _noop as print so scripts with print() run without failing.

## v0.5.1 (2026-08-24)

### Bug Fixes

- Sanitize hyphenated MCP tool names for Starlark sandbox
  ([`55ca24d`](https://github.com/deuriib/mcp-gateway/commit/55ca24dd17fac49685733cdbb720106751d546f0))

MCP servers like context7 expose tools with hyphens (query-docs, resolve-library-id) which break
Starlark struct syntax. Add _sanitize_identifier() to convert non-identifier characters to
underscores at the Starlark boundary, preserving original names for MCP calls.

## v0.5.0 (2026-08-24)

### Bug Fixes

- Resolve ruff lint errors (S110, I001)
  ([`00bb396`](https://github.com/deuriib/mcp-gateway/commit/00bb396d81d2766e1ad683210696f33248f40aaf))

### Features

- Wire MCP tool execution into Starlark sandbox via ServerFactory
  ([`452d258`](https://github.com/deuriib/mcp-gateway/commit/452d258688ef187d667e958269b98e0af9260914))

Previously, executeToolCode ran code in an empty sandbox with no access to MCP servers. This commit
bridges the gap by:

- Adding ServerFactory: creates server structs and call_tool function that wrap async MCP client
  calls with asyncio.run() for sync access - Extending StarlarkSandbox with set_global() for
  injecting functions - Wiring CodeMode to inject call_tool + server structs on init - Updating
  executeToolCode description to document tool access

112 tests passing, 0 regressions.

## v0.4.4 (2026-08-24)

### Bug Fixes

- Mock win32 platform in absolute_path_invalid test for CI (Linux)
  ([`1c8faad`](https://github.com/deuriib/mcp-gateway/commit/1c8faad645948334fd8747bca0f00bbced993012))

- Use Self type for **aenter**/**aiter** (ruff PYI034)
  ([`349986e`](https://github.com/deuriib/mcp-gateway/commit/349986e3f36378616d7cdfefb97097b1ccd1e78b))

- Windows stdio transport â€” command resolution, noise filter, env passthrough
  ([`c4c2a69`](https://github.com/deuriib/mcp-gateway/commit/c4c2a69ee120a02a729a2bf2dad1f54628f2f221))

- Add stdio_transport.py: resolve_windows_command prefers .exe over .cmd/.bat to bypass cmd.exe
  banner injection on Windows - Add filtered_stdio_client: wraps MCP SDK stdio_client, drops
  non-JSON parse failures from read stream with on_noise callback - Fix _FilteredReadStream to
  implement async context manager protocol (**aenter**/**aexit**) required by MCP SDK dispatcher -
  Fix t.inputSchema -> t.input_schema for MCP SDK v2 compatibility - Wire StdioConfig.envs ->
  StdioServerParameters.env with --env CLI option - Wire on_noise callback in production (logs
  warning to stderr) - 22 new tests in test_stdio_transport.py, 3 new tests in test_cli.py, 1 new
  test in test_registry.py (96/96 pass, ruff clean)

## v0.4.3 (2026-08-24)

### Bug Fixes

- Refresh continues after individual server errors
  ([`4a9afe3`](https://github.com/deuriib/mcp-gateway/commit/4a9afe300efd0c3d774ada45d6798c8273cdc809))

Extract _refresh_server as standalone async function (was defined inside the for loop). Wrap each
server refresh in try/except so a failure in one server does not abort the entire refresh cycle.

## v0.4.2 (2026-08-24)

### Bug Fixes

- Parse stdio command from connection_string in old .pyi fallback
  ([`1acdeed`](https://github.com/deuriib/mcp-gateway/commit/1acdeed05d4b856aafeeab2bf9ec822f418d4770))

Old-format STDIO .pyi files store the command in # connection_string: instead of # stdio_command:.
The fallback parser was checking for stdio_command first and creating no StdioConfig when it was
missing, causing validation errors on refresh.

## v0.4.1 (2026-08-24)

### Bug Fixes

- List command reads connection type from JSON config
  ([`988bba3`](https://github.com/deuriib/mcp-gateway/commit/988bba3314c6c699a7eec89c774ca7e95cdd3721))

list_servers() was parsing .pyi comments for connection_type, which no longer exist in the new
JSON-based format. Now reads from get_config() which handles both JSON and legacy .pyi comment
fallback.

## v0.4.0 (2026-08-24)

### Features

- Auto-auth OAuth flow, stdio config persistence, token cleanup
  ([`0c4d448`](https://github.com/deuriib/mcp-gateway/commit/0c4d448b954d66d6e320dd5bba1b3a1d94bcac58))

- Add force_auth param to _discover_tools for conditional OAuth - Add/remove/refresh commands try
  without auth first, OAuth only on failure - Persist stdio_command and stdio_args in .pyi registry
  files - Clean up stored OAuth tokens on server remove - Backward compat for old .pyi files without
  stdio comments - Add comprehensive tests for all new behaviors

- Harden gateway with session TTL, sandbox timeout, clean registry, and configurable OAuth
  ([`6d51ebc`](https://github.com/deuriib/mcp-gateway/commit/6d51ebc6099dc6656a7faf8a6aa3aa27958f0ae5))

- Session TTL + cleanup: evict idle sessions after 5min, send None sentinel to close SSE streams,
  return JSON-RPC error for expired sessions - Real sandbox timeout: ThreadPoolExecutor with
  configurable timeout (default 30s), SandboxTimeoutError for slow injected callbacks - Deduplicate
  _discover_tools: extract _create_client_transport async context manager, single flight path for
  all connection types - STREAMABLE_HTTP validation: require connection_string in model_post_init -
  Configurable OAuth port: --oauth-port option on add/refresh commands - Clean registry: config in
  JSON files, .pyi contains only tool signatures, backward compatible with old comment-style .pyi
  files - serverInfo.version now reads **version** instead of hardcoded 0.1.0 - 22 new tests (71
  total), all passing, lint clean

## v0.3.0 (2026-08-24)

### Features

- Move servers/ to ~/.config/mcp-gway/servers/
  ([`db62a5a`](https://github.com/deuriib/mcp-gateway/commit/db62a5a6fb4eafc8547191ce8a8685f9152c31c9))

## v0.2.1 (2026-08-24)

### Bug Fixes

- Return docs_url in getToolDocs instead of opening browser
  ([`7bc1457`](https://github.com/deuriib/mcp-gateway/commit/7bc145717a113e8840d4f7dcce5c80ba4d14875a))

## v0.2.0 (2026-08-24)

### Features

- Add --docs-url option and open browser in getToolDocs
  ([`c41f412`](https://github.com/deuriib/mcp-gateway/commit/c41f41209f8c720ab3e270100201f5325a639aed))

## v0.1.4 (2026-08-24)

### Bug Fixes

- Update config path to mcp-gway in oauth, gateway, cli
  ([`9ce40ba`](https://github.com/deuriib/mcp-gateway/commit/9ce40ba8f367903b612afdbd63afc930d3f47a6e))

### Documentation

- Update package name to mcp-gway in README and AGENTS
  ([`6a3e48e`](https://github.com/deuriib/mcp-gateway/commit/6a3e48e4dc777dacf270c113f74361f3d85cc801))

## v0.1.3 (2026-08-24)

### Bug Fixes

- Rename package to mcp-gway for PyPI
  ([`e1e6622`](https://github.com/deuriib/mcp-gateway/commit/e1e6622d9b139bd23b0cae500aefef8f29ba8d66))

- Rename Python module to mcp_gway to match PyPI package name
  ([`4c6de5d`](https://github.com/deuriib/mcp-gateway/commit/4c6de5d9a6fc9d3212ba3a98c2e0a1336660a24e))

## v0.1.2 (2026-08-24)

### Bug Fixes

- Build package after semantic release bumps version
  ([`be80eeb`](https://github.com/deuriib/mcp-gateway/commit/be80eeb1f0eccb9bbd863df71d3671424b90bced))

### Continuous Integration

- Chain release workflow to run after tests pass
  ([`bfe88bc`](https://github.com/deuriib/mcp-gateway/commit/bfe88bcd0127db06385013f21a7f8a3716b50137))

## v0.1.1 (2026-08-24)

### Bug Fixes

- Update docstring format
  ([`f421602`](https://github.com/deuriib/mcp-gateway/commit/f4216026bc86c833c1fadc3bdef4cf6d9803b75b))

## v0.1.0 (2026-08-24)

### Chores

- Initial commit with plan and spec
  ([`2ebf698`](https://github.com/deuriib/mcp-gateway/commit/2ebf698e2324b91b9824b7b219dfe263d97d6aaa))

- Remove cached pycache files
  ([`44d4143`](https://github.com/deuriib/mcp-gateway/commit/44d4143e0a1946435146fc17da3b9fb6f11ddf7b))

### Continuous Integration

- Add semantic release and fix uv installation
  ([`e6db163`](https://github.com/deuriib/mcp-gateway/commit/e6db163b12d8cc6960fa02ea47729b22379fce52))

- Replace publish.yml with release.yml for automatic versioning - Add python-semantic-release
  configuration - Fix uv installation in GitHub Actions using astral-sh/setup-uv - Add branch
  triggers for main and master

### Features

- Cli commands for MCP gateway management
  ([`f86a9ae`](https://github.com/deuriib/mcp-gateway/commit/f86a9ae2c4e63386fa5cc34c796933fc0b56c5dc))

- Code mode with 4 meta-tools
  ([`12e3f72`](https://github.com/deuriib/mcp-gateway/commit/12e3f727042128f15635c2671f66d8bda44696c6))

- Http/sse gateway server with JSON-RPC 2.0
  ([`edaba81`](https://github.com/deuriib/mcp-gateway/commit/edaba81582db7575e0ba48c37d62a07318a9b27f))

- Integration test and project documentation
  ([`b55a40b`](https://github.com/deuriib/mcp-gateway/commit/b55a40bc3e9df68b9cdcd9234dadd57f5ecacea1))

- Oauth support, refresh command, SSE transport, and project docs
  ([`bc5d5d0`](https://github.com/deuriib/mcp-gateway/commit/bc5d5d051b4b6d79adeacec5d61d4c4058f73382))

- Added OAuth 2.0 support with dynamic client registration (RFC 7591) - Added refresh command for
  re-authenticating and re-discovering tools - Added POST /mcp endpoint for direct JSON-RPC - Added
  streamable-http transport type - Added agentmemory, context7, supabase, betterfullstack MCP
  servers - Professional README with architecture diagram - AGENTS.md for AI assistants - GitHub
  Actions workflows for testing and PyPI deployment - MIT License

- Project scaffold with models and tests
  ([`22f4b80`](https://github.com/deuriib/mcp-gateway/commit/22f4b80aed81def6f730df33c28e3ce02522c405))

- Registry for .pyi file CRUD operations
  ([`65d69ee`](https://github.com/deuriib/mcp-gateway/commit/65d69eef749f9de1b97f616d71bc44c2f0fbb573))

- Starlark sandbox and server proxy for code mode
  ([`1e63043`](https://github.com/deuriib/mcp-gateway/commit/1e630430b8e908afed19f37258738f93f4ecd6a7))

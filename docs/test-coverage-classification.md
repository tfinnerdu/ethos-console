# Test Coverage Classification

Contract-pinned / characterization tests for files with no live-infra dependency
live in `console/tests/characterization/` (e.g. the real `ColleagueApiClient`
and `UnidataClient` classes, as opposed to their mock subclasses). Regular
unit/route tests stay in `console/tests/` alongside everything else.

Every production source file must be accounted for by exactly one (or more) of:

| Category | Symbol | Meaning |
|---|---|---|
| **Unit-tested** | ✅ | Behavior asserted by pytest / xunit test file |
| **Contract-pinned** | 📌 | Invariant locked in `test_contracts.py` / `*ContractTests.cs` |
| **Compile-verified** | 🔧 | Purely declarative — compiler + analyzers cover correctness |
| **Manual-procedure** | 📋 | Host-dependent UI or streaming flow; step-by-step in `docs/e2e-testing.md` |

---

## Python Console (`console/app/`)

| File | Category | Coverage reference |
|---|---|---|
| `app/__init__.py` | ✅ 📌 | App factory exercised by every test via `conftest.py`; blueprint prefixes (incl. `/api/cn`, `/api/dob-repair`) pinned in `test_contracts.py`; `register_auth_gate(app)` exercised by `test_auth.py` |
| `app/audit.py` | ✅ 📌 | `test_audit.py` — write_event, query_events, actor fallback, pagination, filters |
| `app/auth.py` | ✅ | `test_auth.py` — fail-closed when unconfigured/default `SECRET_KEY`, `verify_credentials`, session login/logout, `next` sanitization, exemption list (`/api/health/live`, `/login`, `/logout`, `/static/*`) |
| `app/bus_monitor.py` | ✅ | `test_bus_monitor.py` — all pure-logic methods; `start()`/`stop()` + no-auto-start-on-boot regression guard in `test_bus_api.py`; thread loop is 📋 (see §4 Frontend smoke in e2e-testing.md) |
| `app/cn_repository.py` | ✅ | `test_cn_monitor_api.py` exercises the routes that call this; `MockCnRepository` characterized in `test_mock_mode.py` |
| `app/colleague_api_client.py` | ✅ | `tests/characterization/test_colleague_api_client_characterization.py` exercises the REAL client (headers/basic-auth encoding, URL construction, `_LegacyTlsAdapter`'s TLS verification is left intact); `test_mock_mode.py` only covers `MockColleagueApiClient`, a subclass that overrides every network-calling method and previously left this file's own code unexercised — do not cite that test alone as coverage for this file |
| `app/conductor_client.py` | ✅ | `test_replay_api.py` swaps the extension to a MagicMock for trigger paths |
| `app/database.py` | ✅ 📌 | Model to_dict() shapes pinned in `test_contracts.py`; CRUD exercised via API tests; seed counts pinned |
| `app/ethos_client.py` | ✅ | `test_ethos_client.py` — all methods mocked with `requests`; `get_resource_by_id` and `publish_notification` exercised via `test_cn_monitor_api.py` push tests |
| `app/health_monitor.py` | ✅ | `test_health_monitor.py` — latency percentiles, thresholds, resource health |
| `app/request_utils.py` | ✅ | `test_request_utils.py` — `get_json_body()` coerces every non-dict JSON body (falsy AND truthy: null/[]/""/0/false and 42/"str"/[1,2]/true) to `{}`, unlike the `or {}` idiom it replaced |
| `app/unidata_client.py` | ✅ | `tests/characterization/test_unidata_client_characterization.py` — `_parse_list_ids()` (pure function), connection param passthrough, `run_command`/`call_subroutine` argument marshalling (mocked `_uopy`, mirroring the `pyodbc`-mock pattern in `test_dob_sql_source.py`); previously entirely unaccounted for in this doc |
| `app/routes/__init__.py` | 🔧 | Empty init file |
| `app/routes/auth.py` | ✅ | Login/logout flow in `test_auth.py` (wrong/correct credentials, `next` param, already-authenticated redirect); login.html render is 📋 |
| `app/routes/cn_monitor.py` | ✅ 📌 | `test_cn_monitor_api.py` — health, notifications/detail/paragraph, history (audit-backed), diagnostics set-diff, push (one audit per publish), audit log; `/api/cn` prefix pinned in `test_contracts.py` |
| `app/routes/bus.py` | ✅ 📋 | REST endpoints in `test_bus_api.py`, incl. `/start`, `/stop`, non-numeric `limit` guard on `/export`, and audit emission on preset create/delete; SSE `/stream` is 📋 (§4 e2e-testing.md — streaming requires live WSGI) |
| `app/routes/colleague_api.py` | ✅ | `test_colleague_api.py` — about/event-configurations/transaction/metadata, 503-unconfigured shapes, non-object JSON body, audit emission (success and failure) on the CTX transaction call; previously entirely absent from this doc with zero route-level tests |
| `app/routes/dob_repair.py` | ✅ | `test_dob_repair_api.py` — analyze (CSV upload + configured-path fallback + SQL fetch), status, candidates, decision (incl. audit emission, deliberately excluding DOB values from the audit `detail` blob), export corrections |
| `app/routes/env.py` | ✅ | `test_env.py` — list, switch (success/404/non-object body), credential swap, cache invalidation, audit emission; previously not listed in this doc and only exercised incidentally as a cache-invalidation side effect from `test_resources_api.py` |
| `app/routes/errors.py` | ✅ | `test_errors_api.py` — list, filter, spikes, flush (one summary audit event per batch, not one per row), export, non-numeric paging-param guards |
| `app/routes/graphql_routes.py` | ✅ 📌 | `test_graphql_api.py`; cache TTL value pinned in `test_contracts.py` |
| `app/routes/health.py` | ✅ 📌 | `test_health.py`; liveness probe contract in `test_contracts.py`; `/` and `/token` gating (now global, not per-route) exercised in `test_auth.py` |
| `app/routes/main.py` | ✅ 📋 | Page routes (incl. `/dob-repair`) exercised by `test_auth.py`'s gate tests; tab rendering and navigation are 📋 (§4 frontend smoke test) |
| `app/routes/mnemonics.py` | ✅ | `test_mnemonics_api.py` — full CRUD, filter, uppercase, 404, 409 |
| `app/routes/phase3.py` | ✅ 📌 | All four 503 responses in `test_contracts.py`; full UI is 📋 (§4 Phase 3 — requires UNIDATA_CONN_STR) |
| `app/routes/replay.py` | ✅ | `test_replay_api.py` — fetch, trigger, history, DB persistence |
| `app/routes/resources.py` | ✅ | `test_resources_api.py` — list, cn-enabled, annotate, annotations list |
| `app/routes/schema_browser.py` | ✅ | `test_schema_browser_api.py` — types list, type detail, resource-schema, validate |
| `app/dob_detector.py` | ✅ | `test_dob_detector.py` — pure-Python PD0002124 detection engine, no Flask/DB coupling |
| `app/dob_sql_source.py` | ✅ | `test_dob_sql_source.py` — read-only guard (rejects writes/multi-statement/`SELECT...INTO`), connection-string building, row-to-Record mapping (mocked `pyodbc`, no live SQL Server) |
| `config.py` | 📌 | `AUTH_USERNAME`/`AUTH_PASSWORD`/`SECRET_KEY`/`DOB_RECONCILE_INPUT_CSV` env-var wiring exercised by `test_auth.py` and `test_dob_repair_api.py` |
| `run.py` | 🔧 | Flask `app.run()` entry point — no runtime logic to test |

---

## JavaScript (`console/static/js/`)

JavaScript is not unit-testable in the current test setup (no Jest/browser harness). All JS files are covered by **📌 contract-pinned** API shape tests (the JS only works if the API responds correctly) and **📋 manual procedure** (§4 Console Smoke Test in `docs/e2e-testing.md`).

| File | Contract-pinned via | Manual procedure |
|---|---|---|
| `bus_monitor.js` | `test_bus_api.py` shapes | §4 Bus Monitor — Start/Stop control, SSE stream dot, pause/resume, export |
| `cn_monitor.js` | `test_cn_monitor_api.py` shapes | §4 CN Monitor — health dot, notification list, diagnostics diff, audit log |
| `colleague_query.js` | `test_contracts.py` phase3 503 shape | §4 Phase 3 setup guide renders correctly |
| `dob_repair.js` | `test_dob_repair_api.py` shapes | §4 DOB Repair — upload/analyze, review queue actions, elevated-risk/unparseable sections, export download |
| `errors.js` | `test_errors_api.py` — list/spikes/flush shapes | §4 Errors tab — tile counts, spike chart, CSV download |
| `field_diff.js` | `test_contracts.py` phase3 503 shape | §4 Phase 3 setup guide renders correctly |
| `graphql_builder.js` | `test_graphql_api.py` — schema, execute, saved query shapes | §4 GraphQL Builder — schema tree, query run, save/delete |
| `health.js` | `test_health.py` — full health response key contract | §4 Health tab — token badge, queue bar, resource rows |
| `mnemonics.js` | `test_mnemonics_api.py` shapes | §4 Mnemonics tab — list, search, create, edit, delete |
| `replay.js` | `test_replay_api.py` shapes | §4 Replay tab — fetch message, trigger, history |
| `resources.js` | `test_resources_api.py` shapes | §4 Resources tab — list renders, annotation modal saves |
| `schema_browser.js` | `test_schema_browser_api.py` shapes | §4 Schema Browser — type list, field table, validator |

---

## HTML Templates (`console/app/templates/`)

All templates are **🔧 compile-verified** by Flask's Jinja2 template engine (syntax errors surface on first render) plus **📋 manual procedure** for layout and interaction. Route-render is also exercised by auth and health contract tests.

| File | Additional coverage |
|---|---|
| `base.html` | 📌 Navigation tabs (incl. DOB Repair) rendered in page-route tests |
| `login.html` | ✅ `test_auth.py` — wrong credentials show error, correct credentials redirect, not-configured notice |
| `bus_monitor.html` | 📋 §4 Bus Monitor |
| `cn_monitor.html` | ✅ 📋 `test_auth.py` renders page; setup guide + live UI are 📋 §4 CN Monitor |
| `colleague_query.html` | 📋 §4 Phase 3 (setup guide path + configured path) |
| `dob_repair.html` | 📋 §4 DOB Repair |
| `errors.html` | 📋 §4 Errors tab |
| `field_diff.html` | 📋 §4 Phase 3 |
| `graphql.html` | 📋 §4 GraphQL Builder |
| `health.html` | 📋 §4 Health tab |
| `mnemonics.html` | 📋 §4 Mnemonics tab |
| `relay.html` | 📋 §4 Replay tab |
| `resources.html` | 📋 §4 Resources tab |
| `schema_browser.html` | 📋 §4 Schema Browser |

---

## Mock-mode providers (`console/app/mocks/`)

| File | Category | Coverage reference |
|---|---|---|
| `ethos.py`, `colleague_api.py`, `conductor.py`, `unidata.py`, `cn_repository.py` | ✅ 📌 | `test_mock_mode.py` — three required signals (badge / header / health key) + characterization for every provider's fixture shape; parametrized smoke test asserts every tab returns 200 in mock mode |
| `fixtures.py` | 📌 | Pinned by the characterization tests above |

---

## Infrastructure & Configuration

| File | Category | Notes |
|---|---|---|
| `console/config.py` | 📌 | Env var wiring tested via `test_auth.py`, `test_dob_repair_api.py`, and `test_contracts.py` |
| `console/run.py` | 🔧 | Entry point |
| `console/Dockerfile` | 📋 | Manual: build the image and confirm it starts (no dedicated e2e-testing.md section since the CNM Docker Compose stack was retired) |
| `console/k8s/*.yaml` (5 files) | 📋 | Manual deploy smoke test; liveness probe path (`/api/health/live`) is 📌 pinned in test_contracts.py |
| `console/requirements.txt` | 🔧 | pip install — no testable behavior |
| `console/pytest.ini` | 🔧 | pytest config |
| `start-local.ps1` | 📋 | Manual: run it and confirm the console starts (see §2 intro in e2e-testing.md) |

---

## Coverage Gaps (Accepted)

| Item | Reason not tested | Mitigation |
|---|---|---|
| `BusMonitor` daemon thread loop | Threading + blocking I/O; cannot test without live Ethos | Pure-logic methods are 100% unit-tested; thread behavior is 📋 §4 Bus Monitor SSE dot |
| `bus.py /stream` SSE endpoint | Streaming requires a real WSGI server (not Flask test client) | Bus logic tested via `test_bus_api.py`; stream verified by 📋 §4 |
| Phase 3 configured path | Requires UNIDATA ODBC driver and DSN | 503 path fully tested; configured stub returns valid shape |
| DOB SQL fetch — requires ODBC driver | Requires Microsoft ODBC Driver 18 for SQL Server and a live SQL Server; not available in the test sandbox | `is_configured()`/`fetch_records()` mocked in `test_dob_repair_api.py` and `test_dob_sql_source.py`; connection-string building and read-only guard fully unit-tested; live fetch verified manually against a real server |
| JS behavior | No browser/Jest harness in this project | API shape contracts ensure JS receives correct data; 📋 manual test covers rendering |

---

## Running the Full Suite

```bash
# Python (446 tests)
cd console && python -m pytest tests/ -v
```

Manual procedures: see `docs/e2e-testing.md` §4 for the full console smoke test checklist.

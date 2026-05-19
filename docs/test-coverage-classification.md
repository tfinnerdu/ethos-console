# Test Coverage Classification

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
| `app/__init__.py` | ✅ 📌 | App factory exercised by every test via `conftest.py`; blueprint prefixes (incl. `/api/cn`) pinned in `test_contracts.py` |
| `app/auth.py` | ✅ | `test_auth.py` — check_key, api_auth_required, _auth_enabled |
| `app/cn_client.py` | ✅ | `test_cn_monitor_api.py` — all methods exercised via mocked CnmClient |
| `app/bus_monitor.py` | ✅ | `test_bus_monitor.py` — all pure-logic methods; thread loop is 📋 (see §12 Bus Monitor in e2e-testing.md) |
| `app/database.py` | ✅ 📌 | Model to_dict() shapes pinned in `test_contracts.py`; CRUD exercised via API tests; seed counts pinned |
| `app/ethos_client.py` | ✅ | `test_ethos_client.py` — all methods mocked with `requests`; `get_resource_by_id` and `publish_notification` exercised via `test_cn_monitor_api.py` push tests |
| `app/health_monitor.py` | ✅ | `test_health_monitor.py` — latency percentiles, thresholds, resource health |
| `app/routes/__init__.py` | 🔧 | Empty init file |
| `app/routes/auth.py` | ✅ 📌 | Login/logout flow in `test_contracts.py` auth section; login.html render is 📋 |
| `app/routes/cn_monitor.py` | ✅ 📌 | `test_cn_monitor_api.py` — 503 shape, 200 happy paths, 502 upstream errors, push 400/200/partial results; `/api/cn` prefix pinned in `test_contracts.py` |
| `app/routes/bus.py` | ✅ 📋 | REST endpoints in `test_bus_api.py`; SSE `/stream` is 📋 (§12 e2e-testing.md — streaming requires live WSGI) |
| `app/routes/errors.py` | ✅ | `test_errors_api.py` — list, filter, spikes, flush, export |
| `app/routes/graphql_routes.py` | ✅ 📌 | `test_graphql_api.py`; cache TTL value pinned in `test_contracts.py` |
| `app/routes/health.py` | ✅ 📌 | `test_health.py`; liveness probe contract in `test_contracts.py` |
| `app/routes/main.py` | ✅ 📋 | Page routes exercised by auth contract tests; tab rendering and navigation are 📋 (§12 frontend smoke test) |
| `app/routes/mnemonics.py` | ✅ | `test_mnemonics_api.py` — full CRUD, filter, uppercase, 404, 409 |
| `app/routes/phase3.py` | ✅ 📌 | All four 503 responses in `test_contracts.py`; full UI is 📋 (§12 Phase 3 — requires UNIDATA_CONN_STR) |
| `app/routes/replay.py` | ✅ | `test_replay_api.py` — fetch, trigger, history, DB persistence |
| `app/routes/resources.py` | ✅ | `test_resources_api.py` — list, cn-enabled, annotate, annotations list |
| `app/routes/schema_browser.py` | ✅ | `test_schema_browser_api.py` — types list, type detail, resource-schema, validate |
| `config.py` | 📌 | CONSOLE_KEY, env-var wiring exercised by auth contract tests |
| `run.py` | 🔧 | Flask `app.run()` entry point — no runtime logic to test |

---

## JavaScript (`console/static/js/`)

JavaScript is not unit-testable in the current test setup (no Jest/browser harness). All JS files are covered by **📌 contract-pinned** API shape tests (the JS only works if the API responds correctly) and **📋 manual procedure** (§12 Console Smoke Test in `docs/e2e-testing.md`).

| File | Contract-pinned via | Manual procedure |
|---|---|---|
| `bus_monitor.js` | `test_bus_api.py` shapes | §12 Bus Monitor — SSE stream dot, pause/resume, export |
| `cn_monitor.js` | `test_cn_monitor_api.py` shapes | §12 CN Monitor — health dot, notification list, diagnostics diff, audit log |
| `colleague_query.js` | `test_contracts.py` phase3 503 shape | §12 Phase 3 setup guide renders correctly |
| `errors.js` | `test_errors_api.py` — list/spikes/flush shapes | §12 Errors tab — tile counts, spike chart, CSV download |
| `field_diff.js` | `test_contracts.py` phase3 503 shape | §12 Phase 3 setup guide renders correctly |
| `graphql_builder.js` | `test_graphql_api.py` — schema, execute, saved query shapes | §12 GraphQL Builder — schema tree, query run, save/delete |
| `health.js` | `test_health.py` — full health response key contract | §12 Health tab — token badge, queue bar, resource rows |
| `mnemonics.js` | `test_mnemonics_api.py` shapes | §12 Mnemonics tab — list, search, create, edit, delete |
| `replay.js` | `test_replay_api.py` shapes | §12 Replay tab — fetch message, trigger, history |
| `resources.js` | `test_resources_api.py` shapes | §12 Resources tab — list renders, annotation modal saves |
| `schema_browser.js` | `test_schema_browser_api.py` shapes | §12 Schema Browser — type list, field table, validator |

---

## HTML Templates (`console/app/templates/`)

All templates are **🔧 compile-verified** by Flask's Jinja2 template engine (syntax errors surface on first render) plus **📋 manual procedure** for layout and interaction. Route-render is also exercised by auth and health contract tests.

| File | Additional coverage |
|---|---|
| `base.html` | 📌 Navigation tabs rendered in page-route tests |
| `login.html` | ✅ Auth contract tests — wrong key shows error, correct key redirects |
| `bus_monitor.html` | 📋 §12 Bus Monitor |
| `cn_monitor.html` | ✅ 📋 | Auth contract test renders page; setup guide + live UI are 📋 §12 CN Monitor |
| `colleague_query.html` | 📋 §12 Phase 3 (setup guide path + configured path) |
| `errors.html` | 📋 §12 Errors tab |
| `field_diff.html` | 📋 §12 Phase 3 |
| `graphql.html` | 📋 §12 GraphQL Builder |
| `health.html` | 📋 §12 Health tab |
| `mnemonics.html` | 📋 §12 Mnemonics tab |
| `relay.html` | 📋 §12 Replay tab |
| `resources.html` | 📋 §12 Resources tab |
| `schema_browser.html` | 📋 §12 Schema Browser |

---

## C# CNM Service (`cnm/src/`)

### Application Layer

| File | Category | Coverage reference |
|---|---|---|
| `GetAboutQuery.cs` | ✅ | `GetAboutHandlerTests.cs` |
| `GetAuditLogQuery.cs` | ✅ | `GetAuditLogHandlerTests.cs` |
| `GetChangeNotification*.cs` (3 files) | ✅ | `GetChangeNotification*HandlerTests.cs` |
| `GetParagraphQuery.cs` | ✅ | `GetParagraphHandlerTests.cs` |
| `GetSubscriptionPublishingDiagnosticQuery.cs` | ✅ | `GetSubscriptionPublishingDiagnosticHandlerTests.cs` |
| `GetResourcesQuery.cs` | ✅ | `GetResourcesHandlerTests.cs` |
| `ServiceRegistration.cs` | 🔧 | DI registration — compiler catches type errors |

### API Layer

| File | Category | Coverage reference |
|---|---|---|
| `Program.cs` | 🔧 | Startup wiring — `CnmWebApplicationFactory` exercises the full host in tests |
| `Controllers/*.cs` (7 files) | ✅ | `*EndpointTests.cs` integration tests via `WebApplicationFactory` |
| `Services/CurrentUserService.cs` | ✅ | `MeEndpointTests.cs` |
| `DevAuth/DevAuthHandler.cs` | ✅ | All endpoint tests run through dev auth handler |

### Infrastructure Layer

| File | Category | Coverage reference |
|---|---|---|
| `ChangeNotificationRepository.cs` | 📌 | `ChangeNotificationRepositoryStubTests.cs` — §0.2 stub behavior locked; see inline doc for when to replace with real impl |
| `ColleagueAboutRepository.cs` | ✅ | `ColleagueWebApiContractTests.cs` |
| `ResourceRepository.cs` | ✅ | `ResourceRepositoryTests.cs` |
| `AuditRepository.cs` | ✅ | `AuditRepositoryTests.cs` |
| `FileAuditRepository.cs` | ✅ | `FileAuditRepositoryTests.cs` |
| `CnmDbContext.cs` | ✅ | `AuditRepositoryTests.cs` uses EF InMemory provider |
| `Persistence/Configurations/*.cs` | 🔧 | EF Fluent API config — compiler + EF model validation |
| `Health/*.cs` (3 files) | ✅ | `HealthDeepEndpointTests.cs` + `HealthEndpointTests.cs` |
| `Colleague/WebApi/IColleagueWebApiClient.cs` | 🔧 | Interface — no runtime behavior; implementations tested via repos |
| `Colleague/WebApi/*Options.cs` (3 files) | 🔧 | POCOs — compiler-verified |
| `Colleague/WebApi/*Response.cs` (2 files) | 🔧 | DTOs — compiler-verified |
| `Colleague/WebApi/EventConfigs/*.cs` (2 files) | 🔧 | DTOs — compiler-verified |
| `Colleague/Das/DasOptions.cs` | 🔧 | POCO — compiler-verified |
| `ServiceRegistration.cs` | 🔧 | DI registration |

### Contracts Layer

All 9 files in `cnm/src/EthosCn.Contracts/` are **🔧 compile-verified** — pure record/DTO types with no runtime behavior. Shape is indirectly verified by handler and endpoint tests that serialize/deserialize them.

### Domain Layer

| File | Category |
|---|---|
| `Entities/*.cs` (3 files) | 🔧 Pure domain objects; EF mapping verified by persistence tests |
| `Enums/*.cs` (3 files) | 🔧 Enum values — compiler-verified |

---

## Infrastructure & Configuration

| File | Category | Notes |
|---|---|---|
| `console/config.py` | 📌 | Env var wiring tested via auth and contract tests |
| `console/run.py` | 🔧 | Entry point |
| `console/Dockerfile` | 📋 | §7 Dev Cluster Smoke Test in e2e-testing.md |
| `console/k8s/*.yaml` (5 files) | 📋 | §7 — liveness probe path (`/api/health/live`) is 📌 pinned in test_contracts.py |
| `console/requirements.txt` | 🔧 | pip install — no testable behavior |
| `console/pytest.ini` | 🔧 | pytest config |
| `cnm/docker-compose.yml` | 📋 | §1 Local Dev Setup in e2e-testing.md |
| `ethos-console.sln` | 🔧 | Solution file |
| `start-local.ps1` | 📋 | §1 Local Dev Setup |

---

## Coverage Gaps (Accepted)

| Item | Reason not tested | Mitigation |
|---|---|---|
| `BusMonitor` daemon thread loop | Threading + blocking I/O; cannot test without live Ethos | Pure-logic methods are 100% unit-tested; thread behavior is 📋 §12 Bus Monitor SSE dot |
| `bus.py /stream` SSE endpoint | Streaming requires a real WSGI server (not Flask test client) | Bus logic tested via `test_bus_api.py`; stream verified by 📋 §12 |
| Phase 3 configured path | Requires UNIDATA ODBC driver and DSN | 503 path fully tested; configured stub returns valid shape |
| JS behavior | No browser/Jest harness in this project | API shape contracts ensure JS receives correct data; 📋 manual test covers rendering |

---

## Running the Full Suite

```bash
# Python (204 tests)
cd console && python -m pytest tests/ -v

# C# (22 tests)
cd cnm && dotnet test
```

Manual procedures: see `docs/e2e-testing.md` §12 for the full console smoke test checklist.

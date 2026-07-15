# Ethos Dev Console — End-to-End Testing Guide

**Audience:** Developers and QA running the Flask console locally or in dev cluster.

The repository used to contain a separate C# CNM service. That service was folded into the console (in-process Python under `app/cn_repository.py`), so this guide is now console-only — one stack, one test suite, one smoke pass.

---

## 1. Automated tests

Pytest suite covering every API blueprint against an in-memory SQLite database. No live Ethos required.

### Prerequisites

```powershell
cd console
pip install -r requirements.txt
pip install pytest
```

### Run all tests

```powershell
pytest
```

### Run a specific module

```powershell
pytest tests/test_audit.py
pytest tests/test_cn_monitor_api.py
pytest tests/test_mock_mode.py
```

### What's covered

| Module | Scenarios |
|---|---|
| `test_audit.py`             | `write_event`, `query_events`, actor fallback, pagination, filters |
| `test_health.py`            | Liveness, full health shape, latency keys, `mock` key |
| `test_errors_api.py`        | Empty list, POST + retrieve, status filter, spikes, flush, CSV export |
| `test_resources_api.py`     | List, CN-enabled, annotations CRUD, idempotent upsert |
| `test_graphql_api.py`       | Schema 503 when unconfigured, schema with mock, saved-query CRUD, preloaded guard |
| `test_replay_api.py`        | Fetch, trigger (via ConductorClient extension), history, DB persistence |
| `test_cn_monitor_api.py`    | Health, notifications, detail/paragraph, history (audit-backed), diagnostics set-diff, push (one audit per publish), audit log |
| `test_schema_browser_api.py` | Types list, type detail (resolves field→type), introspection-empty error path, validate |
| `test_mock_mode.py`         | The three required signals (badge / header / health key), per-provider fixture characterizations, every tab returns 200 in mock mode |
| `test_mnemonics_api.py`     | CRUD, filter, uppercase, 404, 409 |
| `test_bus_*.py`             | Bus REST + monitor pure-logic methods, incl. `/start`/`/stop` and no-auto-start-on-boot regression guard |
| `test_dob_detector.py`      | PD0002124 detection engine: backward-shift HIGH case, year-boundary shift, same-zone clean records, forward-gap REVIEW, ambiguous-origin MEDIUM, elevated-risk worklist, identity scoring, institution-specific origin codes (`extra_ie_origin_values`), same-person corroboration (`_classify_self_corroboration`) |
| `test_dob_repair_api.py`    | DOB Repair CRUD: analyze (CSV + SQL fetch), status, candidates, decision (accept/reject/defer), export corrections |
| `test_dob_sql_source.py`    | SQL fetch read-only guard (rejects writes, multi-statement, `SELECT...INTO`), connection-string building, row mapping — no live SQL Server needed |
| `test_contracts.py`         | Blueprint prefixes (all 15, incl. `/api/colleague` and `/api/env`), model shapes, error envelopes, seed counts, health keys |
| `test_auth.py`              | Login gate: fail-closed when unconfigured/default `SECRET_KEY`, redirect/401 when not logged in, login/logout flow, `next` sanitization — builds its own non-`TESTING` app instance so the real gate runs (every other module gets a free pass via `current_app.testing`) |
| `test_env.py`               | List/switch environments, credential swap, cache invalidation, audit emission, non-object JSON body |
| `test_colleague_api.py`     | About/event-configurations/transaction/metadata, 503-unconfigured shapes, audit emission (success/failure) on the CTX transaction call |
| `test_request_utils.py`     | `get_json_body()` coerces every non-dict JSON body — falsy (`null`/`[]`/`""`/`0`/`false`) AND truthy (`42`/a string/`[1,2]`/`true`) — to `{}` |
| `characterization/test_colleague_api_client_characterization.py` | Real `ColleagueApiClient`: basic-auth header encoding, URL construction per endpoint, `_LegacyTlsAdapter` leaves cert/hostname verification intact |
| `characterization/test_unidata_client_characterization.py` | Real `UnidataClient`: `_parse_list_ids()`, connection param passthrough, `run_command`/`call_subroutine` argument marshalling (mocked `_uopy`) |

---

## 2. Liveness and health smoke

Run after starting the console with `.\console\start-local.ps1`.

**Login required.** Every curl example below except Liveness needs an
authenticated session cookie once `AUTH_USERNAME`/`AUTH_PASSWORD` are
configured (they're fail-closed by default — see the "Authentication"
subsection of §15 in `docs/console-user-guide.md`). Get a cookie jar once
and reuse it for the rest of this guide:

```powershell
curl -c cookies.txt -d "username=<user>&password=<pass>" http://localhost:5012/login
curl -b cookies.txt http://localhost:5012/api/health/
```

### Liveness

```powershell
# Always 200 — use for Uptime Kuma / k8s liveness probe
curl http://localhost:5012/api/health/live

# Full health — keys: token, queue_depth, queue_status, queue_error, latency,
# recent_errors, error_count_1h, error_status, resource_health, ethos_configured, mock
curl http://localhost:5012/api/health/
```

Expected: `{"status": "ok"}` from Liveness; the full health response is covered below.

### Full health response shape

```json
{
  "ethos_configured": true,
  "mock": false,
  "token": { "valid": true, "expires_in_minutes": 45 },
  "queue_depth": 12,
  "queue_status": "green",
  "queue_error": null,
  "latency": { "p50": 142, "p95": 380, "p99": 510, "max": 720, "sample_count": 87 },
  "recent_errors": [],
  "error_count_1h": 0,
  "error_status": "green",
  "resource_health": [
    { "resource": "persons", "hourly_rate": 43, "last_seen_seconds_ago": 5, "status": "green" }
  ]
}
```

| Field | Green | Amber | Red |
|---|---|---|---|
| `queue_status` | depth < 100 | 100–499 | ≥ 500 or error |
| `error_status` | 0 errors | 1–10 errors | > 10 errors |
| resource `status` | event within 30 min | no recent event | — |

---

## 3. API smoke (real mode)

All commands below need the `cookies.txt` session cookie from §2 — add `-b cookies.txt` to each (omitted here for brevity).

```powershell
$BASE = "http://localhost:5012"

# Ethos resources
curl $BASE/api/resources/
curl $BASE/api/resources/cn-enabled
curl $BASE/api/resources/annotations

# GraphQL — schema + preloaded saved queries
curl $BASE/api/graphql-console/schema
curl $BASE/api/graphql-console/saved

# Errors
curl $BASE/api/errors/
curl $BASE/api/errors/spikes

# Change notifications (in-process — no separate service to start)
curl $BASE/api/cn/health
curl $BASE/api/cn/notifications
curl "$BASE/api/cn/notifications?resource=persons"
curl $BASE/api/cn/diagnostics
curl $BASE/api/cn/audit-log

# DOB Repair
curl $BASE/api/dob-repair/status
curl -F "csv_file=@console/tests/fixtures/dob_sample_persons.csv" $BASE/api/dob-repair/analyze
```

The CN reads against Colleague Web API are intentionally stubbed pending endpoint confirmation, so in real mode `/api/cn/notifications` is expected to return an empty list. Run in mock mode (`CONSOLE_MOCK_MODE=true`) to see realistic CN data.

Expected after the DOB Repair analyze call: `summary.high == 2`, `summary.medium == 1`, `summary.review == 1` against the bundled fixture.

---

## 4. Frontend smoke

Open `http://localhost:5012` and verify:

- [ ] Unauthenticated request redirects to `/login`; wrong credentials show an error; correct credentials land on Bus Monitor
- [ ] Bus Monitor loads **stopped** by default (no auto-poll); clicking **Start Monitor** connects the SSE stream (status dot animates) and the button turns into **Stop Monitor**
- [ ] Resources page loads, table renders (empty without a configured `ETHOS_ENV_n`)
- [ ] GraphQL page loads, saved query chips appear (5 preloaded)
- [ ] Health page loads without JS console errors
- [ ] Error Log page loads, metric tiles show `0` or `—`
- [ ] DOB Repair page loads; uploading the bundled sample CSV populates the summary tiles and review queue; Export Corrections CSV downloads after accepting a HIGH candidate
- [ ] "View all →" link from Health navigates to `/errors`
- [ ] Mnemonics page loads, table renders
- [ ] Change Notifications tab loads — no "configure CNM" setup card
- [ ] Schema Browser loads, types list populates after "Load Schema"
- [ ] Field Diff page loads; **known limitation** — Compare always returns empty Matched/EEDM-only/UniData-only sections (`app/routes/phase3.py`'s field-diff handler is not yet implemented), so an empty result here is expected, not a bug
- [ ] Sign out redirects to `/login`; the app is gated again

### Caustic-operation banners

See `docs/warning.md` §1 for rationale.

- [ ] **Replay** tab shows the red caustic-operation banner
- [ ] **Change Notifications → Push** shows the red caustic banner (when an `ETHOS_ENV_n` block is configured)
- [ ] **Colleague API** shows the red caustic banner (when `COLLEAGUE_WEB_API_URL` is set)
- [ ] **Direct Query** shows the red caustic banner (when `UNIDATA_HOST` is set)
- [ ] Caustic banners appear in **both** development and production — they warn about the action, not the environment

### Confirmation dialogs

Every state-changing action opens a confirmation dialog (`static/js/confirm.js`).
Cancel / Esc / backdrop-click must abort the action with no request sent.

Type-to-confirm (caustic — confirm button stays disabled until the exact target is typed):

- [ ] **Replay → Replay to Conductor** — type the workflow name
- [ ] **CN → Push → Publish** — type the resource name
- [ ] **Colleague API → Call** — type the transaction ID
- [ ] **Direct Query → Run** — type the command verb (e.g. `LIST`)
- [ ] **Direct Query → Subroutine → Call** — type the subroutine name

Plain confirm (data changes; deletes get a red confirm button):

- [ ] Mnemonic create / update / **delete**
- [ ] Resource annotation save
- [ ] GraphQL saved-query save / **delete**
- [ ] Bus filter preset save / **delete**
- [ ] Bus **Clear** feed
- [ ] Error log **Flush in-memory**
- [ ] Ethos environment switch (nav-bar dropdown)

Not gated (pure reads / cache refreshes — confirm dialog must NOT appear):

- [ ] Resource list refresh, schema-cache reload, read-only GraphQL query run, bus pause/resume

---

## 5. CONSOLE_MOCK_MODE smoke

See `docs/warning.md` §5. Enable with `CONSOLE_MOCK_MODE=true` in `.env` and restart.

- [ ] Nav bar shows an amber **MOCK** badge next to the environment badge
- [ ] Every API response carries header `X-Mock-Mode: true` (`curl -i http://localhost:5012/api/resources/`)
- [ ] `GET /api/health/` returns body with `"mock": true`
- [ ] Every tab loads with content — no "off" badges, no empty "no env configured" states
- [ ] Resources tab populates with ~22 mock resources
- [ ] GraphQL tab introspection shows `persons16`, `sections16`, etc.
- [ ] Schema Browser left list populates; clicking `persons16` shows fields
- [ ] CN Monitor → Monitor shows mock notifications
- [ ] CN Monitor → Push runs, echoes the payload, no real Ethos call
- [ ] Replay → Fetch by ID returns a mock message; Replay to Conductor returns a `mock-<workflow>-<ts>` id
- [ ] Colleague API → Call returns a mock CTX result echoing the input
- [ ] Direct Query → Run for `LIST PERSON SAMPLE 3` returns a mock table
- [ ] Direct Query → Subroutine Call returns mock arg values
- [ ] Disable `CONSOLE_MOCK_MODE`, restart, and verify the MOCK badge, `X-Mock-Mode` header, and `"mock": true` health key all disappear

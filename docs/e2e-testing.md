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
| `test_bus_*.py`             | Bus REST + monitor pure-logic methods |
| `test_contracts.py`         | Blueprint prefixes, model shapes, error envelopes, seed counts, health keys |
| `test_auth.py`              | check_key, `api_auth_required`, `_auth_enabled` |

---

## 2. Liveness and health smoke

After `.\console\start-local.ps1`:

```powershell
# Always 200 — use for Uptime Kuma / k8s liveness probe
curl http://localhost:5012/api/health/live

# Full health — keys: token, queue_depth, queue_status, queue_error, latency,
# recent_errors, error_count_1h, error_status, resource_health, ethos_configured, mock
curl http://localhost:5012/api/health/
```

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
```

The CN reads against Colleague Web API are intentionally stubbed pending endpoint confirmation, so in real mode `/api/cn/notifications` is expected to return an empty list. Run in mock mode (`CONSOLE_MOCK_MODE=true`) to see realistic CN data.

---

## 4. Frontend smoke

Open `http://localhost:5012` and verify:

- [ ] Bus Monitor loads, SSE stream connects (status dot animates)
- [ ] Resources page loads, table renders (empty without a configured `ETHOS_ENV_n`)
- [ ] GraphQL page loads, saved query chips appear (5 preloaded)
- [ ] Health page loads without JS console errors
- [ ] Error Log page loads, metric tiles show `0` or `—`
- [ ] "View all →" link from Health navigates to `/errors`
- [ ] Mnemonics page loads, table renders
- [ ] Change Notifications tab loads — no "configure CNM" setup card
- [ ] Schema Browser loads, types list populates after "Load Schema"

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

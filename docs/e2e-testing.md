# Change Notification Manager — End-to-End Testing Guide

**Audience:** Developers and QA running CNM against a real or local environment  
**Version:** v1  
**Status:** Draft — scenarios marked *[Requires Colleague]* cannot be executed until the dev Colleague integration is live.

---

## 1. Test Environment Overview

CNM has four levels of testing. Each has different prerequisites and a different purpose.

| Level | When to run | Requires |
|---|---|---|
| **Automated unit** | Every build, CI | Nothing — pure in-memory |
| **Automated integration (API)** | Every build, CI | Nothing — WebApplicationFactory, no DB |
| **Automated contract** | When `COLLEAGUE_INTEGRATION_TESTS=true` | VPN + dev Colleague credentials |
| **Manual E2E** | Before a release or after infrastructure changes | Full local or dev-cluster stack |

---

## 2. Prerequisites by Scenario

### Local stack (no Colleague)

Required to run manual E2E without Colleague connectivity:

- [ ] .NET 8 SDK installed
- [ ] Node 20+ installed
- [ ] Repository cloned and on the correct branch
- [ ] `.\cnm\start-local.ps1 -ForceDeps` run at least once (installs npm packages)
- [ ] No `.env` required — dev auth bypass and file audit are active

### Local stack (with Colleague)

Additional requirements for Colleague-connected testing:

- [ ] VPN connected to Doane network
- [ ] `.env` at repo root with `ColleagueWebApi__BaseUrl`, `__Username`, `__Password` populated
- [ ] `ConnectionStrings__CnmDb` pointing to a local or shared SQL Server instance
- [ ] EF migrations applied: `dotnet ef database update --project cnm\src\EthosCn.Infrastructure --startup-project cnm\src\EthosCn.Api`

### Dev cluster

- [ ] `kubectl` configured for the dev cluster
- [ ] Kubernetes secrets present: `cnm-colleague-creds`, `cnm-db-conn`
- [ ] Ingress accessible at `du-int.doane.edu/dev/cnm`

---

## 3. Running the Automated Test Suite

### All tests (unit + API integration)

```
dotnet test ethos-console.sln
```

### With coverage report

```
dotnet test ethos-console.sln --collect:"XPlat Code Coverage"
```

### Specific project

```
dotnet test cnm\tests\EthosCn.Application.Tests\EthosCn.Application.Tests.csproj
dotnet test cnm\tests\EthosCn.Api.Tests\EthosCn.Api.Tests.csproj
dotnet test cnm\tests\EthosCn.Infrastructure.Tests\EthosCn.Infrastructure.Tests.csproj
```

### Colleague contract tests (integration-only)

These are skipped by default. Set the environment variable before running:

```powershell
$env:COLLEAGUE_INTEGRATION_TESTS = "true"
dotnet test cnm\tests\EthosCn.Infrastructure.Tests\EthosCn.Infrastructure.Tests.csproj
```

> These require VPN + dev Colleague credentials in `.env`. Do not run against prod.

---

## 4. Post-Startup Smoke Test Checklist

Run these immediately after starting the stack, before doing anything else.

```powershell
.\cnm\start-local.ps1
```

Wait for both the API and Vite to report ready, then verify:

### API smoke tests

```powershell
# Shallow health — should return 200 with status: ok
curl http://localhost:9501/api/v1/health

# Deep health — expect 200 (healthy) or 503 (degraded if Colleague not configured)
curl http://localhost:9501/api/v1/health/deep

# Resources — should return array of 41 items
curl http://localhost:9501/api/v1/resources

# Change notifications — should return empty array [] until Colleague connected
curl http://localhost:9501/api/v1/change-notifications

# Diagnostics — should return diff with totalSubscribed: 41
curl http://localhost:9501/api/v1/diagnostics/subscription-publishing

# Me endpoint — should return dev-user in local dev
curl http://localhost:9501/api/v1/me

# About — should return { version: null } until Colleague connected
curl http://localhost:9501/api/v1/about
```

### Frontend smoke tests

Open `http://rmw01tfinner.doane.local:9500` (or `http://localhost:9500`) and verify:

- [ ] Page loads without a blank screen or console errors
- [ ] Change Notifications nav item is visible and active by default
- [ ] Change Notifications list loads (empty table is expected without Colleague)
- [ ] Diagnostics nav item is visible and navigates to the diagnostics page
- [ ] Diagnostics page shows all 41 resources in the "Subscribed but NOT published" section
- [ ] Audit Log nav item is visible and navigates to the audit log page
- [ ] Audit Log shows empty table (no entries yet)
- [ ] Header shows user display name (`Dev User (local)` in local dev)

---

## 5. Manual E2E Scenarios

### 5.1 Authentication and Access

| Scenario | Steps | Expected |
|---|---|---|
| Sign in (non-local) | Navigate to app URL → redirected to AD → sign in | Lands on Change Notifications list |
| Sign out | Click Sign out in header | Redirected to sign-in screen |
| Direct URL without auth | Navigate to any route while signed out | Redirected to sign-in screen |
| AD group without CNM access | Sign in with account not in CNM AD group | 403 / access denied page |

> *[Requires AD configuration]* Not testable in local dev mode.

---

### 5.2 Change Notifications List

| Scenario | Steps | Expected |
|---|---|---|
| List loads | Navigate to `/change-notifications` | Table appears, ~240 rows *[Requires Colleague]* |
| Filter by resource | Enter `persons` in resource filter | Only rows matching `persons` shown |
| Filter by status | Select `Enabled` in status filter | Only enabled notifications shown |
| Clear filter | Clear filter inputs | All rows returned |
| Click a row | Click any notification row | Navigates to detail view |
| Namespace badges | Inspect rows for `x-dp-*` and `d45-*` resources | Appropriate namespace badge visible |

> *[Requires Colleague]* Row count and real status values require Colleague integration. Without it, list is empty and status shows `Unknown`.

---

### 5.3 Change Notification Detail

| Scenario | Steps | Expected |
|---|---|---|
| Detail loads | Click a notification in the list | Detail view shows resource name, status, process code |
| Has paragraph | Open a notification with a paragraph code | Paragraph tab is visible |
| No paragraph | Open a notification without a paragraph code | Paragraph tab hidden or shows "None" |
| Edit button disabled | Click the Edit button | Button is non-interactive; no action taken |
| Enable button disabled | Click Enable | Button is non-interactive |
| Disable button disabled | Click Disable | Button is non-interactive |
| Delete button disabled | Click Delete | Button is non-interactive |
| History tab | Click History tab | Shows audit entries for this notification (empty until actions taken) |
| Back navigation | Click back or use browser back | Returns to list at same scroll position |

> *[Requires Colleague]* Detail data requires Colleague integration.

---

### 5.4 Paragraph Viewer

| Scenario | Steps | Expected |
|---|---|---|
| View paragraph | Open a notification with a paragraph code → click Paragraph tab | Envision source code displayed in a read-only code block |
| Audit written | View a paragraph | New entry appears in Audit Log with action `ViewParagraph` |
| No paragraph | Open notification without paragraph code | Paragraph tab shows "No paragraph configured" or is hidden |

> *[Requires Colleague + DAS/SQL integration]* Paragraph source retrieval not available until §0.1 pre-work wires the data access path.

---

### 5.5 Diagnostics View

| Scenario | Steps | Expected |
|---|---|---|
| Page loads | Navigate to `/diagnostics` | Three sections visible: red, yellow, green |
| Totals correct | Check header | `totalSubscribed` = 41 |
| Without Colleague | View without Colleague connected | All 41 appear in "subscribed but not published" (red); other sections empty |
| With Colleague *[Requires Colleague]* | View with Colleague connected | Sections populate with real data; most standard EEDM resources move to aligned (green) |
| Vendor resources | Check `d45-*` resources | Should appear in "subscribed but not published" — expected, they are Ethos cloud-proxied |
| Namespace badges | Inspect resource list | `d45-` resources show "vendor" badge, `x-dp-` show "institution" badge |

---

### 5.6 Audit Log

| Scenario | Steps | Expected |
|---|---|---|
| Log loads | Navigate to `/audit` | Table appears (empty initially) |
| Actions generate entries | View change notifications list, then open a detail | New `View` entries appear in audit log |
| Paragraph view logged | View a paragraph | `ViewParagraph` entry with paragraph code as target identifier |
| Pagination | Generate >50 entries, navigate to page 2 | Page 2 shows older entries |
| Filter by user | Enter `dev-user` in user filter | Only entries from that user shown |
| Filter by target | Enter a notification ID | Only entries for that notification shown |
| Date range filter | Set from/to date range | Only entries within range returned |

---

### 5.7 Health Checks

| Scenario | Steps | Expected |
|---|---|---|
| Shallow always returns 200 | `curl /api/v1/health` | `{ "status": "ok", ... }` — even if DB/Colleague down |
| Deep healthy | All dependencies up | 200, all three checks `healthy` |
| Deep without DB | No `ConnectionStrings__CnmDb` set | 503, `database` check `unhealthy` |
| Deep without Colleague | No Colleague config / unreachable | 503, `colleague-api` check `degraded`; other checks unaffected |
| Deep response shape | Inspect JSON | Keys: `status`, `total_duration_ms`, `checks` with `database`, `colleague-api`, `resources-seeded` |

---

### 5.8 Write Endpoints Return 501

Verify all v1.5+ write paths return `501 Not Implemented`:

```powershell
# These should all return 501
curl -X POST   http://localhost:9501/api/v1/change-notifications/any/enable
curl -X POST   http://localhost:9501/api/v1/change-notifications/any/disable
curl -X POST   http://localhost:9501/api/v1/change-notifications/bulk/status
curl -X PUT    http://localhost:9501/api/v1/change-notifications/any -d '{}'
curl -X POST   http://localhost:9501/api/v1/change-notifications -d '{}'
curl -X DELETE http://localhost:9501/api/v1/change-notifications/any
```

Each should return: `{ "error": "Not implemented in v1.", "code": "NOT_IMPLEMENTED" }`

---

## 6. Colleague Contract Test Scenarios

Run with `COLLEAGUE_INTEGRATION_TESTS=true`. These should be executed during §0.2 pre-work and again after any Colleague Web API upgrade.

| Test | What to verify |
|---|---|
| `GET /api/about` | Returns a non-null version string; field name matches `ColleagueAboutResponse.ProductVersion` |
| `GET /api/event-configurations` | Returns non-empty list; each item has `Name` and `Status`; status values are expected strings |
| Status values | Confirm exact strings (e.g. `"Enabled"` vs `"enabled"`) — update `EventConfigurationResponse` if they differ |
| `GET /api/configuration/ems/{configId}` | Returns `ResourceMap` with entries having `ResourceName`, `UrlPath`, `BusinessProcess`; confirm field names |
| EMS resource count | `ResourceMap` should contain ~240 entries |
| Cross-reference | Resources in `event-configurations` that match our subscription list should appear in the `Aligned` section of the diagnostic |

**After completing §0.2:** Update the `NotImplementedException` stubs in `ColleagueWebApiContractTests.cs` with real assertions and confirm all pass before closing out the pre-work.

---

## 7. Dev Cluster Smoke Test (Post-Deployment)

After deploying to the dev k8s cluster via `kubectl apply -f k8s\`:

```powershell
# Confirm pods are running
kubectl get pods -n cnm-dev

# Tail API logs for startup errors
kubectl logs -f deployment/cnm-api -n cnm-dev

# Port-forward and run smoke tests
kubectl port-forward svc/cnm-api 9501:8080 -n cnm-dev

# Then run the API smoke tests from §4 against localhost:9501
```

Verify via ingress (`du-int.doane.edu/dev/cnm`) that the frontend loads and proxies correctly to the API.

---

## 8. Regression Checklist

Run before any release or after a significant code change:

- [ ] All automated tests pass: `dotnet test ethos-console.sln`
- [ ] Shallow health returns 200
- [ ] Deep health returns expected shape with all three check keys
- [ ] Resources endpoint returns exactly 41 items
- [ ] Diagnostics endpoint returns `totalSubscribed: 41`
- [ ] All six write endpoints return 501
- [ ] Frontend loads without console errors
- [ ] Diagnostics page renders three sections
- [ ] Audit log records a `View` entry after navigating the change notifications list
- [ ] `.hub-logs/audit.txt` is being written in local dev

---

## 9. What Is Not Testable Without Colleague

These scenarios require a live connection to the dev Colleague Web API and cannot be covered by the automated suite:

| Gap | Blocked by | Resolution |
|---|---|---|
| Real change notification list | Colleague integration not wired | Complete §0.2; implement `ChangeNotificationRepository` |
| Real status values (Enabled/Disabled) | Same | Same |
| Paragraph source display | DAS/SQL not wired | Complete §0.1; implement paragraph access path |
| Diagnostics "aligned" section populated | Colleague returns empty list | Same as change notification list |
| `GET /api/about` returning real version | Colleague integration | Same |
| Enable/disable operations | v1.5 write path | v1.5 milestone |

---

## 10. Interpreting the Audit File in Local Dev

Audit entries go to `.hub-logs/audit.txt` when running locally. Each line is one entry:

```
[2025-05-17 14:30:00Z] View     | ChangeNotification       | (list)     | dev-user  | 127.0.0.1  | Success
[2025-05-17 14:30:05Z] View     | ChangeNotification       | cn-001     | dev-user  | 127.0.0.1  | Success
[2025-05-17 14:30:12Z] ViewParagraph | Paragraph           | ETHOS.PARA | dev-user  | 127.0.0.1  | Success
```

Columns: `[timestamp] action | targetType | targetIdentifier | userId | sourceIp | outcome`

The file is wiped on each `cnm\start-local.ps1` run (API log is wiped; audit file is append-only and persists across restarts).

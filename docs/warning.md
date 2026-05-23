# Ethos Dev Console — Operational Warnings

**Audience:** Anyone running or deploying the Ethos Dev Console.
**Purpose:** Flag the places in this console that can cause real-world,
hard-to-undo effects, and separate genuine bugs from expected
local-development behaviour.

The console itself flags caustic actions inline (see section 1). This file is
the reference for the dev-vs-production triage that the console does **not**
surface in the UI (see section 2).

---

## 1. Caustic operations — actions with real side effects

Five actions in this console reach outside the console's own database and
cause effects that **cannot be undone from the console**. Each one carries a
red warning banner on its tab (see `app/templates/_macros.html →
caustic_banner`) **and** requires **type-to-confirm** before it runs — the
operator must type the exact target (workflow name, resource, transaction ID,
command verb, or subroutine name) into the dialog. Both signals show in **every
environment on purpose** — a caustic action is most dangerous in production, so
the warning is not dev-only.

| Tab | Action | What it does | Blast radius |
|---|---|---|---|
| **Replay** | "Replay to Conductor" | `POST {conductor_url}/api/workflow/{name}` — starts a live Conductor workflow run. | The workflow runs its full pipeline: Salesforce upserts, Colleague writes, emails/notifications. A bad payload or wrong Conductor URL pushes bad data downstream. |
| **Change Notifications → Push** | "Publish Change Notifications" | `ethos.publish_notification()` — posts real change notifications onto the Ethos integration bus. | **Widest blast radius in the console.** *Every* subscriber for that resource — every Conductor workflow, every downstream consumer — receives and acts on the notification. No dry-run, no recall. |
| **Colleague API** | "Call" (CTX Transaction Caller) | `POST {colleague_web_api}/api/transactions/{id}` — runs an ENVISION process by name. | Read processes (`GET.*`) are safe. Write processes (`SAVE.*`, `UPDATE.*`, `DELETE.*`) mutate Colleague data immediately, with no undo. |
| **Direct Query** | "Run" (UniQuery / TCL statement) | `uopy.Command(statement)` — runs an arbitrary statement against Colleague/UniData. | Read verbs (`LIST`, `SELECT`, `COUNT`) are safe. Write verbs (`DELETE`, `CLEAR.FILE`, …) change data immediately. UniData has **no transaction rollback**. |
| **Direct Query** | "Call" (ENVISION Subroutine Caller) | `uopy.Subroutine(name)` — calls an arbitrary Colleague subroutine. | A subroutine can read or write anything; the console cannot tell which. No rollback. |

### Before running a caustic action

1. **Confirm the target environment.** Check the env badge in the nav bar and,
   for Ethos, the environment dropdown. The console will happily publish to
   production if that is the key it holds.
2. **Confirm the payload.** Resource name, operation, and GUIDs for Push;
   workflow name and JSON for Replay; transaction ID for Colleague.
3. **Prefer a non-production target** for anything exploratory.
4. **Replay/Push fan out.** One click can trigger dozens of downstream
   workflow executions. Treat batch GUID lists with extra care.

### Non-caustic by comparison

GraphQL queries, schema introspection, and the Schema Browser validator are
read-only against Ethos. Resource annotations, mnemonic edits, saved queries,
and bus filter presets write only to the console's **local** SQLite/Postgres
database.

### Confirmation dialogs

**Every state-changing action is gated by a confirmation dialog** (shared helper
`static/js/confirm.js`):

- **Caustic actions** (the five above) use **type-to-confirm** — the confirm
  button stays disabled until the operator types the exact target.
- **Local data changes** (create/update/delete of mnemonics, annotations, saved
  queries, presets; error-log flush; bus-feed clear; Ethos environment switch)
  use a plain confirm dialog; deletes get a red confirm button.
- Pure reads and cache refreshes (resource refresh, schema-cache invalidation,
  read-only GraphQL queries, bus pause/resume) are **not** gated — confirmations
  on no-consequence actions only train operators to click through.

---

## 2. Local development vs. production

Separately-hosted services are usually unreachable from a developer
workstation. The errors below are *expected in local dev* and are **not
console bugs**:

| Symptom | Cause | Not a bug because… |
|---|---|---|
| Empty Notifications / Diagnostics on the **CN Monitor** tab in non-mock mode | The in-process Colleague change-notification reader is intentionally stubbed pending endpoint confirmation. | Same TODO state the previous C# CNM service was in — the data layer is awaiting Colleague Web API endpoint inventory. Mock mode shows realistic CN data while the real path is wired up. |
| `Connection aborted` / `ConnectionResetError 10054` on the **Colleague API** tab | The Colleague Web API host is not reachable (no VPN, firewall, or the host genuinely reset the connection). | Network reachability is an environment fact, not console logic. Connect to the Doane network / VPN, or test from a host that can reach it. |
| `401 Unauthorized` from `…/api/available-resources` (Resources tab, Field Diff resource list) | The Ethos **API key in use lacks scope** for the `available-resources` endpoint. The key may be valid for other calls and still be denied this one. | Endpoint-level authorization is granted in Ethos, not in this code. Use a key whose application has access to `available-resources`. |
| Replay cannot reach Conductor | `CONDUCTOR_URL` points at a host not reachable from the workstation. | Same as above — reachability is environmental. |

**Rule of thumb:** if the error text is a *transport* error (refused, reset,
timeout, DNS) or an *authorization* error (401/403) against an **external**
host, it is almost always environment/credentials — move to an environment that
can reach the service with a properly-scoped credential. If the error is a
*shape* error (missing field, wrong type, 500 from our own routes, a Python
traceback), that is a console bug worth filing.

---

## 3. Triage of issues observed in the 2026-05-22 test session

| Reported symptom | Verdict | Detail |
|---|---|---|
| Schema Browser: `type/advancementAppointments0` → `Type not found` | **Bug — fixed** | The type list shows GraphQL *Query field* names, but `get_type` looked up *type definitions* by that name. A field name is not always a type name. `get_type` now resolves a field name to its return type before giving up. Introspection that returns no schema now reports an honest "introspection unavailable" error instead of a misleading "type not found". |
| EEDM Resource Coverage Map: "No resources — check the configured Ethos environment" | **Environment + bug — fixed (UI)** | Root cause is the `available-resources` 401 below. Separately, the Resources page swallowed the real error and always showed a generic "check your env" text. It now surfaces the actual error (e.g. the 401) in the status line and table. |
| Field Diff resource list: `401 … available-resources` | **Environment** | The Ethos key lacks scope for `available-resources`. The Field Diff resource list now shows the real error instead of rendering blank. |
| Colleague Web API: `ConnectionResetError 10054` | **Environment** | Colleague Web API host unreachable from the test workstation. Needs network/VPN access. No console change. |
| CN tab shows empty notifications / diagnostics in non-mock mode | **Implementation** | The CN data layer (`app/cn_repository.py`) is stubbed pending Colleague Web API endpoint confirmation. Run in mock mode (`CONSOLE_MOCK_MODE=true`) to see realistic CN data while the real path is being wired up. |

---

## 4. Are the mnemonics hard-coded?

**Partly.** The ~30 starter mnemonics live in a hard-coded `SEED_MNEMONICS`
list in `app/database.py`. On startup `seed_mnemonics()` inserts any that are
not already present. After that first seed the mnemonics are **database-backed
and fully editable** through the Mnemonics tab / `/api/mnemonics` (create,
update, delete).

Two consequences worth knowing:

- Seeding is **insert-only and idempotent** — it never updates an existing
  row. Editing `SEED_MNEMONICS` later will **not** change mnemonics already in
  the database; only a fresh database picks up the new seed.
- The seed list is a **productization note** for peer-institution reuse: the
  mnemonic→EEDM-resource mappings are standard Colleague, but any
  Doane-specific assumptions should stay in this swappable seed, never in
  executable code.

---

## 5. `CONSOLE_MOCK_MODE` — all-or-nothing fixture mode

The console can be run with **every** upstream call returning fixture data
instead of touching a real service. Use this to develop against the UI, demo
to a peer institution, or exercise CI without credentials.

**Enable** by setting in `.env`:

```
CONSOLE_MOCK_MODE=true
```

When on:

- Every tab is exercisable. The "off" badges disappear because every feature
  flag is forced true.
- `MockEthosClient`, `MockColleagueApiClient`, `MockConductorClient`,
  `MockUnidataClient`, and `MockCnRepository` (under `app/mocks/`) replace
  the real clients at app-creation time. Shared fixtures live in
  `app/mocks/fixtures.py` and are pinned by `tests/test_mock_mode.py` so a
  shape change cannot slip through silently.
- The bus monitor sees a deterministic trickle of one mock change
  notification per poll. The Replay tab can fetch any message id and replays
  return a `mock-<workflow>-<ts>` id without calling Conductor. The CN Push
  tab "publishes" — the mock client echoes the payload and does nothing.

**Hard separation rule.** There is no hybrid path. Either every upstream is
real or every upstream is mock. A per-call "real-first, mock-on-error"
fallback is forbidden — that's the silent-mock-fallback failure mode this
project explicitly rejects.

**Three required signals** (`tests/test_mock_mode.py` pins each one):

1. **MOCK badge** in the nav bar — amber, hard to miss.
2. **`"mock": true`** in the `/api/health/` response body.
3. **`X-Mock-Mode: true`** header on every API response.

If any of those three is missing, mock mode is broken and an operator could
reasonably mistake fixture output for live data. Treat the failing test as a
P1.

**Production safety.** Never set `CONSOLE_MOCK_MODE=true` in a production
deployment; the badge / header / health flag are the operator-facing safety
net but the env flag itself is the authoritative gate. Keep it `false` (or
unset) in production secrets.

# Ethos Dev Console — Operational Warnings

**Audience:** Anyone running or deploying the Ethos Dev Console.
**Purpose:** Flag the places in this console that can cause real-world,
hard-to-undo effects, and separate genuine bugs from expected
local-development behaviour.

This file is the source of truth referenced by the **local-development banner**
shown in the app when `FLASK_ENV=development`.

---

## 1. Caustic operations — actions with real side effects

Three actions in this console reach outside the console's own database and
cause effects that **cannot be undone from the console**. Each one carries a
red warning banner in the UI (see `app/templates/_macros.html →
caustic_banner`). The banner shows in **every environment on purpose** — a
caustic action is most dangerous in production, so the warning is not dev-only.

| Tab | Action | What it does | Blast radius |
|---|---|---|---|
| **Replay** | "Replay to Conductor" | `POST {conductor_url}/api/workflow/{name}` — starts a live Conductor workflow run. | The workflow runs its full pipeline: Salesforce upserts, Colleague writes, emails/notifications. A bad payload or wrong Conductor URL pushes bad data downstream. |
| **Change Notifications → Push** | "Publish Change Notifications" | `ethos.publish_notification()` — posts real change notifications onto the Ethos integration bus. | **Widest blast radius in the console.** *Every* subscriber for that resource — every Conductor workflow, every downstream consumer — receives and acts on the notification. No dry-run, no recall. |
| **Colleague API** | "Call" (CTX Transaction Caller) | `POST {colleague_web_api}/api/transactions/{id}` — runs an ENVISION process by name. | Read processes (`GET.*`) are safe. Write processes (`SAVE.*`, `UPDATE.*`, `DELETE.*`) mutate Colleague data immediately, with no undo. |

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

GraphQL queries, schema introspection, the Schema Browser validator, resource
annotations, mnemonic edits, and saved queries either are read-only against
Ethos or write only to the console's **local** SQLite/Postgres database. They
are safe to use freely.

---

## 2. Local development vs. production

When `FLASK_ENV=development`, the console shows a dismissible banner explaining
that **separately-hosted services are usually unreachable from a developer
workstation**. The errors below are *expected in local dev* and are **not
console bugs**:

| Symptom | Cause | Not a bug because… |
|---|---|---|
| `Connection refused` / `WinError 10061` on the **CN Monitor** tab, host `localhost:5011` | The CNM service (the C# `cnm/` project) is not running locally. | The console is a thin proxy — it has nothing to serve until CNM is up. Start CNM, or point `CNM_BASE_URL` at a running instance. |
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
| EEDM Resource Coverage Map: "No resources — check ETHOS_API_KEY" | **Environment + bug — fixed (UI)** | Root cause is the `available-resources` 401 below. Separately, the Resources page swallowed the real error and always showed the generic "check ETHOS_API_KEY" text. It now surfaces the actual error (e.g. the 401) in the status line and table. |
| Field Diff resource list: `401 … available-resources` | **Environment** | The Ethos key lacks scope for `available-resources`. The Field Diff resource list now shows the real error instead of rendering blank. |
| Colleague Web API: `ConnectionResetError 10054` | **Environment** | Colleague Web API host unreachable from the test workstation. Needs network/VPN access. No console change. |
| CN tabs: `localhost:5011 … connection refused` | **Environment** | The CNM service is not running locally. Start it, or repoint `CNM_BASE_URL`. No console change. |

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

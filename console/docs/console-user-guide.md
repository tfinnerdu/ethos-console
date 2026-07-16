# Doane Ethos Dev Console — User Guide

**Audience:** Enterprise Services / Integration team  
**Application:** Ethos Dev Console (Flask, port 5012)  
**Covers:** Every tab, every control, every configuration option

---

## Table of Contents

1. [Overview](#1-overview)
2. [Getting Started](#2-getting-started)
3. [Navigation & Global UI](#3-navigation--global-ui)
4. [Bus Monitor](#4-bus-monitor)
5. [Replay](#5-replay)
6. [GraphQL](#6-graphql)
7. [Schema Browser](#7-schema-browser)
8. [Resources](#8-resources)
9. [Mnemonics](#9-mnemonics)
10. [Field Diff](#10-field-diff)
11. [Direct Query](#11-direct-query)
12. [Colleague API](#12-colleague-api)
13. [Change Notifications](#13-change-notifications)
14. [Health](#14-health)
15. [Configuration Reference](#15-configuration-reference)
16. [DOB Repair](#16-dob-repair)
17. [DoaneEdgeGate](#17-doaneedgegate)

---

## 1. Overview

The Ethos Dev Console is an internal developer tool for the Doane Enterprise Services team. It provides a single browser-based interface for monitoring, querying, and diagnosing the Ellucian Ethos integration platform — without requiring Postman, command-line tools, or direct database access.

**What it does:**

| Capability | Tab |
|---|---|
| Watch Ethos change notifications arrive in real time | Bus Monitor |
| Re-fire historical events through Conductor workflows | Replay |
| Write and execute GraphQL queries against Ethos | GraphQL |
| Browse the full EEDM resource schema | Schema Browser |
| Inspect any Ethos REST resource | Resources |
| Look up Colleague file-to-EEDM resource mappings | Mnemonics |
| Compare EEDM fields to UniData fields side by side | Field Diff |
| Run TCL/UniQuery statements directly against Colleague UniData | Direct Query |
| Call Colleague CTX transactions via the Web API | Colleague API |
| Monitor change notification configuration and subscription alignment | Change Notifications |
| Check API token status, latency, error log | Health |
| Detect and human-review PD0002124 (Instant Enrollment DOB timezone shift) | DOB Repair |

**Tab badges:** Any tab whose required environment variable is not configured shows a small muted `OFF` chip. These disappear automatically once the corresponding `.env` entry is filled in and the server is restarted.

---

## 2. Getting Started

### Prerequisites

- Python 3.11+, `pip`, a virtual environment
- `uopy==1.4.0` (optional — enables Direct Query and Field Diff)
- A valid Ethos integration API key

### Local setup

```bash
cd console
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in your values
python run.py
```

The console starts on **http://localhost:5012** by default (override with `PORT=` in `.env`).

### Authentication

The console sits behind a single shared username/password (see `app/auth.py`). Set `AUTH_USERNAME` and `AUTH_PASSWORD` in `.env` — any page loads to a **Sign in** screen first. A **Sign out** link always appears in the top nav.

**Fail-closed.** If `AUTH_USERNAME`/`AUTH_PASSWORD` are unset, or `SECRET_KEY` is still the placeholder default, the sign-in page shows "Authentication is not configured on this deployment" instead of a form, and every other page/API route is blocked too — nothing is reachable until it's configured correctly. This is a deliberate, temporary step (one shared credential, no per-user accounts); the plan is to replace it with SSO later without changing how the rest of the app is gated. See `docs/auth-gate-guide.md` for the reusable pattern this follows and exactly what would change at SSO time.

Sessions expire after `AUTH_SESSION_LIFETIME_HOURS` (default 8h). Health check endpoints (`/api/health/live`) are never gated — they have to keep working for uptime monitors and k8s probes regardless of login state.

---

## 3. Navigation & Global UI

### Top Navbar

The dark navy bar at the top of every page.

| Element | Description |
|---|---|
| **Doane Ethos Dev Console** (logo/link) | Navigates to the Bus Monitor (home page) |
| **ENV badge** | Shows the current Flask environment (`DEVELOPMENT` or `PRODUCTION`) |
| **Ethos environment dropdown** | Appears when 2+ Ethos environments are configured via `ETHOS_ENV_*` vars. Click to hot-swap credentials — switches the active API key and base URL without a restart, and resets the Bus Monitor buffer. |
| **Health** link | Quick link to the Health tab |
| **Sign out** link | Ends the session |

### Token Expiry Banner

A collapsible amber banner appears automatically across the top of the page when the active Ethos JWT token has 10 minutes or fewer remaining. It shows the exact minutes left and dismisses itself once the token refreshes (which happens automatically on the next API call). The check runs once per minute.

### Tab Bar

The dark row of tabs beneath the navbar. Each tab links to a major feature area. Tabs with an `OFF` badge require additional `.env` configuration — clicking them still works and shows a setup guide.

---

## 4. Bus Monitor

**URL:** `/`  
**Requires:** a configured Ethos environment

The Bus Monitor polls the Ethos message bus, displaying every change notification as it arrives. It is the primary real-time operational view.

**Defaults to stopped.** The console no longer auto-starts polling on boot — click **Start Monitor** to begin (it turns into a red **Stop Monitor** button once running). This avoids spamming Ethos with `/consume` requests every `BUS_POLL_INTERVAL` seconds when nobody is watching the tab. The Start/Stop state is shared across tabs/sessions (it's a server-side background thread, not per-browser) and is reflected live via the same event stream that feeds the live feed below. This is a separate control from **Pause**, which only suspends polling temporarily while leaving the background thread running.

### Summary Tiles

Four metric tiles appear across the top:

| Tile | Description |
|---|---|
| **Queue Depth** | How many unconsumed messages are currently waiting in the Ethos queue. A rising number indicates the consumer is falling behind. |
| **Events / hr (total)** | The rolling event rate across all resources since the monitor started. |
| **Active Resources** | Count of resources that have published at least one event in the current session, with a sub-label showing how many are currently silent. |
| **Events Seen (session)** | Total events consumed since the last page load or Clear. |

### Live Event Feed

The scrolling event log in the left column. Each row shows:

- **Timestamp** (UTC) when the event was consumed
- **Resource name** (e.g. `persons`, `courses`)
- **Operation** (`created`, `updated`, `deleted`)
- **GUID** of the affected record
- Error events appear in red with the error message

**Controls:**

| Button | Function |
|---|---|
| **Pause / Resume** | Freezes or resumes the live event stream. New events continue to accumulate in the buffer while paused; they appear all at once on resume. |
| **Clear** | Clears the event feed and resets session stats. Does not affect the Ethos queue. |
| **Export** | Downloads the last 100 events as a JSON file. |

### Filters & Presets

Below the feed controls:

| Control | Function |
|---|---|
| **Resource filter** (text box) | Live-filters the feed to show only events matching the typed resource name (partial match, case-insensitive). |
| **Operation dropdown** | Filters to `all`, `created`, `updated`, or `deleted` events. |
| **Bookmark icon** | Saves the current resource + operation filter combination as a named preset (prompts for a name). |
| **Presets dropdown** | Lists saved presets. Click a preset to apply it; hover to see a delete button. Presets are stored in the local SQLite database and persist across restarts. |
| **Filter status** | Shows how many events match the current filter out of total buffered. |

### Resource Activity Table

The right column. Shows aggregated stats per resource for the current session:

| Column | Description |
|---|---|
| Resource | EEDM resource name |
| Count | Total events seen this session |
| Last Seen | How many seconds ago the most recent event arrived |
| Rate | Estimated events per hour based on session duration |
| Status | `active` (event within last 30 min) or `silent` |

**Silence threshold:** A number input at the bottom of the resource table lets you set a custom silence threshold (default 30 minutes). Resources that exceed this threshold without an event are highlighted.

---

## 5. Replay

**URL:** `/replay`  
**Requires:** a configured Ethos environment + `CONDUCTOR_URL`

The Replay tab lets you re-fire a Colleague change notification through a Netflix Conductor workflow — useful for testing integration logic without generating a real Colleague change.

### Input Modes

Three tabs switch between how you load a message:

**By ID**  
Enter a numeric Ethos message ID (from the Bus Monitor event feed or a previous export). Click **Fetch** to pull the full message body from the Ethos API and load it into the preview panel.

**Paste JSON**  
Paste a raw change notification JSON payload directly. Click **Load** to validate and preview it.

**Build**  
Construct a synthetic notification by filling in:
- **Resource Name** — EEDM resource (e.g. `persons`)
- **Operation** — `created`, `updated`, or `deleted`
- **Resource GUID** — the UUID of the affected record
- **Content** — optional JSON body representing the resource payload

Click **Build** to assemble and preview the synthetic message.

### Message Preview

Once a message is loaded via any method, it is displayed as formatted JSON. The **Copy JSON** button copies the full payload to the clipboard.

### Trigger Conductor Workflow

- **Workflow Name** — the Conductor workflow definition name to invoke (e.g. `EDA_Person_Sync`)
- **Conductor URL** — pre-filled from `CONDUCTOR_URL` in `.env`, but editable per-request
- **Trigger Replay** button — POSTs the loaded message to Conductor and displays the workflow ID and status returned

### Replay History

A log of all replays triggered in the current session, showing workflow name, trigger time, the message ID or source, and outcome status.

---

## 6. GraphQL

**URL:** `/graphql`  
**Requires:** a configured Ethos environment (set `ETHOS_ENV_n_GRAPHQL_KEY` for a dedicated GraphQL key)

An interactive GraphQL query builder and executor for the Ethos GraphQL API.

### Schema Tree (left panel)

Click **Load Schema** (refresh icon) to fetch and render the EEDM GraphQL schema. Resources appear as expandable rows.

- Expand a resource to see all available fields with their types
- Check field checkboxes to automatically build a query in the editor
- Use the **Search** box to filter resources by name
- **Select All / Deselect All** buttons toggle all fields for the open resource
- If GraphQL introspection is unavailable on your Ethos instance, the panel falls back to the `available-resources` REST endpoint and shows resource names with version numbers

### Query Editor (right panel)

A free-text editor for writing or editing GraphQL queries. Pre-populated by the schema tree when you check fields. Can also be typed directly.

### Variables

A collapsible JSON editor below the main query area for supplying GraphQL variables. Click **Variables** to expand. Enter a JSON object (e.g. `{"personId": "0012345"}`).

### Executing Queries

Click **Run** (or press Ctrl+Enter) to execute the query. Results appear below the editor as formatted JSON.

- The status bar shows the HTTP status code and elapsed time
- Errors from Ethos (including GraphQL-level errors) are shown in red with the full error object

### Saved Queries

Click **Save** after writing a query to store it with a name and optional description. Saved queries are stored in the database and persist across restarts.

- **Load** a saved query by clicking its name in the saved queries list
- **Delete** a saved query with the trash icon
- Pre-loaded system queries (seeded at startup) cannot be deleted

---

## 7. Schema Browser

**URL:** `/schema-browser`  
**Requires:** a configured Ethos environment

A read-only browser for exploring the full EEDM resource schema — all field names, types, and nesting structure.

### Resource List (left panel)

All EEDM resource types from the GraphQL schema, sorted alphabetically. Use the **Search** box to filter by name.

Click any resource to expand its field tree in the main panel.

### Field Tree (right panel)

Shows all fields for the selected resource, including:
- Field name
- GraphQL type (scalar, object, list)
- Nested object expansion (click to drill into sub-fields)

The tree is lazy-loaded — sub-fields are only fetched when you expand a node.

---

## 8. Resources

**URL:** `/resources`  
**Requires:** a configured Ethos environment

A browser for the Ethos REST resource API. Explore any EEDM resource, inspect records by GUID, and export collections.

### Resource List (left panel)

All resources available on your Ethos instance, loaded from `/api/available-resources`. Versions are shown alongside each resource name.

- Use the **Search** box to filter by resource name
- Click any resource to load its records in the main panel

### Resource Records (right panel)

Displays records from the selected resource as a table with pagination. Each row shows the record's fields as columns.

**Controls:**

| Button | Function |
|---|---|
| **Load** | Fetches the first page of records for the selected resource |
| **Previous / Next** | Paginates through records |
| **Get by GUID** | Fetches a single record by entering its UUID |
| **Postman** | Exports a Postman Collection v2.1 JSON file for the currently loaded resource. Includes a List endpoint and a Get-by-ID endpoint with the correct versioned Accept header, `{{base_url}}` and `{{ethos_token}}` variables pre-configured. |

### Version Selector

A dropdown above the records table lets you select which representation version to request (e.g. `v12.3.0`). The Accept header is constructed automatically.

---

## 9. Mnemonics

**URL:** `/mnemonics`  
**Requires:** Nothing (uses local database)

A team-maintained reference table mapping Colleague file mnemonics to their EEDM resource equivalents. Useful for cross-referencing a Colleague CINC file name with the Ethos resource it corresponds to.

### Browsing & Searching

The left panel lists all saved mnemonics. The **Search** box filters across mnemonic code, Colleague file name, and EEDM resource name simultaneously. Click any row to open its detail panel.

### Detail Panel

Shows for the selected mnemonic:

| Field | Description |
|---|---|
| Mnemonic | The Colleague short code (e.g. `PERM`) |
| File | The full Colleague UniData file name (e.g. `PERSON`) |
| EEDM Resource | The corresponding Ethos resource (e.g. `persons`) |
| Version | The primary EEDM version mapping |
| Change Notification | Whether a CN is configured for this resource |
| CN Notes | Free-text notes about the change notification behavior |
| Known Gotchas | Team notes about known issues or quirks |
| Fields | A sub-table mapping Colleague field names to EEDM field paths |
| Related | Linked mnemonics (e.g. related sub-files) |

### Adding a Mnemonic

Click **Add** (top-right of the list). Fill in the form:
- Mnemonic code (required, auto-uppercased)
- Colleague file name
- EEDM resource
- Version
- CN status and notes
- Gotchas
- Field mappings (add rows as needed)

Click **Save** to store. Entries persist in the local SQLite database.

### Editing & Deleting

With a mnemonic selected in the detail panel:
- **Edit** opens the form pre-filled with the current values
- **Delete** removes the entry after confirmation (cannot be undone)

---

## 10. Field Diff

**URL:** `/field-diff`  
**Requires:** a configured Ethos environment + `UNIDATA_HOST`

**Known limitation:** the comparison logic is not implemented yet. The page and its Matched/EEDM-only/UniData-only layout are fully built, but `POST /api/phase3/field-diff/<resource>` currently returns empty arrays for all three sections with `"note": "Field diff not yet implemented."` (see `app/routes/phase3.py`) — an empty result here means "not yet computed," not "confirmed no differences." Treat this tab as a UI preview until the backend comparison ships.

Compares the fields in an Ethos EEDM resource definition against the actual fields in the corresponding Colleague UniData file. Highlights fields that exist in one place but not the other — useful for diagnosing missing data in Ethos payloads.

### How to use

1. Select or type an EEDM resource name (e.g. `persons`)
2. Click **Compare** — the console fetches the EEDM schema from Ethos and the field list from UniData via uopy
3. Three sections are returned:
   - **Matched** — fields present in both (shown in green)
   - **EEDM only** — fields in the Ethos schema not found in UniData (shown in amber)
   - **UniData only** — fields in the UniData file not mapped in the EEDM schema (shown in grey)

### Requirements

UniData connection must be configured (see [Direct Query](#11-direct-query) for setup). The feature shows a setup guide when `UNIDATA_HOST` is not set.

---

## 11. Direct Query

**URL:** `/colleague-query`  
**Requires:** `UNIDATA_HOST`, `UNIDATA_USER`, `UNIDATA_PASSWORD`, `UNIDATA_ACCOUNT`

Executes TCL/UniQuery statements directly against the Colleague UniData database via the uopy API (Rocket Software's Python interface for UniData/UniVerse). Read-only — no write operations.

### Colleague Files (left panel)

Click **Load Files** to list all UniData files (VOC F-type entries) in the configured Colleague account. Use the **Filter** box to search by name. Click any file name to insert it into the query editor.

### Query Editor

A resizable textarea for writing UniQuery or raw TCL statements.

**Snippet toolbar** — quick-insert buttons above the textarea:

| Button | Inserts |
|---|---|
| SELECT | `SELECT @ID FROM FILE WITH FIELD = "VALUE"` |
| LIST | `LIST FILE FIELD1 FIELD2 WITH FIELD1 = "VALUE" SAMPLE 20` |
| COUNT | `COUNT FILE WITH FIELD = "VALUE"` |
| SAVING | `SELECT FILE WITH FIELD = "VALUE" SAVING @ID` |
| SAMPLE | `LIST FILE FIELD1 FIELD2 SAMPLE 10` |
| LIST VOC | `LIST VOC WITH F1 = "F" BY @ID` |

Click any snippet to replace the editor contents with the template. Edit the placeholders before running.

**Run** — executes the statement and shows output in the results panel  
**Clear** — empties the editor and results

### UniQuery Quick Reference (collapsible)

Click the **? Syntax** button (top-right of the editor card) to toggle a three-column reference panel covering:
- Commands (`LIST`, `SELECT`, `COUNT`, `SORT`)
- Filter operators (`WITH field = "val"`, `NE`, `GT`, `LT`, `LIKE "Sm..."`)
- Sorting (`BY field`, `BY.DSND field`)
- Connectors (`AND`, `OR`, `NOT`)
- Special fields (`@ID`, `@RECORD`)
- Output modifiers (`ID.SUPP`, `HDR.SUPP`, `SAVING`)
- Copy-paste example queries

### Results Panel

Raw TCL output is displayed as preformatted text. If the query returns structured rows (columns detected), a sortable table is rendered with an **Export CSV** button.

### ENVISION Subroutine Caller (collapsible)

Expand the **ENVISION Subroutine Caller** panel at the bottom of the page to call a uopy subroutine directly against the UniData connection.

**How to use:**

1. Enter the subroutine name (e.g. `GET.PERSON.INFO`) — auto-uppercased
2. Click **Add Arg** to add argument rows. For each argument:
   - **Label** — optional friendly name for the arg
   - **Direction** — `IN` (pass a value in), `OUT` (read the returned value), `INOUT` (both)
   - **Value** — the input value (ignored for OUT args)
3. Click **Call** to execute

Results are shown as a table with each argument's label, direction badge, and the value returned after the call. OUT and INOUT args show the subroutine's return values.

### Connection Setup

When `UNIDATA_HOST` is not set, the tab displays a setup guide with the required `.env` variables and installation steps for `uopy==1.4.0`.

---

## 12. Colleague API

**URL:** `/colleague-api`  
**Requires:** `COLLEAGUE_WEB_API_URL`, `COLLEAGUE_WEB_API_USER`, `COLLEAGUE_WEB_API_PASS`

Calls the Ellucian Colleague Web API using Basic authentication. Supports testing CTX transaction calls and inspecting event configuration.

### Connection Status Bar

A narrow status bar at the top of the page. Click **Test Connection** to call `/api/about` on the Colleague Web API. The indicator dot turns:
- **Green** — connected; version string displayed
- **Red** — connection failed or credentials rejected
- **Amber** — test in progress

### CTX Transaction Caller (left panel)

Call any ENVISION business process registered as a Colleague Web API transaction.

**Fields:**

| Field | Description |
|---|---|
| Transaction ID | The ENVISION process name as exposed via the Colleague Web API (e.g. `GET.PERSON.INFO`). Auto-uppercased. |
| Request Body | JSON payload to send. The structure depends on the transaction — consult the Colleague Web API documentation or the ENVISION process definition. |

**Format** button — pretty-prints the JSON payload in the editor.

**Call** — POSTs to `/api/transactions/{transactionId}`. The response is displayed as formatted JSON with the HTTP status badge. **Copy** copies the full JSON response to the clipboard.

**Clear** — resets the transaction ID, payload, and result.

### Event Configurations (right panel)

Click **Load Configurations** to fetch all event configurations from `/api/event-configurations`.

- Use the **Filter** box to search by resource name
- Click any configuration row to open its full JSON detail in the detail panel below
- Enabled configurations show a green `on` badge; disabled show grey `off`

### Detail Panel

Appears below the event configurations list when a configuration or API info is selected. Shows the raw JSON of the selected item with a close button.

### Connection Setup

When `COLLEAGUE_WEB_API_URL` is not set, the tab shows a setup guide with the three required `.env` variables.

---

## 13. Change Notifications

**URL:** `/cn-monitor`
**Requires:** `COLLEAGUE_WEB_API_URL` (for live data) — works fully in `CONSOLE_MOCK_MODE`

Shows Colleague change notification configuration and subscription alignment. The reads are in-process — there is no separate service to point at. (The previous C# CNM service was folded into the console.)

### Summary Tiles

| Tile | Description |
|---|---|
| CN Service | Local status — `colleague_api_configured` reflects whether `COLLEAGUE_WEB_API_URL` is set |
| Total | Total change notifications configured in Colleague |
| Enabled | Count with active publishing enabled |
| Disabled | Count with publishing disabled |
| Subscribed | Resources Ethos is subscribed to |
| Published | Resources Colleague is actively publishing |
| Gaps | Resources in one list but not the other |

### Tabs

**Change Notifications tab**

A filterable table of all Colleague change notification configurations. Columns include resource name, status (Enabled/Disabled), and process code.

- **Search** box filters by resource name in real time
- **Status filter** dropdown filters to Enabled or Disabled
- Click any row to expand its detail panel (right side) showing full configuration JSON, paragraph code if set, and EDPS rules

**Diagnostics tab**

Three-column alignment view comparing what Colleague publishes against what the Ethos tenant is subscribed to:

| Column | Color | Meaning |
|---|---|---|
| Aligned | Green | Colleague publishes AND we subscribe — correctly wired |
| Subscribed, not published | Red | We listen for it but Colleague isn't publishing it — events will never arrive |
| Published, not subscribed | Yellow | Colleague publishes it but we ignore it — expected noise or a missed subscription |

**Audit Log tab**

A timestamped log of every state-changing action recorded by `app/audit.py` — Publish, Trigger, Call, etc. Filterable by user and target identifier. The CN per-notification History view reads from the same audit table.

### Implementation note

In non-mock mode the change-notification reads (`app/cn_repository.py`) call the real Colleague Web API `/api/event-configurations` endpoint. Field-name mapping from that response is best-effort against the documented shape — verify against a real tenant response if the CN list looks off. Run with `CONSOLE_MOCK_MODE=true` to see fixture CN data instead when no Colleague Web API is configured.

---

## 14. Health

**URL:** `/health`  
**Requires:** a configured Ethos environment

Operational health view for the Ethos connection and the console's internal state.

### Summary Tiles

| Tile | Description |
|---|---|
| **Token Status** | Valid / Expired indicator with the token expiry time |
| **Queue Depth** | Current Ethos message queue depth (same as Bus Monitor tile) |
| **P50 Latency** | Median response time of Ethos API calls in the current session |
| **Errors (session)** | Count of Ethos API errors since startup |
| **DoaneEdgeGate** | Up/Unreachable/Not configured, polled from the gate's own `/health` — see below |

### DoaneEdgeGate Tile

Separate from the Ethos tiles above: this polls the DOB-shift prevention reverse proxy's (`../DoaneEdgeGate/`) own `GET /health` endpoint directly, via `GET /api/health/edge-gate` on the console side. Set `EDGE_GATE_URL` (base URL only, e.g. `http://localhost:5199`) to enable it — left unset, the tile reads "Not configured" rather than a false "down". It is polled on its own request/interval, deliberately isolated from the Ethos health payload, so a slow or unreachable gate can never hold up the tiles above it.

| State | Meaning |
|---|---|
| **Not configured** (gray) | `EDGE_GATE_URL` is unset |
| **Up** (green) | The gate responded 200 with `"status":"ok"` |
| **Unreachable** (red) | The gate did not respond, timed out, or returned an error status |

### Resource Health Table

Per-resource breakdown of activity in the current session. Columns: resource name, event count, last seen (seconds ago), rate (events/hour), status. Helps identify which resources have gone silent.

### API Latency Panel

Percentile breakdown of Ethos API response times for the current session:

| Metric | Description |
|---|---|
| P50 | Median response time — half of calls were faster than this |
| P95 | 95th percentile — only 5% of calls were slower |
| P99 | 99th percentile — the edge of normal performance |
| Max | Slowest single call observed |

### Recent Errors

A summary of the most recent Ethos API errors. Click **View all** to navigate to the full Errors page (`/errors`), which shows every error ever persisted to the `EthosErrorLog` database table — unlike this tile's session-scoped in-memory counter, the Errors page survives a console restart and is only cleared via `POST /api/errors/flush` or a direct delete — with timestamp, endpoint, and full error message.

---

## 15. Configuration Reference

All variables go in `console/.env`. Copy `console/.env.example` as a starting point.

### Core — Required

At least one Ethos environment block is required:

| Variable | Default | Description |
|---|---|---|
| `ETHOS_ENV_1_NAME` | — | Display name for the environment (e.g. `Dev`, `Test`, `Prod`). |
| `ETHOS_ENV_1_URL`  | `https://integrate.elluciancloud.com` | Ethos API base URL for this environment. |
| `ETHOS_ENV_1_KEY`  | — | Ethos integration API key. Required for all Ethos-backed features. |
| `ETHOS_ENV_1_GRAPHQL_KEY` | _(falls back to `_KEY`)_ | Optional — set only when the bus key for this env lacks GraphQL scope. |
| `DEFAULT_ENV` | _(first configured env)_ | Case-insensitive match against an `ETHOS_ENV_n_NAME` to preselect at startup. |
| `SECRET_KEY` | `dev-secret-change-in-prod` | Flask session signing key — also signs the login session cookie (see Authentication below). **Must** be a real random value in any deployment that sets `AUTH_USERNAME`/`AUTH_PASSWORD` — left at the default, the login gate can be bypassed by forging a session cookie. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"`. |

### Authentication

```
AUTH_USERNAME=
AUTH_PASSWORD=
AUTH_COOKIE_SECURE=true
AUTH_SESSION_LIFETIME_HOURS=8
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_REDIRECT_URI=
```

| Variable | Default | Description |
|---|---|---|
| `AUTH_USERNAME` / `AUTH_PASSWORD` | — | The single shared login credential, delivered to the container as plaintext env vars from a Kubernetes secret (the secret itself is encrypted at rest). **Fail-closed:** unset either one (and Entra, below, isn't configured either) and every route except health checks is blocked, not silently ungated. |
| `AUTH_COOKIE_SECURE` | `true` | Cookie only sent over HTTPS. Set `false` only for local `http://localhost` dev. |
| `AUTH_SESSION_LIFETIME_HOURS` | `8` | How long a login lasts before you're asked to sign in again. |
| `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` / `ENTRA_REDIRECT_URI` | — | Optional Entra ID (Azure AD) SSO. When **all four** are set, an unauthenticated visit to any page auto-redirects straight to Microsoft's sign-in page instead of the local form — which stays reachable directly at `/login` as a fallback (Entra outage, or before the app registration/admin consent is finished). Register a Web-platform app in entra.microsoft.com, add a client secret, and register `ENTRA_REDIRECT_URI` byte-for-byte (protocol/host/port/path, no trailing-slash difference) or Microsoft refuses with `AADSTS50011`. Signed-in users get their real Entra identity (`session["username"]`, and the audit trail's actor) instead of the shared credential's literal username string. |

Define `ETHOS_ENV_2_*` through `ETHOS_ENV_5_*` the same way to expose the nav-bar environment switcher.

### Multi-Environment Switcher

Define up to 5 named environments. The nav dropdown appears when 2 or more are configured.

```
ETHOS_ENV_1_NAME=Dev
ETHOS_ENV_1_URL=https://integrate.elluciancloud.com
ETHOS_ENV_1_KEY=<dev api key>

ETHOS_ENV_2_NAME=Prod
ETHOS_ENV_2_URL=https://integrate.elluciancloud.com
ETHOS_ENV_2_KEY=<prod api key>
```

### Colleague Web API

| Variable | Description |
|---|---|
| `COLLEAGUE_WEB_API_URL` | Base URL of the Colleague Web API (e.g. `https://colleague-webapi.doane.edu`) |
| `COLLEAGUE_WEB_API_USER` | Service account username |
| `COLLEAGUE_WEB_API_PASS` | Service account password |

### UniData / Direct Query

| Variable | Default | Description |
|---|---|---|
| `UNIDATA_HOST` | — | Hostname or IP of the UniData server |
| `UNIDATA_PORT` | `31438` | OIPC port |
| `UNIDATA_USER` | — | UniData service account |
| `UNIDATA_PASSWORD` | — | UniData password |
| `UNIDATA_ACCOUNT` | — | Full server-side path to the Colleague apphome directory (e.g. `D:\Ellucian\coll18\test\apphome`) |

### Conductor / Replay

| Variable | Description |
|---|---|
| `CONDUCTOR_URL` | Netflix Conductor API base URL |
| `CONDUCTOR_API_KEY` | Conductor API key |

### DoaneEdgeGate

| Variable | Default | Description |
|---|---|---|
| `EDGE_GATE_URL` | _(unset)_ | Base URL of the DoaneEdgeGate proxy (see §17), e.g. `http://localhost:5058`. The console appends `/health` itself. Leave unset to show the Health tab tile as "Not configured" rather than a false "down". |

### Alerting

| Variable | Default | Description |
|---|---|---|
| `SILENCE_THRESHOLD_MINUTES` | `30` | Minutes without activity on a resource before it's flagged silent (Bus Monitor / resource health) |

### Database & Server

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite (`ethos_console.db`) | PostgreSQL connection string if not using SQLite (e.g. `postgresql://user:pass@localhost:5432/ethos_console`) |
| `PORT` | `5012` | HTTP port |
| `FLASK_ENV` | `development` | `development` or `production` |
| `BUS_POLL_INTERVAL` | `2` | Seconds between Ethos bus polls, once started (see §4 — the monitor no longer auto-starts) |

### DOB Repair — SQL Fetch Source

Optional, alternative to CSV upload on the DOB Repair tab (see §16). Leave all unset to keep DOB Repair CSV-only.

```
DOB_RECONCILE_INPUT_CSV=
DOB_RECONCILE_SQL_FILE=
DOB_RECONCILE_DB=DRIVER={ODBC Driver 17 for SQL Server};Server={serverNameHere};Database={databaseNameHere};UId={userNameHere};PWD={passwordHere};
```

| Variable | Description |
|---|---|
| `DOB_RECONCILE_INPUT_CSV` | Path to a PERSON export CSV that a nightly job refreshes on the server. Shows a "Reload from configured export" button when set. |
| `DOB_RECONCILE_SQL_FILE` | Path to a `.sql` file you draft and own — a single read-only SELECT/WITH statement whose output columns match `app/dob_detector.py`'s `DEFAULT_COLUMNS`. See `docs/dob_reconcile_query.example.sql`. |
| `DOB_RECONCILE_DB` | A complete ODBC connection string for the SQL Server reporting connection (your Colleague reporting view / ODS mirror) — this app never assembles one from parts, so include everything your driver needs (`Encrypt=yes;TrustServerCertificate=yes` for a typical internal SQL Server with a self-signed certificate; omit `UId`/`PWD` for a trusted/Windows-integrated connection). |

Grant that connection string's DB login **SELECT-only** permission on whatever reporting views the query touches — that's the real safety boundary, not the app's own read-only-statement guard.

**Grant the configured DB login SELECT-only permission** on whatever views the query touches — that's the real safety boundary, not the app's own read-only-statement guard (`app/dob_sql_source.py` rejects multiple statements and write keywords, but that's a footgun-catcher, not a substitute for database permissions).

---

## 16. DOB Repair

**URL:** `/dob-repair`  
**Requires:** Nothing (CSV upload works out of the box; SQL fetch is optional — see §15)

Detects and human-reviews PD0002124 — the Colleague Self-Service Instant Enrollment defect that stores a registrant's Date of Birth one day early when their browser timezone is east of the Central-time server. This tab finds likely-shifted PERSON records from a data export and proposes corrections. **It never writes to Colleague, Ethos, or NAE.** A reviewer accepts, rejects, or defers each candidate, and the tab exports an approved-corrections CSV that you apply through your own sanctioned write channel (an audited Ethos PUT, or manual NAE correction).

This tab displays applicant PII — name, date of birth, address, email, phone — so restrict access to the review team, not the general console user base.

**Important, confirmed by direct data audit:** the original design assumption — a shifted DOB causes Instant Enrollment's duplicate-check to fail and create a *second* PERSON record, giving a "twin pair" to compare against — does not describe what's actually happening. No duplicate PERSON records with differing birth dates are being created by this bug. For a brand-new registrant (the majority of Instant Enrollment traffic), the shifted DOB is the *only* record of that value — there is no twin to pair against by construction, not by bad luck. Practical effect:
- The **Review Queue** (twin-pairing, below) is real but low-yield for this specific bug's backlog. Still worth running — it costs nothing and catches genuine duplicates from other causes too.
- The **Elevated Risk Worklist** (below) is the mechanism with real reach into the backlog, but it cannot confirm anything from data alone — treat it as an outreach/verification contact list, not a correction list.
- If your export includes a same-person corroboration source — a DOB the person independently resubmitted later via a different channel (a transcript order, a financial aid application, anything where they restate their own DOB on a separate later occasion) — populate the optional `corroborating_dob`/`corroborating_source` columns below. This is the one mechanism that can confirm a shift with no identity-matching ambiguity at all, since it's definitionally the same person_id.

### Load PERSON Export

Export PERSON data from any source you have — an ODS/Colleague reporting view, an Informer report, or an Ethos-to-CSV export. Minimum useful columns: person id, last/first name, date of birth, and an origin field marking Instant Enrollment records. A real Colleague extract's origin column usually carries an institution-specific operator/process code (e.g. a numeric web-registration operator ID, or `GUEST`/`WEBCASHIER`-style process names) rather than a human-readable label like `INSTANT_ENROLL` — set `DOB_RECONCILE_IE_ORIGIN_CODES` in `.env` to your own confirmed codes (see §15) rather than expecting the generic defaults (`INSTANT_ENROLL`, `INSTANT ENROLLMENT`, `IE`, `SS_IE`) to match. Address, email, and phone improve identity matching. Two additional OPTIONAL columns, `corroborating_dob` and `corroborating_source`, enable the same-person corroboration mechanism described above — omit them entirely if you have no such source.

- Choose the CSV file and click **Analyze**.
- If `DOB_RECONCILE_INPUT_CSV` is set, a **Reload from configured export** button appears.
- If the SQL fetch source is configured (§15), a **Fetch via SQL & Analyze** button appears — runs a single, server-administered SELECT query live against your reporting database.
- **Identity Threshold** (default 6) — how strongly two records must resemble the same person before they're compared for a one-day DOB gap.

### Review Queue

Every candidate's DOBs are exactly one calendar day apart, from one of two sources — a cross-person twin pair, OR a same-person corroboration (current PERSON DOB vs. `corroborating_dob` for the same person_id, when that column is populated) — sorted worst-first:

| Bucket | Meaning |
|---|---|
| **HIGH** | EITHER the Instant-Enroll record is exactly one day *before* an authoritative (non-IE) twin, OR a same-person corroboration matches the -1 day signature. Classic bug signature either way. The later/corroborating date is proposed as the true DOB. |
| **MEDIUM** | Cross-person twin only: same one-day gap, but origin doesn't cleanly separate corrupted from authoritative. Later date is a tentative guess only — confirm before accepting. |
| **REVIEW** | The Instant-Enroll-side date is the *later* one — the wrong direction for this bug, so it's more likely a typo, two different people, or an unrelated later edit. No date is pre-selected. |

A same-person corroboration row shows the same person_id on both sides of the table — that's expected, not a bug; it means the "twin" is the same PERSON record confirmed against an independent later resubmission, not a second person. For each row, pick which date is true (pre-selected to the later/corroborating date for HIGH and MEDIUM), then **Accept** (after a confirmation dialog), **Reject**, or **Defer**. Decisions persist across re-analysis.

### Elevated Risk Worklist

Instant-Enroll records with a DOB, no twin, no corroboration, and an address in an Eastern-time state. Per the confirmed finding above, this is expected to contain most of the actual backlog for new registrants — but it still **cannot be confirmed from data alone**. This is a **risk-ranked outreach/verification contact list, not proof of corruption**: it tells you who to contact to confirm their real DOB, not what to change. Never correct this list wholesale, and never bulk-apply anything from it.

### Export Corrections CSV

Downloads every **accepted** decision as `dob_corrections.csv` with columns: `person_id, current_dob, corrected_dob, decided_by, decided_at, candidate_id, note`. This is the hand-off point to a separate, deliberate write step — it is not applied automatically by this console.

---

## 17. DoaneEdgeGate

**Not a console tab** — DoaneEdgeGate is a separate ASP.NET Core reverse proxy (`DoaneEdgeGate/` at the repo root, part of the same `ethos-console.sln`) that sits in front of the Colleague Web API and prevents PD0002124 (§16's DOB timezone shift) at the network edge, before a corrupted date is ever written. It's covered here because the console has direct visibility into it (§14's Health tile) and a documented working relationship with DOB Repair, below.

### What it does

The Self-Service date picker serializes local midnight as a UTC instant (`toISOString()`) — for any US timezone, that lands on a same-date *morning* UTC time. The Colleague Web API then truncates that instant to server-local (Central) date, landing one day early for anyone east of Central. DoaneEdgeGate forwards the bare date instead of the instant, so the server has nothing to truncate and the intended date survives. No timezone math, and it's fail-safe: a value that's already a bare date is left untouched.

### Run modes

Three modes, meant to be used left to right:

| Mode | Behavior |
|---|---|
| **Off** (default) | Pure passthrough — the gate does nothing. Deploy in this mode first. |
| **Shadow** | Runs the transform and logs every would-be rewrite, but forwards the ORIGINAL body unchanged. Validates against real traffic with zero risk before mutating anything. |
| **Active** | Matched requests are rewritten before forwarding. |

`FailMode=Open` (the default and strongly recommended setting) forwards the original body unchanged if the rewrite step ever throws — the gate sits in front of every registration and must never be able to drop an enrollment.

### Relationship to DOB Repair (§16)

DoaneEdgeGate is prevention; DOB Repair is detection and cleanup — for whatever got through before the gate was Active, or for the population outside its reach (see the limitation below). Every rewrite (and every would-be rewrite in Shadow) is logged with the original instant and the rewritten date, keyed to the request — and, with the response record-ID capture feature, to the actual Colleague record it produced. That's a direct join key for the nightly detector, not a fuzzy inference. See `DOB-Repair-Tandem-Flow.md` at the repo root for the full picture of how the two tools reinforce each other.

**One honest limitation:** a registrant physically in a UTC-ahead zone (Europe, Asia, Australia) at submission time serializes local midnight to the *previous* UTC date — already wrong before it reaches the gate, with no offset information left to recover the intended date. This population is small for Instant Enrollment but real. DOB Repair's same-person corroboration mechanism (§16) is the only way to catch this case after the fact.

### Where it lives / how to deploy it

The proxy's source, tests, and full documentation live in `DoaneEdgeGate/` — this guide doesn't duplicate that material. Start here, in order:

1. `DoaneEdgeGate-Deployment-Walkthrough.md` — pre-reqs, watch-outs, and a test checklist; the index into everything else below.
2. `DoaneEdgeGate-Pilot-and-Phase0.md` — the repoint decision and the Phase 0 go/no-go capture (do this before deploying anything).
3. `DoaneEdgeGate-IIS-Deployment.md` — the concrete per-environment IIS rollout.
4. `DoaneEdgeGate/docs/architecture.md` — the full design and every configuration option.

### Health tab integration

See §14's DoaneEdgeGate Tile — the console polls the gate's own `GET /health` independently of the Ethos tiles, so a slow or unreachable gate can never hold up the tiles next to it. That's the console's only integration with the gate today — it does not read `/api/v1/status` or `/api/v1/rewrites/recent`. Hit those directly on the gate if you need mode, rewrite counts, or the recent-rewrites audit trail.

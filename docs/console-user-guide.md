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

Set `CONSOLE_KEY=some-secret` in `.env` to password-protect the console. Leave it blank to run open (suitable for local-only use). When a key is set, a **Sign out** link appears in the top nav.

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
| **Sign out** link | Ends the session (only visible when `CONSOLE_KEY` is configured) |

### Token Expiry Banner

A collapsible amber banner appears automatically across the top of the page when the active Ethos JWT token has 10 minutes or fewer remaining. It shows the exact minutes left and dismisses itself once the token refreshes (which happens automatically on the next API call). The check runs once per minute.

### Tab Bar

The dark row of tabs beneath the navbar. Each tab links to a major feature area. Tabs with an `OFF` badge require additional `.env` configuration — clicking them still works and shows a setup guide.

---

## 4. Bus Monitor

**URL:** `/`  
**Requires:** `ETHOS_API_KEY`

The Bus Monitor continuously polls the Ethos message bus, displaying every change notification as it arrives. It is the primary real-time operational view.

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

**Silence threshold:** A number input at the bottom of the resource table lets you set a custom silence threshold (default 30 minutes). Resources that exceed this threshold without an event are highlighted and, if `ALERT_WEBHOOK_URL` is configured, trigger a webhook alert.

---

## 5. Replay

**URL:** `/replay`  
**Requires:** `ETHOS_API_KEY` + `CONDUCTOR_URL`

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
**Requires:** `ETHOS_API_KEY` (or `ETHOS_GRAPHQL_API_KEY` for a dedicated key)

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
**Requires:** `ETHOS_API_KEY`

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
**Requires:** `ETHOS_API_KEY`

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
**Requires:** `ETHOS_API_KEY` + `UNIDATA_HOST`

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
**Requires:** `CNM_BASE_URL`

Connects to the Change Notification Manager (CNM) service to show Colleague change notification configuration and subscription alignment.

### Summary Tiles

| Tile | Description |
|---|---|
| CNM Service | Connection status dot + status text |
| Total | Total change notifications configured in Colleague |
| Enabled | Count with active publishing enabled |
| Disabled | Count with publishing disabled |
| Subscribed | Resources our Conductor consumer listens to |
| Published | Resources Colleague is actively publishing |
| Gaps | Resources in one list but not the other |

### Tabs

**Change Notifications tab**

A filterable table of all Colleague change notification configurations. Columns include resource name, status (Enabled/Disabled), and process code. 

- **Search** box filters by resource name in real time
- **Status filter** dropdown filters to Enabled or Disabled
- Click any row to expand its detail panel (right side) showing full configuration JSON, paragraph code if set, and EDPS rules

**Diagnostics tab**

Three-column alignment view comparing what Colleague publishes against what Conductor subscribes to:

| Column | Color | Meaning |
|---|---|---|
| Aligned | Green | Colleague publishes AND we subscribe — correctly wired |
| Subscribed, not published | Red | We listen for it but Colleague isn't publishing it — events will never arrive |
| Published, not subscribed | Yellow | Colleague publishes it but we ignore it — expected noise or a missed subscription |

**Audit Log tab**

A timestamped log of all actions taken through the CNM service — who viewed, enabled, disabled, or deleted what. Filterable by date range and user.

### Connection Setup

When `CNM_BASE_URL` is not set, the tab shows a setup guide. In local development, set `CNM_BASE_URL=http://localhost:5011` and leave `CNM_API_KEY` blank (the CNM dev server accepts unauthenticated requests). In production, set both URL and API key.

---

## 14. Health

**URL:** `/health`  
**Requires:** `ETHOS_API_KEY`

Operational health view for the Ethos connection and the console's internal state.

### Summary Tiles

| Tile | Description |
|---|---|
| **Token Status** | Valid / Expired indicator with the token expiry time |
| **Queue Depth** | Current Ethos message queue depth (same as Bus Monitor tile) |
| **P50 Latency** | Median response time of Ethos API calls in the current session |
| **Errors (session)** | Count of Ethos API errors since startup |

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

A summary of the most recent Ethos API errors. Click **View all** to navigate to the full Errors page (`/errors`), which shows every error logged since the console started with timestamp, endpoint, and full error message.

---

## 15. Configuration Reference

All variables go in `console/.env`. Copy `console/.env.example` as a starting point.

### Core — Required

| Variable | Default | Description |
|---|---|---|
| `ETHOS_API_KEY` | — | Ethos integration API key. Required for all Ethos-backed features. |
| `ETHOS_BASE_URL` | `https://integrate.elluciancloud.com` | Ethos API base URL |
| `SECRET_KEY` | `dev-secret-change-in-prod` | Flask session signing key. Change in production. |

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

### GraphQL Dedicated Key

| Variable | Description |
|---|---|
| `ETHOS_GRAPHQL_API_KEY` | Optional. When set, all GraphQL tab operations (schema load, query execution) use this key instead of `ETHOS_API_KEY`. Useful for pointing GraphQL at a production environment while the rest of the console uses a test key. |

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

### Change Notification Manager

| Variable | Description |
|---|---|
| `CNM_BASE_URL` | CNM service URL (e.g. `http://localhost:5011` for local dev) |
| `CNM_API_KEY` | Azure AD bearer token for production. Leave blank for local dev. |

### Conductor / Replay

| Variable | Description |
|---|---|
| `CONDUCTOR_URL` | Netflix Conductor API base URL |
| `CONDUCTOR_API_KEY` | Conductor API key |

### Alerting

| Variable | Default | Description |
|---|---|---|
| `ALERT_WEBHOOK_URL` | — | Teams or Slack incoming webhook URL. Teams URLs contain `webhook.office.com`; all others are treated as Slack/generic. Leave blank to disable. |
| `ALERT_ERROR_THRESHOLD` | `10` | Number of bus poll errors per hour before an alert fires |
| `SILENCE_THRESHOLD_MINUTES` | `30` | Minutes without activity on a resource before a silence alert fires |

### Database & Server

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite (`ethos_console.db`) | PostgreSQL connection string if not using SQLite (e.g. `postgresql://user:pass@localhost:5432/ethos_console`) |
| `CONSOLE_KEY` | *(open)* | Password for the console UI. Leave blank for open access. |
| `PORT` | `5012` | HTTP port |
| `FLASK_ENV` | `development` | `development` or `production` |
| `BUS_POLL_INTERVAL` | `2` | Seconds between Ethos bus polls |

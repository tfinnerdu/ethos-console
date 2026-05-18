# Change Notification Manager — End-to-End User Guide

**Audience:** Enterprise Services team members  
**Version:** v1 (read-only; Colleague Web API 2.9)  
**Status:** Draft — sections marked *[Pending Colleague connection]* will be updated once the application is connected to the dev Colleague environment.

---

## 1. What is CNM?

The Change Notification Manager is an internally-built web application that gives the Enterprise Services team a centralized view of how Colleague publishes change notifications to our Ethos integration platform.

Colleague can publish notifications for roughly 240 EEDM resources. Our Netflix Conductor consumer currently subscribes to about 41 of those. CNM surfaces both sides of that relationship in one place, shows you the configuration details behind each notification, and keeps a full audit trail of every action taken in the tool.

In v1, CNM is **read-only**. Every edit, enable, disable, and delete control is visible in the UI but intentionally disabled — v1 is about visibility and establishing the operational foundation. Write operations arrive in v1.5.

---

## 2. Access and Roles

### Getting access

Access is controlled via Active Directory group membership. Contact the Enterprise Services team lead to be added to the appropriate group.

| AD Group | CNM Role | What it allows |
|---|---|---|
| *(TBD — confirm group names with AD team)* | `CNM.Viewer` | View all read-only screens |
| *(TBD)* | `CNM.Admin` | Viewer access + audit log |

### Signing in

1. Navigate to the CNM application URL *(dev: TBD once deployed to dev cluster)*
2. You will be redirected to the Doane AD sign-in page
3. Sign in with your `@doane.edu` credentials
4. You are returned to CNM and landed on the Change Notifications list

> **Local dev note:** When running locally with `.\start-local.ps1`, authentication is bypassed — you are automatically signed in as `dev-user` with `CNM.Admin` access. No AD credentials are needed for local development.

---

## 3. Navigation

The left sidebar contains four sections:

| Nav item | What it shows |
|---|---|
| **Change Notifications** | Full inventory of configured change notifications |
| **Diagnostics** | Subscription vs. publishing mismatch view |
| **Audit Log** | Full audit trail of all activity in CNM *(admin only)* |

The header shows your display name and a **Sign out** button.

---

## 4. Change Notifications List

**Path:** `/change-notifications`

This is the main inventory screen. It shows all change notifications that Colleague is configured to publish — approximately 240 entries once connected to the dev environment.

### What each column means

| Column | Source | Notes |
|---|---|---|
| Resource | Colleague CINC form | The EEDM resource name (e.g. `persons`, `x-dp-comments`) |
| Description | Colleague CINC form | Human-readable description of the notification |
| Status | `GET /api/event-configurations` | `Enabled` or `Disabled` — whether Colleague is actively publishing |
| Has Paragraph | Colleague CINC form | Whether a custom Envision paragraph controls when the notification fires |
| Last Modified | Colleague / CNM audit | Most recent change to this notification's configuration |

### Filtering

Use the **Resource** and **Status** filter controls at the top of the list to narrow the view. Filters are applied client-side after the initial load.

### Namespace indicators

Resources are grouped visually by namespace:

- No prefix → standard EEDM resource (e.g. `persons`, `courses`)
- `x-dp-` prefix → Doane institution-defined custom resource (e.g. `x-dp-comments`)
- `d45-` prefix → vendor/partner resource (likely Ethos cloud-proxied, not Colleague-published)

> *[Pending Colleague connection]* The status column will show real Enabled/Disabled values once connected. Currently shows `Unknown` for all entries.

---

## 5. Change Notification Detail

**Path:** `/change-notifications/{id}`

Click any row in the list to open the detail view for that notification.

### Fields shown

| Field | Description |
|---|---|
| Resource Name | EEDM resource identifier |
| Status | Current enabled/disabled state |
| Process Code | The Colleague business process name (e.g. `INTG-PERSON`) |
| Paragraph Code | The Envision paragraph name, if one is configured |
| Parameters | Any parameter values associated with the notification |
| EDPS Rules | Privacy rules applied to this resource's fields |
| Last Modified | Timestamp of the most recent configuration change |

### Disabled controls

The **Enable**, **Disable**, and **Delete** buttons are visible but non-interactive in v1. They will activate in v1.5 once the `PUT /api/event-configurations` write path is implemented.

### Viewing history

The **History** tab within the detail view shows all CNM audit entries for this specific notification — who viewed it, any attempted changes, and outcomes.

---

## 6. Paragraph Viewer

**Path:** `/change-notifications/{id}` → Paragraph tab

If a notification has a paragraph code, the **Paragraph** tab shows the raw Envision source code for that paragraph.

This is a read-only view. The source is fetched from Colleague's data store (DAS or SQL primary — confirmed during pre-work §0.1) and displayed as-is.

> *[Pending Colleague connection]* Paragraph source retrieval requires the DAS/SQL integration to be wired up. Currently shows a "not available" state.

**Who can see paragraphs:** All `CNM.Viewer` users. Paragraph views are logged to the audit trail.

---

## 7. Diagnostics — Subscription vs. Publishing

**Path:** `/diagnostics`

This view compares two lists:

- **Subscribed** — the ~41 resources our Conductor consumer listens to (static list seeded in CNM)
- **Published** — the ~240 resources Colleague is actively configured to publish (from `GET /api/event-configurations`)

The view is divided into three sections:

| Section | Badge color | Meaning |
|---|---|---|
| Subscribed but NOT published | Red | We consume these in Conductor but Colleague has no active publishing config. Events will never arrive. |
| Published but NOT subscribed | Yellow | Colleague is publishing these but we are not listening. Noise in Ethos we are ignoring. |
| Aligned | Green | Both sides agree — Colleague is publishing and we are subscribed. |

### How to interpret findings

**Subscribed but not published** is the most actionable finding. If a resource appears here after Colleague is connected, check:
1. Is it a `d45-*` resource? These are likely vendor-proxied via Ethos cloud and won't appear in Colleague's CINC — expected gap.
2. Is it an initiation-style resource (e.g. `personal-relationship-initiation-process`)? These may be RPC-only and not emit data-change notifications — expected gap.
3. Is it a standard EEDM resource that should be publishing? That is a real misconfiguration worth investigating in Colleague's CINC form.

> *[Pending Colleague connection]* Currently shows all 41 subscribed resources as "subscribed but not published" because the Colleague stub returns an empty list. This resolves once the integration is live.

---

## 8. Audit Log

**Path:** `/audit`  
**Requires:** `CNM.Admin` role

The audit log is an append-only record of every meaningful action in CNM. Entries are written by the application, not Colleague — so CNM's audit log is the authoritative record of which human did what.

### What is logged

| Action | Trigger |
|---|---|
| `View` | Any user views the change notification list or a detail record |
| `ViewParagraph` | A user opens the paragraph viewer for a notification |
| `Edit` | A user attempts to modify a notification *(v1.5+)* |
| `Enable` / `Disable` | A user enables or disables a notification *(v1.5+)* |
| `Delete` | A user deletes a notification *(v1.5+)* |

### Filtering

Filter by **User**, **Target identifier**, or **Date range**. Results are paged at 50 per page by default.

### Columns

| Column | Description |
|---|---|
| Timestamp | UTC timestamp of the action |
| User | AD principal who performed the action |
| Action | What was done |
| Target | The notification ID or paragraph code affected |
| Outcome | `Success`, `Failure`, or `Denied` |
| Correlation ID | Groups related operations (e.g. a view that triggered a paragraph fetch) |
| Source IP | Client IP address at time of action |

> **Local dev:** Audit entries write to `.hub-logs/audit.txt` instead of the database. Open that file to inspect audit activity during local development.

---

## 9. Health Checks

Two health endpoints are available for operational use:

### Shallow (liveness)

```
GET /api/v1/health
```

Returns immediately with no external dependencies. Used by k8s liveness probe.

```json
{ "status": "ok", "service": "cnm-api", "version": "1.0.0", "uptime_seconds": 3600 }
```

### Deep (readiness / monitoring)

```
GET /api/v1/health/deep
```

Runs read-only checks against all dependencies. Use this for Pingdom / Uptime Kuma / Grafana alerting. Safe to call every 30 seconds.

```json
{
  "status": "healthy",
  "total_duration_ms": 45,
  "checks": {
    "database":         { "status": "healthy",  "description": null },
    "colleague-api":    { "status": "healthy",  "description": "Colleague Web API responding. Version: 2.9.0.0" },
    "resources-seeded": { "status": "healthy",  "description": "41 resources loaded." }
  }
}
```

| Status | HTTP code | Meaning |
|---|---|---|
| `healthy` | 200 | All checks passed |
| `degraded` | 503 | At least one check is impaired but the app is still running |
| `unhealthy` | 503 | A critical dependency is down |

`colleague-api` returning `degraded` does **not** cause k8s to restart the pod — CNM itself is still operational; only Colleague data is unavailable.

---

## 10. Known Limitations (v1)

- All edit, enable, disable, and delete controls are visible but non-interactive. This is intentional — they activate in v1.5.
- Paragraph source retrieval requires DAS/SQL integration (pre-work §0.1). Shows unavailable until wired.
- The diagnostics view shows all subscribed resources as mismatched until Colleague integration is live.
- The application is deployed to the dev environment only in v1. Test and prod deployments arrive in v1.5.
- `d45-*` resources will likely always appear in "subscribed but not published" — they are vendor-proxied via Ethos cloud, not Colleague-published.

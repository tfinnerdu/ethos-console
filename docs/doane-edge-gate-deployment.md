# DoaneEdgeGate — Deployment Walkthrough

Reverse-proxy mitigation for PD0002124 (Colleague Self-Service Instant
Enrollment's -1 day DOB timezone defect). This gate sits in front of Self-
Service and rewrites the corrupted DOB field in-flight, so the fix lands
before Colleague ever sees the bad value — as opposed to `docs/dob_reconcile_
query.example.sql` / the DOB Repair tab, which clean up records already
written.

**Status note:** this walkthrough is written from the architecture described
in the investigation-findings handoff doc plus everything confirmed in this
session's diagnostic work. It has NOT yet been reconciled against the
`DoaneEdgeGate-IIS-Deployment.md` produced in the original build session —
if that document exists and you want it merged rather than superseded, share
it and this gets reconciled rather than duplicated.

---

## 1. What this is, in one paragraph

A YARP-based ASP.NET Core reverse proxy, IIS-hosted, sitting in front of the
`Student` Self-Service site via **repoint** (DNS/binding redirected to the
gate; the gate forwards upstream to Self-Service's real, now-internal
endpoint) — **not takeover** (the gate does not run inside Self-Service's
own process/site). It inspects the JSON body of the Instant Enrollment
person-create POST, and when the DOB field matches the bug's known corrupted
shape (a UTC `Z`-suffixed midnight instant that decodes to the wrong
calendar date), rewrites it to the correct date before forwarding. Three
modes control blast radius: **Off** (pure passthrough, does nothing) →
**Shadow** (inspects and logs what it *would* rewrite, changes nothing) →
**Active** (actually rewrites). `FailMode=Open`: if the gate itself errors,
the request passes through unmodified rather than blocking a registration.

---

## 2. Pre-requisites — confirm these BEFORE deploying, not during

These are blockers, not nice-to-haves. Deploying without them risks either a
broken gate or, worse, corrupting/blocking real registrations.

### 2.1 Phase 0 capture — is this actually done yet?

The original findings doc flagged this as gating everything: a live capture
(via DevTools Network request blocking or an XHR/fetch breakpoint) on
**prod**, of the real person-create POST, before any record is created.
Four things needed from that one request:

| # | What | Why it matters |
|---|---|---|
| 1 | Content-Type of the POST | The gate's middleware no-ops on any non-JSON body (fail-safe). If IE posts form-urlencoded instead of JSON, the gate as designed does nothing at all. |
| 2 | DOB value shape | Confirms it's genuinely a `Z`-suffixed UTC instant (the bug signature) and not an offset form, a bare date, or something else — this is the actual go/no-go for the whole approach. |
| 3 | Exact request path | Becomes the gate's `Match:PathPatterns` config. |
| 4 | Exact DOB field name in the JSON body | Becomes the gate's `Rewrite:DateFieldNames` config. |

**If this hasn't been done yet, do it first** — every config value below
depends on it, and deploying with guessed values means the gate either does
nothing (silently) or, worse, rewrites the wrong field.

### 2.2 Where does the gate physically need to sit?

Open question from the findings doc: a separate IIS site `D45-Web-API`
exists alongside `prod_selfservice` on the same server. Not yet confirmed
whether the browser's person-create POST hits `Student` directly or routes
through `D45-Web-API`. Trace this in the same Network capture as Phase 0 (or
a separate one) — if the DOB payload passes through `D45-Web-API`, the
repoint target is that site, not `Student` directly, and the whole binding
plan below needs to point there instead.

### 2.3 Test environment sanity, now that login is unblocked

You've confirmed the guest-credential gap was the login blocker and you're
in on test. Before running ANY registration through the gate in test —
including throwaway validation runs:

- **Confirm test's Web API/DMI connection points at test's own Colleague
  account, not prod's.** This was flagged as OPEN, HIGH PRIORITY in the
  findings doc and is now live risk, not theoretical, since you can reach
  Instant Enrollment on test. A "test" registration against a mispointed DMI
  writes a real PERSON record into production.
- Confirm whether test is on the same SS/Web API build/patch level as prod.
  A gate config validated against a different build isn't guaranteed valid
  on prod without re-verification.
- The blank `identityProviderPublicKeyPassword` (SAML) gap on test is a
  separate, real issue (breaks real user/staff SSO login) — unrelated to
  Instant Enrollment specifically, but worth fixing before test is otherwise
  considered "matches prod."

### 2.4 Payment / completing a full registration in test

Phase 0 capture and Shadow-mode validation both happen at/around the
Personal Identification step, upstream of payment — you don't need a
completed registration for those. Only the final Active-mode pilot check
(confirm the corrected date actually lands in Colleague) needs a completed
registration. Before standing up sandbox Ellucian Payment Gateway wiring,
try a **$0 test section** in Colleague, or a pay-later/invoice path if your
CE Web Reg Params support one — cheaper to set up and sufficient for this
specific validation.

---

## 3. Deployment steps

1. **Stand up the gate as its own IIS site/app pool** on the same server (or
   an adjacent one), bound to whatever port/host the repoint plan calls for.
   Do NOT install it into `prod_selfservice`'s existing site — that's the
   "takeover" approach explicitly rejected in favor of repoint.
2. **Configure YARP's upstream (`Downstream:BaseUrl`)** to point at Self-
   Service's real endpoint — resolved per §2.2 above (either `Student`
   directly, or `D45-Web-API` if that's confirmed as the actual DOB-carrying
   hop).
3. **Set the gate's own config**: `Match:PathPatterns`, `Rewrite:DateFieldNames`
   from Phase 0 capture (§2.1), `FailMode=Open`, mode = **Off** initially.
4. **Repoint DNS/binding** so external traffic hits the gate's binding
   instead of `prod_selfservice` directly. Confirm the gate in Off mode is
   fully transparent — every route, not just Instant Enrollment, must behave
   identically to today, since Off-mode passthrough is your safety net if
   anything about the repoint itself is wrong.
5. **Flip to Shadow.** No behavior change from a user's perspective; the
   gate now logs what it would have rewritten. This is where you actually
   validate the transform logic against real traffic with zero risk to real
   registrations.
6. **Only after a clean Shadow pass**, flip to **Active** for the
   `FieldAllowlist` (the single confirmed DOB field). Do not skip ahead to
   `ShapeAll` (any date-shaped field) until Shadow has run long enough
   against `FieldAllowlist` in Active mode to build confidence, per the
   staged-rollout design already decided.

---

## 4. Testing procedure, per mode

| Mode | What to verify |
|---|---|
| **Off** | Every route on the repointed binding behaves identically to hitting Self-Service directly. Diff response headers/bodies for a handful of routes (not just IE) against the direct endpoint. |
| **Shadow** | Submit real-shaped Instant Enrollment traffic (test env, once §2.3 is clear) with a few different DOB shapes — a `Z` morning instant (the bug case), an explicit-offset value, a naive local datetime, an already-bare date, unparseable garbage, and an *afternoon* `Z` instant (should NOT be treated as the bug — afternoon UTC doesn't cross the date boundary the same way). Confirm the Shadow log classifies each correctly and would rewrite ONLY the morning-`Z` case. |
| **Active (FieldAllowlist)** | Submit a real morning-`Z` registration in test, confirm the forwarded request actually carries the corrected date, and confirm (once a full registration completes — see §2.4) the resulting PERSON record in Colleague has the correct DOB. Confirm the gate's rewrite log captures the created record ID from the proxy *response*, not just the request — this is the only correction path available for records with no twin to fuzzy-match against later (see the DOB Repair tool's own findings on why twin-pairing has low yield for this bug). |
| **FailMode=Open check** | Deliberately break the gate (bad config, kill a dependency it needs) and confirm requests still pass through to Self-Service successfully rather than erroring out to the end user. This is the single most important safety property to verify before trusting Active mode with real traffic — an enrollment gate that fails closed is worse than no gate at all. |

---

## 5. Things to watch for

- **YARP request-body rewriting is not an officially supported YARP scenario.**
  Confirmed directly from a YARP maintainer: *"We don't directly support any
  request body transforms, but it's a common thing for people to do
  themselves."* There's a real, version-stamped 2022 report of an HTTP/2
  `PROTOCOL_ERROR` from exactly this — replacing a request body in YARP
  1.0.0 on .NET 6/IIS. AspNetCoreModuleV2 in-process hosting can negotiate
  HTTP/2, so this is a live risk, not a theoretical one. **Mitigation:**
  force HTTP/1.1 on the gate's upstream connection to Self-Service rather
  than allowing HTTP/2 negotiation — confirm this is explicitly configured,
  don't rely on a default. Test this specifically under Shadow/Active, not
  just functionally — a body-rewrite failure could manifest as a dropped or
  malformed request rather than a clean error.
- **Content-Type gate is a silent no-op, not a loud failure.** If Self-
  Service ever changes how it posts this field (a Self-Service version
  upgrade, say) and the Content-Type stops being JSON, the gate does
  nothing and gives no signal that it stopped working. Worth a periodic
  Shadow-mode health check (e.g., confirm the gate is still seeing and
  classifying traffic on the expected path) rather than assuming "no errors"
  means "still working."
- **Don't skip to `ShapeAll` early.** The staged `FieldAllowlist` → `ShapeAll`
  rollout exists specifically to avoid catching a legitimate timestamp field
  that happens to look date-shaped. Move to `ShapeAll` only after a Shadow
  pass under the broader rule shows zero unexpected matches.
- **No dev/sandbox tier exists for this project** — Shadow-mode observability
  against real prod traffic *is* the safety mechanism, not a supplement to
  one. Budget real attention to reading Shadow logs before trusting Active,
  rather than treating Shadow as a formality.
- **Rollback plan**: since this is a repoint, reverting is DNS/binding-level
  — point traffic back at `prod_selfservice` directly and the gate drops out
  of the path entirely with no Self-Service-side changes to undo. Confirm
  this rollback path is actually rehearsed (not just theoretically available)
  before Active mode ever sees prod traffic.

---

## 6. Open items this doc can't resolve for you

- Phase 0 capture status (§2.1) — tell me if this is done; I'll fold the
  actual values into this doc once known.
- D45-Web-API routing (§2.2) — same.
- Whether IE ever updates an existing PERSON's DOB vs. only writes on create
  — doesn't block deployment, but affects how you interpret Shadow-mode
  findings for repeat registrants specifically.

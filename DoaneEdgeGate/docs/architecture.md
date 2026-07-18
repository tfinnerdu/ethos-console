# DoaneEdgeGate - Architecture and Options

A reverse proxy that sits in front of the Colleague Web API and repairs the
Instant Enrollment date-of-birth shift (PD0002124) at the network edge, before
the corrupt value is ever written.

This document lays out the design and every meaningful option so you can pick the
topology and behavior that fit Doane's environment. It is deliberately opinionated
about defaults and explicit about tradeoffs.

---

## 1. What the bug is, and why an edge rewrite fixes it

The Self-Service date picker produces LOCAL MIDNIGHT of the chosen date. Angular
serializes it with `toISOString()`, i.e. as UTC:

    user picks 1980-04-03 in an Eastern browser
    -> local midnight 1980-04-03T00:00:00-04:00
    -> toISOString() -> "1980-04-03T04:00:00Z"

The .NET Colleague Web API then converts that instant back to server-local
(Central) and truncates to a date. For a client east of Central that lands one day
earlier (1980-04-02). The database is not at fault; the day is lost upstream, in
the serialize-then-truncate round trip.

Key insight that makes the edge fix correct and simple: for every timezone at or
behind UTC (all of the United States and the Americas), local midnight converts to
a SAME-DATE morning UTC time. So the date portion of the UTC string is still the
intended calendar date. If we forward the bare date (`1980-04-03`) instead of the
instant, the server has nothing to convert and truncate, so the intended date
survives. No timezone math, no knowledge of the client's zone.

This is exactly what Ellucian's real fix would do (send date-only from the client).
The proxy just does it at the edge until they ship that.

---

## 2. Transform correctness and its one honest limitation

The transform (`DateInstantTransformer`) is the correctness-critical core and is
covered by the test harness. Behavior:

- `1980-04-03T04:00:00Z`  -> `1980-04-03`   (UTC instant, morning: the bug signature)
- `1980-04-03T00:00:00-05:00` -> `1980-04-03` (explicit offset: wall-clock date is local)
- `1980-04-03T00:00:00`   -> `1980-04-03`   (naive local datetime: drop the time)
- `1980-04-03`            -> unchanged        (already date-only: FAIL-SAFE no-op)
- `not a date`, ``, `1980-13-45`, `1980-02-30T04:00:00Z` -> unchanged (never touched)
- `1980-04-03T18:00:00Z`  -> unchanged        (afternoon UTC is not the bug signature; see guard)

Morning-UTC guard (`RequireMorningUtcForZ`, default true): a Z instant that came
from a Western local-midnight origin always has a morning UTC time (midnight plus
a 4-10 hour offset). If the UTC time is noon or later, it did not come from that
origin, so we leave it alone rather than risk shifting a legitimately different
value. Turn the guard off only if you see a real payload that violates this.

The one limitation, stated plainly: a registrant physically in a UTC-AHEAD zone
(Europe, Asia, Australia) at submission time serializes local midnight to the
PREVIOUS UTC date. That value is already one day early before it reaches the proxy,
and a bare `Z` instant carries no offset to recover the client's zone, so we cannot
fix it here. This population is small for Instant Enrollment but real for
international applicants. The only complete fix for that case is the client sending
date-only (the Ellucian fix). Offset-form instants do not have this problem because
they carry the local wall-clock date directly.

Bottom line: this gate is correct for the entire US registrant population, fail-safe
for anything it does not recognize, and a bridge - not a replacement - for the
upstream fix.

---

## 3. Run modes (the master safety switch)

`EdgeGate:Mode` has three values. The intended lifecycle is left to right:

    Off  ->  Shadow  ->  Active

- Off (default): pure passthrough. The gate does nothing; every request is
  forwarded byte-for-byte. Deploy in this mode. Nothing can go wrong.

- Shadow: the transform runs on matched requests, every would-be rewrite is logged
  and counted, but the ORIGINAL body is forwarded unchanged. This lets you validate
  against real production traffic - watch `/api/v1/rewrites/recent` and the
  `shadow_would_rewrite` counter - and confirm the gate would touch exactly the
  right fields and nothing else, before it mutates anything.

- Active: matched requests are rewritten before forwarding.

Do not switch to Active until Phase 0 confirms the payload actually carries a UTC
instant. If Phase 0 shows the browser already sends date-only and the server
mangles it, there is nothing in the body to rewrite and you need a server-side or
Ellucian fix instead. Shadow mode is how you prove the fix is warranted with zero
risk.

**Changing `Mode` (or any other `EdgeGate:*` setting) requires a full app
restart.** Despite ASP.NET Core's config system supporting live reload in
general, this app deliberately does not wire that up (see
docs/production-hardening-plan.md section 3 for why, and what it would take
to change that) — editing appsettings.json or an environment variable while
the process is running has no effect until it's restarted.

---

## 4. OPTION A - Deployment topology

The same binary supports all three. Pick based on where the Web API lives and how
your ops team prefers to run things. On-prem IIS is the primary path for Doane.

### A1. Behind IIS (recommended for Doane)  -  see docs/deployment-iis.md
IIS hosts the proxy via the ASP.NET Core Module (an app/site), and the proxy
forwards to the Colleague Web API. Fits existing Windows ops, certificate handling,
and monitoring. IIS terminates TLS; the proxy can talk HTTP to the Web API on the
same box or over the internal network. This is the least surprising option for a
shop already running IIS.

### A2. Standalone Kestrel service  -  see docs/deployment-standalone.md
Run the proxy as a Windows Service (or console) listening on its own port, with the
Self-Service client or load balancer pointed at it. Simplest mental model, no IIS
module involved. Good for a dedicated proxy host.

### A3. Containerized (Docker / Kubernetes)  -  see docs/deployment-container.md
Only makes sense if the Web API request path can be routed through the container
platform. For an on-prem IIS Web API this usually is not the case, so treat this as
a secondary option. The manifest is provided and caveated. If you do containerize,
route a dedicated host to the proxy WITHOUT prefix-stripping so downstream paths are
preserved.

---

## 5. OPTION B - Which fields to rewrite (RewriteStrategy)

The bug shifts EVERY user-entered date-only field in the Instant Enrollment flow,
not just birth date. Two strategies:

### B1. FieldAllowlist (default)
Only string properties whose name is in `Rewrite:DateFieldNames` are considered.
Surgical and predictable; you know exactly which fields can change. Default names
cover the common DOB spellings. Add any other date-only fields you confirm are
affected. A field in the allowlist that already holds a bare date is left untouched
(fail-safe), so an over-broad list cannot corrupt clean values - it can only fail
to catch a field you forgot.

### B2. ShapeAll
Any string value that matches the ISO-instant signature is considered, regardless
of field name, on matched requests. Catches every shifted date-only field without
maintaining a list. The tradeoff is that it will also rewrite a genuine timestamp
field if one exists on the same endpoint and happens to be a morning-UTC instant.
On the IE person-create endpoint that is unlikely, but review the endpoint's real
payload (Shadow mode is perfect for this) before choosing ShapeAll.

Recommendation: start with FieldAllowlist and the exact field name(s) from Phase 0.
Move to ShapeAll only if you confirm multiple date-only fields shift and you would
rather not track them individually - and only after a Shadow run shows no legitimate
timestamp fields would be caught.

---

## 6. OPTION C - The forwarder (transport)

### C1. Hand-rolled HttpClient forwarder (default, in this build)
Zero third-party dependencies. A single `HttpClient` with a `SocketsHttpHandler`
configured for no auto-redirect (3xx passes through) and no auto-decompression
(bodies pass through as sent). It strips hop-by-hop headers, recomputes length,
preserves Authorization/cookies, and copies the downstream response back verbatim.
This matches the Doane preference for owning the integration surface (the same
reason Ethos calls use a custom HttpClient rather than a vendor SDK). It is small
enough to read in one sitting and fully covered by the forwarder tests.

### C2. YARP (Microsoft.ReverseProxy) - documented swap
YARP is Microsoft's production reverse-proxy library. It handles more transport
edge cases out of the box (connection pooling policies, header transforms,
destination health checks) at the cost of a NuGet dependency. If you would rather
lean on it than maintain the hand-rolled forwarder, the swap is small:

1. Add the package to `src/DoaneEdgeGate/DoaneEdgeGate.csproj`:

       <ItemGroup>
         <PackageReference Include="Yarp.ReverseProxy" Version="2.*" />
       </ItemGroup>

2. In `Program.cs`, register YARP and map it as the terminal instead of the
   hand-rolled forwarder, keeping the rewrite middleware in front of it:

       builder.Services.AddReverseProxy()
           .LoadFromMemory(
               new[] { new RouteConfig { RouteId = "webapi", ClusterId = "webapi",
                   Match = new RouteMatch { Path = "/{**catch-all}" } } },
               new[] { new ClusterConfig { ClusterId = "webapi",
                   Destinations = new Dictionary<string, DestinationConfig> {
                       ["d1"] = new() { Address = opts.Downstream.BaseUrl } } } });
       // ... app.MapReverseProxy();  after the rewrite middleware

The rewrite middleware and the entire Core library are identical either way - the
risky logic does not change. Only the transport swaps.

Recommendation: keep C1 (hand-rolled) unless you hit a transport edge case that YARP
solves for free. The dependency-free build also restores and runs anywhere with no
package feed, which is convenient for a locked-down deploy host.

---

## 7. OPTION D - Fail mode

`Rewrite:FailMode` controls what happens if the rewrite step throws for a matched
request (for example, a body that is not valid JSON):

- Open (default, strongly recommended): forward the ORIGINAL body unchanged and log
  the error. The gate sits in the path of every registration, so a bug in it must
  never be able to drop an enrollment. A missed correction is recoverable by the
  nightly detector; a dropped submission is not.

- Closed: return a 502 with the Doane error shape. Only choose this if silently
  passing a possibly-corrupt date is worse for you than a failed submission. For
  DOB, Open is almost always right.

---

## 8. The synergy with the detector

Every rewrite (and every would-be rewrite in Shadow mode) is logged as structured
JSON and buffered for `/api/v1/rewrites/recent`, carrying the request id, the
original ISO string, and the rewritten date. That record is the pre-shift source of
truth: it captures exactly what the browser sent, keyed to the record, before any
correction. It upgrades the nightly DoaneDOBReconcile detector from "infer the true
date from a twin" to "compare against what they actually typed." Two efforts, one
artifact - the edge gate and the detector reinforce each other.

---

## 9. What this is not

- Not supported by Ellucian. Keep it toggle-able (Mode=Off) so you can bypass it to
  isolate any support case, and expect to remove it to reproduce a vendor defect.
- Not a schema fixer. It only reshapes date-only values that match the bug
  signature; it does not validate or transform anything else.
- Not the destination. The destination is Ellucian sending date-only from the
  client. This gate is the bridge that stops the bleeding until then, and the audit
  trail that helps clean up what already bled.

---

## 10. Endpoints

- `GET /health` - `{ status, service, version, uptime_seconds }`
- `GET /api/v1/status` - mode, strategy, fail mode, match rules, live counters
- `GET /api/v1/rewrites/recent?take=N` - recent rewrite records (audit / validation)

All application errors return `{ error, code, request_id }`. Logs are one JSON
object per line to stdout: timestamp, level, service, request_id, message, fields.

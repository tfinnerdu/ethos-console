# DoaneEdgeGate - IIS Deployment Guide

> **Unresolved conflict, flagged not silently fixed:** this doc says "forward
> with YARP," but the shipped code's default (and only currently-tested)
> transport is the hand-rolled `HttpClient`/`SocketsHttpHandler` forwarder —
> see `DoaneEdgeGate/README.md`'s own recommendation: *"keep the hand-rolled
> forwarder unless you hit a transport edge case that YARP solves for
> free."* No such edge case is documented anywhere in this repo. Separately,
> a deep-research pass done in a different session on this same effort found
> that YARP's own maintainers describe request-body replacement as **not an
> officially supported scenario**, with a real, version-stamped 2022 report
> of an HTTP/2 `PROTOCOL_ERROR` from attempting exactly that. Given the
> hand-rolled forwarder is simpler, dependency-free, and already fully
> covered by the test harness, and given no stated reason favors YARP here,
> **the recommendation is to stay on the hand-rolled forwarder and treat
> this doc's YARP steps (section 2) as not applicable** unless a concrete
> transport limitation shows up that specifically requires it. Confirm this
> before following section 2 below.

Concrete deployment for the decisions made in planning: host behind IIS, forward
with YARP, insert via repoint (not takeover), run FailMode=Open, and roll the field
strategy forward from FieldAllowlist to ShapeAll. This is the actionable version of
the repo's docs/deployment-iis.md with those choices already committed.

Prerequisite: the Phase 0 capture has confirmed the payload carries a morning-UTC
instant, and you have the endpoint path and DOB field name. If Phase 0 has not been
run, do that first (see the Pilot and Phase 0 checklist). Nothing below is worth
doing until the "Z" shape is confirmed.

---

## 1. Host prerequisites

- Windows Server with IIS.
- .NET 8 Hosting Bundle installed (provides the ASP.NET Core Module v2). Install the
  "ASP.NET Core Runtime 8.x - Windows Hosting Bundle", then run `iisreset`.
- On a shared Colleague UI host, confirm the isolation precheck from the pilot doc:
  each environment's Web API URL lives in that environment's own Self-Service config
  (not a shared parent web.config), and each environment has its own app pool.

---

## 2. Add YARP to the build (one time)

The default build ships the hand-rolled forwarder. To use YARP:

1. In `src/DoaneEdgeGate/DoaneEdgeGate.csproj`:

       <ItemGroup>
         <PackageReference Include="Yarp.ReverseProxy" Version="2.*" />
       </ItemGroup>

2. In `Program.cs`, register YARP and map it as the terminal AFTER the rewrite
   middleware. With repoint plus a dedicated host, paths pass through 1:1, so the
   route is a catch-all with a single destination and NO path transform:

       builder.Services.AddReverseProxy()
           .LoadFromMemory(
               new[] { new RouteConfig { RouteId = "webapi", ClusterId = "webapi",
                   Match = new RouteMatch { Path = "/{**catch-all}" } } },
               new[] { new ClusterConfig { ClusterId = "webapi",
                   Destinations = new Dictionary<string, DestinationConfig> {
                       ["d1"] = new() { Address = opts.Downstream.BaseUrl } } } });

       // ... keep the EdgeGate rewrite middleware in front, then:
       app.MapReverseProxy();

   Only add a `PathRemovePrefix` transform if you are forced to hang the gate off a
   path prefix instead of a dedicated host. With a dedicated host you need none.

The rewrite middleware and the entire Core library are unchanged by this swap. Only
the transport changes.

---

## 3. Publish

From the repo root:

    dotnet publish src/DoaneEdgeGate/DoaneEdgeGate.csproj -c Release -o C:\doane\publish\edge-gate-<env>

Publish one output per environment you are wiring (edge-gate-dev, edge-gate-sandbox,
edge-gate-prod). The binary is identical; only configuration differs.

---

## 4. Create the IIS application (per environment)

Do this once per environment. One gate app maps to exactly one downstream Web API so
a config can never cross-wire.

- Point a site or application at C:\doane\publish\edge-gate-<env>.
- Give it its OWN Application Pool, set to "No Managed Code" (the ASP.NET Core Module
  runs the app outside IIS's managed pipeline). A dedicated pool means you can
  recycle or stop the gate without touching any Self-Service or Web API pool.
- Bind HTTPS with the wildcard Doane certificate. IIS terminates TLS; the gate can
  talk HTTP or HTTPS to the Web API.
- Prefer a dedicated host name that mirrors the Web API's path layout (for example
  an <env>-specific DNS name) so downstream paths pass through 1:1.

---

## 5. Configure (per environment)

Settings come from appsettings.json, overridden by environment variables set on the
app pool or in web.config <environmentVariables>. Start every environment dark
(Mode=Off), FailMode=Open, FieldAllowlist with the Phase 0 field name:

    EdgeGate__Mode=Off
    EdgeGate__Downstream__BaseUrl=https://colleague-webapi-<env>.internal.doane.edu
    EdgeGate__Match__Methods__0=POST
    EdgeGate__Match__PathPatterns__0=<person-create path from Phase 0>
    EdgeGate__Rewrite__Strategy=FieldAllowlist
    EdgeGate__Rewrite__DateFieldNames__0=<DOB field name from Phase 0>
    EdgeGate__Rewrite__FailMode=Open
    EdgeGate__Rewrite__RequireMorningUtcForZ=true

FailMode=Open is deliberate and stays Open. This gate is in the path of every
registration; a rewrite bug must forward the original rather than drop an
enrollment. A missed correction is recoverable by DoaneDOBReconcile; a dropped
submission is not.

---

## 6. Repoint and roll out (per environment)

For each environment, in order dev -> sandbox -> prod:

1. Repoint that environment's Self-Service API URL at its gate app.
2. Mode=Off: run an IE registration end to end. Confirm zero behavior change
   (passthrough), and that a CORS preflight (OPTIONS) round-trips.
3. Mode=Shadow: run a registration with a DevTools Eastern timezone override and a
   known DOB. Check GET /api/v1/rewrites/recent - confirm it WOULD rewrite exactly
   the DOB field and nothing else. Check /api/v1/status for shadow_would_rewrite.
4. Mode=Active: re-run, confirm the stored date is correct.

Flip the mode by changing EdgeGate__Mode and recycling the app pool. To bypass the
gate for any support case, set Mode=Off and recycle - one setting, no re-bind.

Prod's Self-Service config is not touched until dev and sandbox have passed.

---

## 7. Field strategy: start FieldAllowlist, then move to ShapeAll

The bug shifts EVERY user-entered date-only field in the IE flow, not just birth
date. Fix the reported, highest-impact field first, then widen the net once you have
proven the widening is safe.

### Phase A - FieldAllowlist (the DOB fix)
- Strategy=FieldAllowlist, DateFieldNames = the exact DOB field from Phase 0.
- This is surgical and provably safe: you know the single field that can change, and
  an already-bare value is left untouched. Run this through Off -> Shadow -> Active
  in each environment (section 6). This resolves the reported defect.

### Phase B - widen to ShapeAll (catch the rest)
Only after Phase A is Active and stable, and only if you want to catch the other
shifted date-only fields (for example a secondary date the applicant enters):

1. Set Strategy=ShapeAll and Mode=Shadow (do NOT jump straight to Active). ShapeAll
   considers any morning-UTC instant on the matched endpoint regardless of field
   name.
2. Run real registrations and inspect GET /api/v1/rewrites/recent carefully. Confirm
   the ONLY values it would rewrite are user-entered date-only fields. If a genuine
   timestamp field exists on that endpoint (a system-set created/modified time, for
   example) and it happens to be a morning-UTC instant, ShapeAll would rewrite it
   too - that is the one risk, and this Shadow pass is how you catch it.
3. If the Shadow pass shows only legitimate date-only fields, set Mode=Active.
   If it shows a timestamp field being caught, stay on FieldAllowlist and instead
   ADD the extra date-only field name(s) to DateFieldNames - you get the coverage
   without the risk.

Recommendation: most orgs are well served staying on FieldAllowlist with an expanded
DateFieldNames list. Reach for ShapeAll only when the set of affected fields is large
or unstable enough that maintaining a list is the bigger burden - and never without
the Shadow pass in step 2.

RequireMorningUtcForZ stays true in both phases: it scopes rewrites to the bug
signature (a Western local-midnight origin serializes to a morning UTC time) and is
the main thing keeping ShapeAll from touching afternoon/evening timestamps.

---

## 8. After any Self-Service or Web API upgrade

This gate is version-fragile by design. A field rename or endpoint move makes it a
silent no-op (fail-safe, but no longer protecting you). After any SS/Web API patch:

- Re-verify Match:PathPatterns and Rewrite:DateFieldNames against a fresh capture.
- Check the rewrite log is still firing on real registrations.
- If the payload shape changed, update config before trusting the gate again.

---

## 9. Rollback

Revert the environment's Self-Service API URL to the real Web API and recycle the
pool. That removes the gate from the path. Because each environment is repointed
independently, a rollback in one never affects another.

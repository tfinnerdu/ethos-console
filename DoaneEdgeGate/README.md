# DoaneEdgeGate

A reverse proxy that repairs the Instant Enrollment date-of-birth shift
(PD0002124) at the network edge - before the corrupt value is written to Colleague.

It matches only the Instant Enrollment person-create request, finds date-only
values that Angular serialized as UTC instants, and forwards the bare date instead.
The server then has nothing to convert-and-truncate, so the date the registrant
picked survives. No timezone math; correct for the entire US registrant population.

See docs/architecture.md for the full design and every option. This README is the
short version.

## Why it is safe to run

- Dark by default. Ships in Mode=Off (pure passthrough). It does nothing until you
  turn it on.
- Fail-safe. A value that is already a bare date is left untouched, so the gate
  becomes an automatic no-op the day Ellucian fixes the client.
- Fail-open (default). If the rewrite ever throws, the original body is forwarded
  unchanged. The gate sits in the path of every registration and must never be able
  to drop an enrollment.
- Observable before active. Mode=Shadow logs and counts every would-be rewrite while
  forwarding the original, so you can validate against real traffic before mutating
  anything.

## Project layout

    src/DoaneEdgeGate.Core/     Pure, dependency-free logic (transform, rewriter, options)
    src/DoaneEdgeGate/          ASP.NET Core web host (middleware, forwarder, endpoints)
    tests/DoaneEdgeGate.Tests/  Dependency-free test harness (Core + in-process HTTP path)
    docs/                       Architecture and deployment guides
    deploy/                     IIS web.config, Dockerfile, K8s manifest

## Quick start (local)

    # from the repo root
    powershell -File start-local.ps1

    # or directly
    dotnet run --project src/DoaneEdgeGate/DoaneEdgeGate.csproj

Then:

    curl http://localhost:5058/health
    curl http://localhost:5058/api/v1/status

By default Mode=Off and Match:PathPatterns is empty, so the gate matches nothing.
Set Downstream:BaseUrl and the IE path pattern (from Phase 0) before it does
anything useful. See appsettings.json and .env.example.

## Run the tests

    dotnet run --project tests/DoaneEdgeGate.Tests/DoaneEdgeGate.Tests.csproj

The harness is intentionally dependency-free so it runs anywhere with no NuGet feed
(the build host for this project has no package access). It covers the pure
transform and rewriter, and exercises the real middleware and forwarder in-process
with no network. In Visual Studio (which has nuget.org) you can port the cases to
xUnit for Test Explorer if you prefer; they map one-to-one.

## Configure

Settings come from appsettings.json and can be overridden by environment variables
(ASP.NET config uses `__` as the section separator). The ones you will actually set:

    EdgeGate__Mode=Off | Shadow | Active
    EdgeGate__Downstream__BaseUrl=https://colleague-webapi.internal.doane.edu
    EdgeGate__Match__PathPatterns__0=/<IE person-create path from Phase 0>
    EdgeGate__Rewrite__Strategy=FieldAllowlist | ShapeAll
    EdgeGate__Rewrite__FailMode=Open | Closed

See .env.example for the full list and docs/architecture.md sections 4-7 for what
each option trades off.

## Rollout (gated)

1. Deploy with Mode=Off. Confirm registrations still work (passthrough).
2. Switch to Shadow. Watch /api/v1/rewrites/recent; confirm it would touch only the
   intended field(s).
3. Only after Phase 0 confirms the payload carries a UTC instant, switch to Active.
4. Verify a test registration (Eastern-spoofed browser, known DOB) stores correctly.

## Deployment

- Behind IIS (primary for Doane): docs/deployment-iis.md
- Standalone Kestrel service: docs/deployment-standalone.md
- Container / Kubernetes (secondary): docs/deployment-container.md

## Relationship to DoaneDOBReconcile

Every rewrite is logged with the original instant and the rewritten date, keyed to
the request. That is the pre-shift source of truth the nightly DoaneDOBReconcile
detector wants: it turns "infer the true date from a twin" into "compare against
what they actually typed." Run both; the gate stops new corruption while the
detector cleans up the backlog.

This is a bridge, not the destination. The destination is Ellucian sending date-only
from the client. Keep the gate toggle-able so you can bypass it for any vendor
support case.

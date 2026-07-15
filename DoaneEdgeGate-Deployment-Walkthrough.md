# DoaneEdgeGate — Deployment Walkthrough

Start-here index for deploying DoaneEdgeGate at Doane. The detailed material already
exists across several files in this repo; this doc sequences them, consolidates the
pre-reqs/watch-outs/test steps the deployer actually asked for, and covers the two
pieces added this session that aren't in any of those other files yet: response
record-ID capture and the ethos-console Health tab tile.

Read in this order:

1. `DoaneEdgeGate/README.md` — what it does, in five minutes.
2. `DoaneEdgeGate/docs/architecture.md` — the bug, the fix, every option and tradeoff.
3. `DoaneEdgeGate-Pilot-and-Phase0.md` — the repoint decision, the isolation precheck,
   and Phase 0 (the go/no-go capture — **do this before anything else below**).
4. `DoaneEdgeGate-IIS-Deployment.md` — the concrete per-environment IIS rollout, with
   the pilot's decisions already applied.
5. `DOB-Repair-Tandem-Flow.md` — how this gate and the DoaneDOBReconcile detector work
   together; read this if you're also running the detector.

This walkthrough does not repeat their content. It's the checklist to work from.

---

## 1. Pre-reqs

- [ ] **Phase 0 has been run and came back "morning-UTC instant."** (`DoaneEdgeGate-Pilot-and-Phase0.md`
      §2.) If Phase 0 shows a bare date already, or a date that's already wrong, this
      gate has nothing to fix — stop and escalate to Ellucian instead of deploying.
- [ ] **Auth model confirmed as bearer/token, not Windows Integrated/Kerberos.**
      (Pilot doc §0.) A Kerberos-authenticated Web API needs a delegation design
      before a proxy can sit in front of it; do not skip this check.
- [ ] **Isolation precheck done**: each environment's Web API URL lives in that
      environment's own Self-Service config (not a shared parent web.config), and each
      environment has its own app pool. (Pilot doc §1.)
- [ ] **Host ready**: Windows Server + IIS, .NET 8 Hosting Bundle installed
      ("ASP.NET Core Runtime 8.x — Windows Hosting Bundle"), `iisreset` run after
      install. (IIS Deployment doc §1.)
- [ ] **A clean binding/port per environment** you're wiring (dev / sandbox / prod get
      separate gate apps — never one gate app shared across environments).
- [ ] **The two Phase 0 values in hand**: the person-create request path, and the DOB
      field name in the JSON body. Nothing below works without these.

## 2. Things to watch for

- **The YARP-vs-hand-rolled forwarder conflict.** `DoaneEdgeGate-IIS-Deployment.md`
  §2 walks through adding YARP, but the code as shipped defaults to (and is only
  tested with) the hand-rolled `HttpClient`/`SocketsHttpHandler` forwarder — see the
  callout now at the top of that file. A separate deep-research pass found YARP's own
  maintainers describe request-body replacement as not an officially supported
  scenario, with a real 2022 HTTP/2 `PROTOCOL_ERROR` report from exactly that use.
  **Stay on the hand-rolled forwarder** (the default) unless a concrete transport
  limitation forces the swap — treat §2 of that doc as optional, not a required step.
- **Version fragility.** This gate matches on an exact path and field name. A
  Self-Service or Web API upgrade that renames the field or moves the endpoint turns
  the gate into a silent no-op — fail-safe (nothing breaks), but no longer protecting
  anyone. Re-run Phase 0 after any such upgrade (`DoaneEdgeGate-IIS-Deployment.md` §8).
- **Sandbox is not optional**, even if dev looks clean — only skip it if dev and prod
  are confirmed on the same Self-Service/Web API build. This gate has bitten people on
  exactly this kind of version drift before (Pilot doc §3).
- **Absolute URLs in the response.** If the person-create response includes any
  absolute URL back to the real Web API (rather than a relative path), a client could
  follow it and bypass the gate entirely. Check for this during the dev Mode=Off pass.
- **FailMode stays Open.** It's the default for a reason: the gate sits in front of
  every registration, and a bug in it must never be able to drop an enrollment. Don't
  flip to Closed without a specific reason that outweighs that.

## 3. What's new this session (not documented elsewhere yet)

### 3a. Response record-ID capture

`EdgeGateOptions.Rewrite.CaptureResponseRecordId` (default `true`) closes the gap
described in `DOB-Repair-Tandem-Flow.md` §5 ("the honest gap: joining a gate log entry
to a Colleague record"). Previously a rewrite log entry could only be joined to the
Colleague record it produced by fuzzy identity matching after the fact. Now, for any
matched request that was rewritten (Active) or would have been rewritten (Shadow),
the gate inspects the downstream Web API's JSON response for a created-record ID
(checking the field names in `Rewrite.ResponseIdFieldNames` — defaults cover `id`,
`personId`, `recordId`, `Id`) and attaches it to that rewrite's `RecentEntry` in
`/api/v1/rewrites/recent`. This is a direct join key, not an inference.

Mechanics, if you need to adjust it:
- Only buffers (instead of streams) the response body when capture is actually
  requested for that request — ordinary passthrough traffic is unaffected.
- Never breaks forwarding: the client always gets the full response back unchanged,
  whether or not an ID was found (`DoaneEdgeGate.Core/ResponseIdExtractor.cs` never
  throws — a non-JSON response, a parse failure, or no matching field name just yields
  no captured ID).
- If your Web API's create-response shape doesn't use any of the default field names,
  add the real one to `Rewrite.ResponseIdFieldNames`.

Test it: run a registration through Active (or Shadow) mode with a known DOB, then
`GET /api/v1/rewrites/recent` and confirm the entry's `CapturedRecordId` matches the
record that was actually created in Colleague.

### 3b. ethos-console Health tab liveness check

The console (this repo's Flask app) now polls the gate's own `GET /health` and
surfaces it as a tile on the console's Health tab (`/health`), independent from and
never blocking the Ethos-related tiles next to it.

- Set `EDGE_GATE_URL` in the console's environment (base URL only, e.g.
  `http://localhost:5058` or `https://edge-gate.internal.doane.edu` — the console
  appends `/health` itself). Leave it unset to show "Not configured" rather than a
  false "down."
- States: **Not configured** (gray, `EDGE_GATE_URL` unset) / **Up** (green, gate
  returned `200 {"status":"ok",...}`) / **Unreachable** (red, no response, timeout, or
  non-2xx).
- This is a liveness signal only — up/down, plus version and uptime from the gate's
  own `/health` payload. It does not report Mode, rewrite counts, or recent rewrites;
  for that, hit the gate's own `/api/v1/status` and `/api/v1/rewrites/recent` directly
  as described in `docs/architecture.md` §10.

## 4. How to test

### 4a. The .NET test harness (before any deploy)

    dotnet run --project DoaneEdgeGate/tests/DoaneEdgeGate.Tests/DoaneEdgeGate.Tests.csproj

Dependency-free by design (runs with no NuGet feed). Covers the transform, the
payload rewriter (both strategies), the middleware + forwarder in-process with no
real network, and — as of this session — the response record-ID capture path
end-to-end (middleware → forwarder → stats) plus `ResponseIdExtractor` directly.

> This repo's sandbox for this session had no .NET SDK and no reachable NuGet/apt
> mirror to install one, so the new capture-flow tests were written and hand-traced
> against the actual method signatures and call sites (confirmed consistent) but were
> **not executed** here. Run the command above yourself before relying on it — it's a
> quick, non-networked check.

### 4b. Functional test sequence (per environment, in order)

This is the same Off → Shadow → Active sequence from the Pilot doc and the IIS
Deployment doc, restated as a single pass/fail checklist:

- [ ] **Mode=Off**: run an IE registration end to end. Passthrough only — confirm zero
      behavior change, and that a CORS preflight (`OPTIONS`) round-trips.
- [ ] **Mode=Shadow**: run a registration with a DevTools Eastern-timezone override and
      a known DOB. `GET /api/v1/rewrites/recent` — confirm it *would* rewrite exactly
      the DOB field (and, with capture on, that a `CapturedRecordId` shows up). Confirm
      `shadow_would_rewrite` incremented on `/api/v1/status`.
- [ ] **Mode=Active**: re-run the same registration. Confirm Colleague stored the
      correct date, and that the console's Health tab tile shows the gate as Up while
      you do all of the above.
- [ ] Repeat dev → sandbox → prod, never skipping a stage (Pilot doc §3, IIS doc §6).

### 4c. Rollback check

Confirm you can revert in under a minute before you need to: set `EdgeGate__Mode=Off`
(or revert the environment's Self-Service API URL to the real Web API) and recycle the
app pool. Because each environment is repointed independently, this never touches
another environment.

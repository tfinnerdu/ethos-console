# DoaneEdgeGate demo — Instant Enrollment stand-in

Two tiny apps for demoing the gate against something other than production.
Neither persists anything or touches Colleague. This mirrors the real repoint
topology (`../DoaneEdgeGate-Pilot-and-Phase0.md` §0) exactly, so the demo
tells the same story as a real deployment:

```
DoaneEdgeGate.Demo.Frontend  --(ApiBaseUrl)-->  DoaneEdgeGate  --(Downstream:BaseUrl)-->  DoaneEdgeGate.Demo.AddPersonApi
      (stands in for Self-Service)                (unchanged)              (stands in for the real Colleague Web API)
```

## The two apps

### `DoaneEdgeGate.Demo.AddPersonApi` — stands in for the Web API

One endpoint, `POST /api/persons`, that persists nothing — it just echoes
back whatever `birthDate` / `timestamp` / `timezone` it received, plus a
fake `id`. That's enough to prove, in the response itself, exactly what
value the "Web API" received — not just what the gate's own logs say it did.

`birthDate` and `id` are already covered by DoaneEdgeGate's own default
`DateFieldNames` / `ResponseIdFieldNames` (see `appsettings.json` in
`src/DoaneEdgeGate`) — no extra gate config needed for those.

Default port: **5065**. CORS is wide open (`AllowAnyOrigin`) since this is
a throwaway local demo, not anything that should ever hold real data.

### `DoaneEdgeGate.Demo.Frontend` — stands in for Self-Service

One page (`wwwroot/index.html`): pick a birth date and a "browser timezone,"
hit submit. The page's JS deliberately reproduces the actual bug —
constructs a `Date` at local midnight in the picked timezone, then
`.toISOString()`s it, which lands on a UTC instant a few hours into the
*morning* of the same day for any zone west of UTC. That's the exact
signature `RequireMorningUtcForZ` checks for. The page shows both the
buggy JSON it sent and the raw response it got back, side by side — no
devtools needed for a live demo.

Where it POSTs to is the **one setting you repoint** — `ApiBaseUrl` in
`appsettings.json` (already defaulted to `http://localhost:5058`, the
gate's own local port). Default port: **5066**.

## Wiring it up locally

1. `dotnet run --project demo/DoaneEdgeGate.Demo.AddPersonApi` (port 5065).
2. Point the gate's `Downstream:BaseUrl` at `http://localhost:5065` (env var
   `EdgeGate__Downstream__BaseUrl`, or `src/DoaneEdgeGate/appsettings.Development.json`
   — remember this is read once at startup, not hot-reloaded) and
   `dotnet run --project src/DoaneEdgeGate` (port 5058).
3. `dotnet run --project demo/DoaneEdgeGate.Demo.Frontend` (port 5066) — its
   default `ApiBaseUrl` already points at step 2's port, so nothing to
   change for a local run.
4. Open `http://localhost:5066`, pick a date + timezone, submit. With the
   gate's default `Mode: Off` you'll see the buggy payload pass straight
   through unchanged. Flip `EdgeGate__Mode=Shadow` (check
   `GET /api/v1/rewrites/recent`) or `Active` (check the "Response" box
   shows the corrected date) to show the fix itself.

## Wiring it up in IIS

Same shape as `../DoaneEdgeGate-IIS-Deployment.md` §4–5: `dotnet publish`
each of these two projects (same command pattern, different project path),
give each its own IIS application + dedicated app pool ("No Managed Code"),
and set:

- `DoaneEdgeGate.Demo.AddPersonApi` — nothing required; it has no config of
  its own beyond the port IIS binds it to.
- `DoaneEdgeGate.Demo.Frontend` — `ApiBaseUrl` (via `web.config`
  `<environmentVariables>`, same pattern as the gate's own
  `deploy/iis/web.config`) pointed at the gate's IIS binding.
- The gate itself — `EdgeGate__Downstream__BaseUrl` pointed at the
  `AddPersonApi` IIS binding.

Nothing here needs HTTPS/a real cert for a local demo — plain HTTP bindings
are fine since none of this ever carries real data.

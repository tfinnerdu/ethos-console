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

One endpoint, `POST /api/persons`, that persists nothing. It echoes back
whatever `birthDate` / `timestamp` / `timezone` it received (`receivedBirthDate`
etc.) plus a fake `id` — enough to prove, in the response itself, exactly
what value the "Web API" received, not just what the gate's own logs say
it did.

It also simulates the *second* half of the real bug, per the doc comment
on `DoaneEdgeGate.Core/DateInstantTransformer.cs`: the browser's local-
midnight-to-UTC serialization alone doesn't lose the date (the date
substring of a morning-UTC instant is still correct) — the day is only
actually lost when the real Colleague Web API converts that instant to
server-local (Central) time and truncates to a date. `storedBirthDate` in
the response reproduces exactly that conversion, so `Mode: Off`/`Shadow`
show the *actually*-corrupted stored date (not just the unmodified wire
value), and `Mode: Active` shows it matching `receivedBirthDate` once the
gate has stripped the field to a bare date before this conversion ever runs.

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
signature `RequireMorningUtcForZ` checks for. The timezone dropdown's last
option sends a bare date instead (no time component at all) — the actual
no-bug control case, since even UTC midnight still gets shifted by the
Web API's own local-time-truncation step (see above) and isn't safe either.
The page shows the buggy JSON it sent and the raw response it got back
side by side — no devtools needed for a live demo.

Where it POSTs to is the **one setting you repoint** — `ApiBaseUrl` in
`appsettings.json` (already defaulted to `http://localhost:5058`, the
gate's own local port). Default port: **5066**.

Every submission shows four results, not just one:

- **Response (actual)** — the real result from actually hitting the gate,
  labeled with whatever mode it reports right now (`GET /api/v1/status`).
- **Would show (Off / Shadow / Active)** — all three computed *instantly*,
  client-side, from the same submission, without touching the server. Each
  mirrors the real gate's rewrite rule (`DateInstantTransformer.cs`'s regex
  and hour check) and the same Central-time-truncation logic as
  `AddPersonApi`'s `storedBirthDate`, using the browser's own IANA timezone
  support instead of .NET's `TimeZoneInfo`. Off and Shadow predict
  identically on purpose (Shadow never mutates what's forwarded).

This means you don't need to flip the gate's `Mode` and resubmit three
times to show the comparison — submit once and all three predictions are
right there. Flipping `Mode` server-side and resubmitting the *same*
payload is still worth doing for a live demo, though: the "actual" box
will end up exactly matching whichever "would" box corresponds to the
mode you switched to, which is a nice, visible proof that the prediction
was right.

This duplicates the C# rewrite logic in JavaScript rather than calling
back into `DoaneEdgeGate.Core`, which does carry a real (if small) drift
risk if `DateInstantTransformer.cs` ever changes — weighed against needing
either a side-channel field to preserve the pre-gate original value past
the real gate's transformation, or a second, gate-bypassing address for
the frontend to call directly. Picked JS for a demo this size; revisit if
this demo grows into something longer-lived than a one-off.

## Wiring it up locally

1. `dotnet run --project demo/DoaneEdgeGate.Demo.AddPersonApi` (port 5065).
2. Point the gate's `Downstream:BaseUrl` at `http://localhost:5065` (env var
   `EdgeGate__Downstream__BaseUrl`, or `src/DoaneEdgeGate/appsettings.Development.json`
   — remember this is read once at startup, not hot-reloaded) and
   `dotnet run --project src/DoaneEdgeGate` (port 5058).
3. `dotnet run --project demo/DoaneEdgeGate.Demo.Frontend` (port 5066) — its
   default `ApiBaseUrl` already points at step 2's port, so nothing to
   change for a local run.
4. Open `http://localhost:5066`, pick a date + timezone, submit. All four
   boxes fill in immediately — "actual" (labeled with the gate's real
   current mode) plus the three "would show" predictions. With the gate's
   default `Mode: Off`, "actual" matches "Would show (Off)" exactly: the
   buggy payload passes straight through, and `storedBirthDate` shows the
   actually-wrong date. Flip `EdgeGate__Mode=Active` server-side, recycle
   the app pool, and resubmit the *same* payload — "actual" now matches
   "Would show (Active)" instead, showing the fix took effect.
   `Mode: Shadow` never shows up as different from Off in any response,
   by design — check `GET /api/v1/rewrites/recent` and
   `shadow_would_rewrite` on `GET /api/v1/status` on the gate itself to see
   Shadow's effect (it only logs what it would have done).

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

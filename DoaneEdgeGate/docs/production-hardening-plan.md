# DoaneEdgeGate — Production Hardening Plan: Logging, Chunked Transfer, Config Reload

Three items carried over from the pre-production review, none of them a quick
patch. This document lays out root cause, options, and a recommendation for
each, so they can be scheduled and reviewed rather than rushed in.

**Standing caveat for this whole document:** there is no .NET SDK anywhere in
the sandbox this plan was written in — nothing below has been compiled or
run. Every recommendation needs a real build-and-test pass before you rely on
it. Where that matters most (chunked transfer), it's called out explicitly.

---

## 1. Logging has no real sink on the primary deployment path

### What's actually happening

`StructuredLog.Write()` (`src/DoaneEdgeGate/StructuredLog.cs`) does exactly
one thing: `Console.WriteLine(JsonSerializer.Serialize(entry))`. The JSON
shape itself is fine — one object per line, matching the Flask/Conductor
logging convention. The problem is what happens to that line after it leaves
`Console.WriteLine`, and it's different in each deployment mode this repo
documents:

- **IIS (`deploy/iis/web.config`) — the deployment this repo calls
  "recommended for Doane" (`docs/architecture.md` §4, A1):**
  `stdoutLogEnabled="false"`. The ASP.NET Core Module (ANCM) only captures a
  process's stdout when this is `true`; with it `false`, every
  `StructuredLog.Info/Warn/Error` call — startup config, every rewrite and
  shadow-rewrite event, every error with its request_id, the one thing this
  gate exists to produce an audit trail of — is written to a stream nobody
  reads, and is gone. **On the recommended deployment, this app currently
  produces no logs at all**, despite `StructuredLog.cs` looking like a
  working structured-logging module.

- **Kubernetes (`deploy/k8s/edge-gate.yaml`) — the secondary/caveated
  path:** fine as-is. Container stdout is captured by the container runtime
  by default and flows into whatever the cluster ships logs to (`kubectl
  logs`, a log aggregator sidecar, etc.). No change needed here for
  correctness, though the recommendation below benefits it too.

- **Standalone Kestrel (`docs/deployment-standalone.md`):** depends entirely
  on how the Windows Service/console process's stdout is redirected by
  whatever supervises it — worth checking against the actual service
  wrapper in use, same failure mode as IIS is possible if stdout isn't
  redirected to a file anywhere.

### Immediate, cheap mitigation (do this regardless of the larger fix below)

Flip IIS's stdout capture on and point it at a real path:

```xml
<aspNetCore processPath="dotnet"
            arguments=".\DoaneEdgeGate.dll"
            stdoutLogEnabled="true"
            stdoutLogFile=".\logs\stdout"
            hostingModel="inprocess">
```

Caveats to know about before treating this as done:
- ANCM creates a new, PID-suffixed file per process start under `.\logs\` —
  it does not rotate or cap size *within* a run. A long-lived worker process
  logging continuously will grow that file unbounded until the next
  recycle/restart. Put a retention/rotation policy on the `logs` folder
  (a scheduled task, or IIS's own app pool recycling schedule) or this
  trades "no logs" for "disk fills up."
- The `logs` directory must exist and the app pool identity must have write
  access to it, or ANCM silently fails to create the log and you're back to
  no logs with no error surfaced anywhere obvious.

This gets logs flowing again with a one-line config change and no code
change. It does not fix the underlying architecture problem below.

### The larger problem: `Console.WriteLine` has no relationship to ASP.NET Core's own logging

Even with stdout capture fixed, `StructuredLog` is a static wrapper with no
connection to `Microsoft.Extensions.Logging` — the logging abstraction
ASP.NET Core itself, and every middleware in the pipeline, already uses.
Concretely, this means:

- **No log-level filtering without a code change.** There's no
  `Logging:LogLevel` config section that does anything, because nothing
  reads one. Turning down noise (or turning up detail to debug an incident)
  means editing `StructuredLog.cs` call sites or redeploying, not editing
  `appsettings.json`.
- **The framework's own diagnostics are invisible.** Kestrel connection
  errors, unhandled exceptions the framework itself catches before
  `ErrorHandlingMiddleware` sees them, ASP.NET Core's request logging — none
  of it goes through `StructuredLog`, so none of it appears in your one
  place for "what did the gate log." You only see what this app's own code
  explicitly chose to log.
- **No path to a real sink later without touching every call site.** Seq,
  Application Insights, Windows Event Log, a rolling file provider — every
  one of them is an `ILogger` provider. Bolting any of them on today means
  either wrapping `Console.WriteLine`'s output externally (fragile, lossy)
  or rewriting every `StructuredLog.Info(...)` call.

### Recommended fix

Route `StructuredLog` through `ILogger` instead of `Console.WriteLine`,
keeping the same static call-site API so the ~20+ existing call sites don't
need to change:

1. Add a custom `ILoggerProvider`/`ILogger` (or a small
   `Microsoft.Extensions.Logging.Console` custom formatter) that emits
   *exactly* the same JSON-line shape `StructuredLog.Write` produces today —
   this is the part that matters for not breaking whatever already parses
   these logs downstream. A custom `ConsoleFormatter` is the least invasive
   option: it plugs into the existing `AddConsole()` pipeline and ANCM's
   stdout capture keeps working unchanged.
2. In `Program.cs`, build an `ILogger` from `builder.Logging` /
   `app.Services.GetRequiredService<ILoggerFactory>()` once at startup and
   hand it to `StructuredLog` (a settable static field, or a small
   `StructuredLog.Initialize(ILogger logger)` called once in `Program.cs`
   right after `var app = builder.Build();`).
3. Change `StructuredLog.Write` to call `_logger.Log(level, "{Message}
   {Fields}", ...)` (or similar) instead of `Console.WriteLine`, formatted by
   the custom formatter from step 1 into the same JSON shape.
4. Now `appsettings.json`'s standard `Logging:LogLevel` section controls
   verbosity with no code change, and adding a second/replacement sink later
   (rolling file, Seq, Application Insights) is `builder.Logging.AddXxx()`
   in `Program.cs` — zero call-site churn.

This is a contained, mechanical refactor (one file's internals change; call
sites don't) but it touches the app's only observability path, so it needs
real testing against a running instance — verify the JSON shape is
byte-for-byte compatible with what downstream log consumers expect before
cutting over, and verify IIS stdout capture (or whatever `ILogger` provider
you choose) actually receives the output end to end.

---

## 2. Chunked Transfer-Encoding — unverified, not a confirmed bug

Being direct about the confidence level here: re-reading
`HttpClientForwarder.cs` and `EdgeGateMiddleware.cs` closely, nothing jumps
out as an obvious, confirmed defect — but this can't be verified without
compiling and running the app against a real chunked exchange, which wasn't
possible in this environment. Treat this section as "needs a test," not "here
is the bug and the fix."

**Request side (client → gate):** `EdgeGateMiddleware.ReadBodyAsync` and
`HttpClientForwarder`'s `new StreamContent(req.Body)` both operate on
`HttpContext.Request.Body` as a plain stream. Kestrel de-chunks an incoming
`Transfer-Encoding: chunked` request transparently at the HTTP layer before
the app ever sees it, so this should be fine regardless of how the original
client framed the request. Low concern.

**Response side (downstream → gate → client), the part worth actually
testing:** `HttpClientForwarder.cs` line ~87 explicitly does
`context.Response.Headers.Remove("transfer-encoding")` with the comment "let
Kestrel set the length/encoding for the copied stream," combined with
`HttpCompletionOption.ResponseHeadersRead` (streaming, not buffering) and
`response.Content.CopyToAsync(context.Response.Body, ...)`. If the Colleague
Web API ever responds with `Transfer-Encoding: chunked` (no `Content-Length`
— plausible for a large or dynamically-generated response), this is relying
on Kestrel's own default behavior (auto-chunking the outbound response when
no length is set) to reproduce equivalent framing to the client. That's
standard, well-supported ASP.NET Core behavior, not exotic — but "should
work by default" and "verified to work against this specific downstream" are
different claims, and only the second one is trustworthy enough to ship on.

### Recommended verification (before treating this as settled either way)

1. Stand up a minimal stub downstream service (even a 5-line ASP.NET Core
   `WebApplication` or a `HttpListener` script) that responds to the IE
   person-create path with `Transfer-Encoding: chunked` and no
   `Content-Length`, streaming a known payload in multiple chunks.
2. Point `DoaneEdgeGate:Downstream:BaseUrl` at that stub, send a request
   through the gate in `Off` mode (pure passthrough — isolates transport
   from the rewrite logic) and confirm the client receives the complete,
   correctly-framed body.
3. Repeat with the gate in `Active` mode against a matched path, to confirm
   the rewrite path's `captureResponseId` buffering branch (which reads the
   full body via `ReadAsByteArrayAsync`) also handles a chunked response
   correctly — this is actually a different code path (buffers rather than
   streams) and needs its own check.
4. Separately, send a request *to* the gate using `Transfer-Encoding:
   chunked` (curl's `-H "Transfer-Encoding: chunked"` or a client that
   naturally streams without a known length) and confirm it's forwarded
   correctly on the request side too, closing out the lower-concern
   direction with actual evidence instead of an inference from reading the
   code.

If step 2 or 3 fails, the fix is almost certainly in
`HttpClientForwarder.ForwardAsync` — either not stripping
`transfer-encoding` from the response copy, or handling the
`captureResponseId` buffering branch's content-length assumptions
differently. But that's a hypothesis to go test, not a diagnosis to
implement against.

---

## 3. `Rewrite:*` config does not hot-reload, despite looking like it might

### Root cause

`Program.cs`:

```csharp
var opts = builder.Configuration.GetSection(EdgeGateOptions.SectionName).Get<EdgeGateOptions>() ?? new EdgeGateOptions();
builder.Services.Configure<EdgeGateOptions>(builder.Configuration.GetSection(EdgeGateOptions.SectionName));
builder.Services.AddSingleton(new PayloadRewriter(opts.Rewrite));
```

`opts` is a **one-time snapshot**, taken once at startup via `.Get<T>()`.
`PayloadRewriter` — the class that actually applies `Rewrite:Strategy`,
`Rewrite:DateFieldNames`, `Rewrite:RequireMorningUtcForZ`, etc. on every
matched request — is a singleton built from that snapshot in its
constructor (`PayloadRewriter.cs`, `_opts` field). It never looks at
`IConfiguration` again after the app starts.

Separately, `builder.Services.Configure<EdgeGateOptions>(...)` wires up the
options system's `IOptions<EdgeGateOptions>`, which the inline management
middleware in `Program.cs` resolves per-request
(`ctx.RequestServices.GetRequiredService<IOptions<EdgeGateOptions>>().Value`)
to answer `GET /api/v1/status`. This *looks* live because it's resolved
fresh on every request, but `IOptions<T>` is documented to cache its value
for the app's lifetime regardless of underlying config changes — only
`IOptionsSnapshot<T>` (per-request, for scoped/request-based reloading) or
`IOptionsMonitor<T>` (singleton-safe, with an actual `OnChange` callback)
reflect a live `IConfiguration` reload. Since ASP.NET Core's JSON config
provider defaults to `reloadOnChange: true`, editing `appsettings.json`'s
`EdgeGate:Rewrite:*` values while the app is running silently does nothing —
not just to `PayloadRewriter` (expected, it's a plain snapshotted object) but
also to `/api/v1/status`'s reported values (which look like they should be
live, since they're resolved per-request, but aren't). The status endpoint
isn't lying — it's self-consistent with what `PayloadRewriter` is actually
doing — but an operator watching `/api/v1/status` after editing config and
seeing no change has no way to tell "this needs a restart" from "my edit
didn't save" without reading this code.

### This is a decision, not just a bug

Before picking a fix, it's worth deciding what behavior you actually want,
because there's a real tradeoff and this is a safety-critical mode switch
(`docs/architecture.md` calls `Mode` "the master safety switch," with an
intentional Off → Shadow → Active lifecycle):

- **Option A — wire up real hot-reload.** Convenient: tune
  `DateFieldNames`, flip `Mode`/`FailMode`/`Strategy` without a redeploy.
  Downside: a config edit takes effect mid-flight, potentially mid-way
  through a burst of enrollment submissions, with no restart boundary to
  reason about. For `Mode` specifically (the Off/Shadow/Active safety
  switch), an operator might prefer a deliberate restart as a forcing
  function — "I confirmed the new config is what's now running" — rather
  than trusting that a file edit landed correctly.

- **Option B — keep it static, but document and surface it honestly.**
  Cheaper and arguably safer for a component in the path of every
  enrollment: `Rewrite:*` (and `Mode`) changes require a restart, full stop.
  The fix here is just documentation plus maybe a comment in
  `appsettings.json` itself — no code change, no new risk introduced.

**Recommendation: Option B**, specifically because of what this gate does.
The existing Off → Shadow → Active discipline in `architecture.md` already
treats mode changes as deliberate, verified steps, not something to flip
casually — a restart-required config model reinforces that discipline
instead of fighting it. If the team later finds itself wanting to tune
`DateFieldNames` frequently enough that restarts become genuinely annoying,
revisit with Option A then, informed by real operational experience rather
than a guess made now.

### If Option B (recommended): what to actually do

No code change. Add a clear note to `appsettings.json` next to the
`EdgeGate` section and to `docs/architecture.md`'s options list stating that
every `EdgeGate:*` value (not just `Rewrite:*`) requires a full app restart
to take effect, despite ASP.NET Core's config system supporting live reload
in general — because this app deliberately does not wire that up for this
section.

### If Option A: the concrete fix

1. Change `PayloadRewriter`'s constructor to accept
   `IOptionsMonitor<EdgeGateOptions>` instead of a snapshotted
   `RewriteOptions`, and read `_optionsMonitor.CurrentValue.Rewrite` at the
   top of `Rewrite(...)` on every call instead of using a field captured at
   construction time.
2. In `Program.cs`, register `PayloadRewriter` via
   `builder.Services.AddSingleton<PayloadRewriter>()` (letting DI inject
   `IOptionsMonitor<EdgeGateOptions>`) instead of `new PayloadRewriter(opts.Rewrite)`.
3. Change the inline management middleware's
   `GetRequiredService<IOptions<EdgeGateOptions>>()` to
   `IOptionsMonitor<EdgeGateOptions>` and read `.CurrentValue` — small change,
   makes `/api/v1/status` actually live instead of just looking like it is.
4. Test explicitly: start the app, hit `/api/v1/status`, edit
   `appsettings.json`'s `EdgeGate:Rewrite:DateFieldNames`, wait a moment
   (the file watcher has a debounce), hit `/api/v1/status` again and confirm
   the new list is reflected — then confirm a live request actually uses the
   new field list, not just that the status endpoint reports it.
5. Decide whether `Mode` itself should be included in this live-reload path
   or deliberately excluded (kept restart-only) even if the rest of
   `Rewrite:*` becomes hot-reloadable — a hybrid is legitimate: tunable
   detail (field names, thresholds) live, the safety-switch (`Mode`) static.

---

## Suggested sequencing

1. **Now, cheap, no code change:** flip `stdoutLogEnabled="true"` in
   `deploy/iis/web.config` with a retention plan for the log folder. Closes
   the "no logs at all on the recommended deployment" gap immediately.
2. **Before the next feature work on this repo:** the `ILogger` migration
   (§1's larger fix) — it's the dependency for doing anything better with
   logs later, and it's contained to `StructuredLog.cs` + a few lines of
   `Program.cs`.
3. **Before trusting this against a downstream that might actually chunk
   responses:** run the §2 verification. If your Colleague Web API
   deployment is known to never send chunked responses (common for smaller
   JSON payloads with Content-Length known upfront), this can be
   deprioritized — but confirm that assumption rather than assuming it.
4. **§3 is a documentation-only change if you take the recommended Option
   B** — cheap, do it whenever, no reason to delay.

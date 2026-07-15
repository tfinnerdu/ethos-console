using System.Linq;
using System.Net;
using System.Text;
using DoaneEdgeGate;
using DoaneEdgeGate.Core;
using DoaneEdgeGate.Forwarding;
using DoaneEdgeGate.Middleware;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Options;

/// <summary>
/// Exercises the real EdgeGateMiddleware and HttpClientForwarder in-process. No
/// sockets are opened: the middleware talks to a capturing fake forwarder, and the
/// forwarder talks to a stub HttpMessageHandler. Same code paths that run in
/// production, verified without a live server.
/// </summary>
static class IntegrationChecks
{
    private const string Dob = "{\"birthDate\":\"1980-04-03T04:00:00Z\",\"firstName\":\"Ann\"}";

    public static async Task Run(Harness t)
    {
        await MiddlewareChecks(t);
        await ForwarderChecks(t);
    }

    // ---- middleware ----

    private sealed class FakeForwarder : IPayloadForwarder
    {
        public bool Called;
        public byte[]? SentOverride;
        public bool OverrideWasNull;
        public bool CaptureRequested;
        public string? IdToReturn;

        public Task<string?> ForwardAsync(HttpContext context, byte[]? bodyOverride, string requestId, bool captureResponseId = false)
        {
            Called = true;
            SentOverride = bodyOverride;
            OverrideWasNull = bodyOverride is null;
            CaptureRequested = captureResponseId;
            return Task.FromResult(captureResponseId ? IdToReturn : null);
        }
    }

    private static HttpContext Ctx(string method, string path, string? contentType, string? body, string query = "")
    {
        var ctx = new DefaultHttpContext();
        ctx.Items["request_id"] = "test-rid";
        ctx.Request.Method = method;
        ctx.Request.Path = path;
        if (query.Length > 0) ctx.Request.QueryString = new QueryString(query);
        if (contentType != null) ctx.Request.ContentType = contentType;
        if (body != null)
        {
            var b = Encoding.UTF8.GetBytes(body);
            ctx.Request.Body = new MemoryStream(b);
            ctx.Request.ContentLength = b.Length;
        }
        ctx.Response.Body = new MemoryStream();
        return ctx;
    }

    private static EdgeGateOptions Opts(RewriteMode mode, FailMode fail = FailMode.Open,
        RewriteStrategy strat = RewriteStrategy.FieldAllowlist)
    {
        var o = new EdgeGateOptions { Mode = mode };
        o.Match.Methods = new() { "POST", "PUT" };
        o.Match.PathPatterns = new() { "/webapi/enroll" };
        o.Rewrite.Strategy = strat;
        o.Rewrite.FailMode = fail;
        return o;
    }

    private static EdgeGateMiddleware Mw(EdgeGateOptions o, FakeForwarder fwd) =>
        Mw(o, fwd, out _);

    private static EdgeGateMiddleware Mw(EdgeGateOptions o, FakeForwarder fwd, out RewriteStats stats)
    {
        stats = new RewriteStats(o.Rewrite.RecentBufferSize);
        return new(Options.Create(o), fwd, new PayloadRewriter(o.Rewrite), stats);
    }

    private static string Sent(FakeForwarder f) =>
        f.SentOverride != null ? Encoding.UTF8.GetString(f.SentOverride) : "";

    private static async Task MiddlewareChecks(Harness t)
    {
        {   // Active + matched -> rewritten body forwarded
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active), f).InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            var s = Sent(f);
            t.Check("mw Active/matched: rewritten bare date forwarded",
                f.Called && s.Contains("1980-04-03") && !s.Contains("T04:00:00Z"), $"sent='{s}'");
        }
        {   // Active + already-bare -> no-op, original forwarded
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active), f).InvokeAsync(
                Ctx("POST", "/webapi/enroll", "application/json", "{\"birthDate\":\"1980-04-03\"}"));
            var s = Sent(f);
            t.Check("mw Active/already-bare: no-op forwarded",
                f.Called && s.Contains("1980-04-03") && !s.Contains("T"), $"sent='{s}'");
        }
        {   // Shadow + matched -> ORIGINAL forwarded (not mutated)
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Shadow), f).InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            var s = Sent(f);
            t.Check("mw Shadow/matched: original forwarded, not mutated",
                f.Called && s.Contains("T04:00:00Z"), $"sent='{s}'");
        }
        {   // Off -> pure passthrough (streamed, no override)
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Off), f).InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            t.Check("mw Off: pure passthrough (stream, no override)", f.Called && f.OverrideWasNull);
        }
        {   // non-matching path -> passthrough
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active), f).InvokeAsync(Ctx("POST", "/webapi/other", "application/json", Dob));
            t.Check("mw non-matching path: passthrough", f.Called && f.OverrideWasNull);
        }
        {   // non-JSON content-type -> skipped, passthrough
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active), f).InvokeAsync(Ctx("POST", "/webapi/enroll", "text/plain", Dob));
            t.Check("mw non-JSON: skipped, passthrough", f.Called && f.OverrideWasNull);
        }
        {   // malformed JSON + FailMode.Open -> fail-open, original forwarded
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active, FailMode.Open), f).InvokeAsync(
                Ctx("POST", "/webapi/enroll", "application/json", "{bad json"));
            var s = Sent(f);
            t.Check("mw fail-open: malformed body forwarded unchanged (never drops enrollment)",
                f.Called && s.Contains("{bad json"), $"sent='{s}' overrideNull={f.OverrideWasNull}");
        }
        {   // malformed JSON + FailMode.Closed -> 502, no forward
            var f = new FakeForwarder();
            var ctx = Ctx("POST", "/webapi/enroll", "application/json", "{bad json");
            await Mw(Opts(RewriteMode.Active, FailMode.Closed), f).InvokeAsync(ctx);
            t.Check("mw fail-closed: 502 returned and nothing forwarded",
                !f.Called && ctx.Response.StatusCode == 502, $"called={f.Called} status={ctx.Response.StatusCode}");
        }
        {   // ShapeAll -> non-DOB date field rewritten too
            var f = new FakeForwarder();
            await Mw(Opts(RewriteMode.Active, FailMode.Open, RewriteStrategy.ShapeAll), f).InvokeAsync(
                Ctx("POST", "/webapi/enroll", "application/json", "{\"enrollDate\":\"2025-09-02T04:00:00Z\"}"));
            var s = Sent(f);
            t.Check("mw ShapeAll: non-DOB date field also rewritten",
                s.Contains("2025-09-02") && !s.Contains("T04:00:00Z"), $"sent='{s}'");
        }

        // ---- response record-ID capture (DOB-Repair-Tandem-Flow.md section 5) ----
        {   // Active + changed -> capture requested, and the ID the forwarder
            // hands back ends up on the stats entry the middleware records.
            var f = new FakeForwarder { IdToReturn = "12345" };
            var o = Opts(RewriteMode.Active);
            var mw = Mw(o, f, out var stats);
            await mw.InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            var entry = stats.Recent(1).FirstOrDefault();
            t.Check("mw Active/changed: capture requested from forwarder",
                f.CaptureRequested, $"captureRequested={f.CaptureRequested}");
            t.Check("mw Active/changed: captured record id lands on stats entry",
                entry != null && entry.CapturedRecordId == "12345",
                $"entry={entry?.CapturedRecordId ?? "null"}");
        }
        {   // Active + unchanged (already-bare) -> no capture requested
            var f = new FakeForwarder { IdToReturn = "12345" };
            await Mw(Opts(RewriteMode.Active), f).InvokeAsync(
                Ctx("POST", "/webapi/enroll", "application/json", "{\"birthDate\":\"1980-04-03\"}"));
            t.Check("mw Active/unchanged: no capture requested (nothing to join)",
                !f.CaptureRequested, $"captureRequested={f.CaptureRequested}");
        }
        {   // Shadow + changed -> capture is still requested (Shadow observes
            // what Active would have produced, including the downstream id).
            var f = new FakeForwarder { IdToReturn = "67890" };
            var o = Opts(RewriteMode.Shadow);
            var mw = Mw(o, f, out var stats);
            await mw.InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            var entry = stats.Recent(1).FirstOrDefault();
            t.Check("mw Shadow/changed: capture requested",
                f.CaptureRequested, $"captureRequested={f.CaptureRequested}");
            t.Check("mw Shadow/changed: captured record id lands on stats entry",
                entry != null && entry.CapturedRecordId == "67890",
                $"entry={entry?.CapturedRecordId ?? "null"}");
        }
        {   // CaptureResponseRecordId=false -> never requested, even when changed
            var f = new FakeForwarder { IdToReturn = "12345" };
            var o = Opts(RewriteMode.Active);
            o.Rewrite.CaptureResponseRecordId = false;
            await Mw(o, f).InvokeAsync(Ctx("POST", "/webapi/enroll", "application/json", Dob));
            t.Check("mw CaptureResponseRecordId=false: never requested",
                !f.CaptureRequested, $"captureRequested={f.CaptureRequested}");
        }
    }

    // ---- forwarder ----

    private sealed class StubHandler : HttpMessageHandler
    {
        public HttpRequestMessage? Captured;
        public byte[]? CapturedBody;

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            Captured = request;
            if (request.Content != null) CapturedBody = await request.Content.ReadAsByteArrayAsync(ct);
            return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("downstream-ok") };
        }
    }

    private static async Task ForwarderChecks(Harness t)
    {
        var o = new EdgeGateOptions();
        o.Downstream.BaseUrl = "http://downstream.local:9099";
        var stub = new StubHandler();
        var fwd = new HttpClientForwarder(new HttpClient(stub), Options.Create(o));

        var ctx = Ctx("POST", "/webapi/enroll", "application/json", null, "?x=1");
        ctx.Request.Headers["Authorization"] = "Bearer abc";
        ctx.Request.Headers["Connection"] = "keep-alive";
        await fwd.ForwardAsync(ctx, Encoding.UTF8.GetBytes("BODY"), "rid");

        t.Check("fwd target URL = base + path + query",
            stub.Captured?.RequestUri?.ToString() == "http://downstream.local:9099/webapi/enroll?x=1",
            stub.Captured?.RequestUri?.ToString() ?? "null");
        t.Check("fwd sends body override",
            stub.CapturedBody != null && Encoding.UTF8.GetString(stub.CapturedBody) == "BODY");
        t.Check("fwd preserves Authorization header",
            stub.Captured != null && stub.Captured.Headers.Contains("Authorization"));
        t.Check("fwd strips hop-by-hop Connection header",
            stub.Captured != null && !stub.Captured.Headers.Contains("Connection"));

        ctx.Response.Body.Position = 0;
        var respText = await new StreamReader(ctx.Response.Body).ReadToEndAsync();
        t.Check("fwd copies downstream response back to client",
            respText.Contains("downstream-ok") && ctx.Response.StatusCode == 200,
            $"resp='{respText}' status={ctx.Response.StatusCode}");

        // ---- response record-ID capture ----
        {
            var jsonStub = new JsonStubHandler("""{"id":"999","firstName":"Ann"}""");
            var jsonFwd = new HttpClientForwarder(new HttpClient(jsonStub), Options.Create(o));
            var jsonCtx = Ctx("POST", "/webapi/enroll", "application/json", null);
            var id = await jsonFwd.ForwardAsync(jsonCtx, Encoding.UTF8.GetBytes("BODY"), "rid", captureResponseId: true);

            t.Check("fwd capture: extracts id from JSON response", id == "999", $"id='{id}'");

            jsonCtx.Response.Body.Position = 0;
            var jsonRespText = await new StreamReader(jsonCtx.Response.Body).ReadToEndAsync();
            t.Check("fwd capture: client still receives the full response body unchanged",
                jsonRespText.Contains("\"id\":\"999\"") && jsonRespText.Contains("Ann"), $"resp='{jsonRespText}'");
        }
        {   // captureResponseId=false -> never buffers/extracts, even for a JSON response with a matching field
            var jsonStub = new JsonStubHandler("""{"id":"999"}""");
            var jsonFwd = new HttpClientForwarder(new HttpClient(jsonStub), Options.Create(o));
            var jsonCtx = Ctx("POST", "/webapi/enroll", "application/json", null);
            var id = await jsonFwd.ForwardAsync(jsonCtx, Encoding.UTF8.GetBytes("BODY"), "rid", captureResponseId: false);

            t.Check("fwd capture not requested: returns null even though field is present", id == null, $"id='{id ?? "null"}'");
        }
        {   // non-JSON response -> capture requested but nothing to extract, still returns null
            var textStub = new StubHandler();
            var textFwd = new HttpClientForwarder(new HttpClient(textStub), Options.Create(o));
            var textCtx = Ctx("POST", "/webapi/enroll", "application/json", null);
            var id = await textFwd.ForwardAsync(textCtx, Encoding.UTF8.GetBytes("BODY"), "rid", captureResponseId: true);

            t.Check("fwd capture on non-JSON response: null, no crash", id == null, $"id='{id ?? "null"}'");
        }
    }

    private sealed class JsonStubHandler : HttpMessageHandler
    {
        private readonly string _json;
        public JsonStubHandler(string json) => _json = json;

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            var resp = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(_json, Encoding.UTF8, "application/json")
            };
            return Task.FromResult(resp);
        }
    }
}

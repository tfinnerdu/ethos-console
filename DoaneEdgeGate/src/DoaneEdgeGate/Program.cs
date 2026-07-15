using System.Net;
using System.Text.Json;
using DoaneEdgeGate;
using DoaneEdgeGate.Core;
using DoaneEdgeGate.Forwarding;
using DoaneEdgeGate.Middleware;

const string Version = "1.0.0";

var builder = WebApplication.CreateBuilder(args);

// Bound options snapshot (used for singletons whose shape does not hot-reload).
var opts = builder.Configuration.GetSection(EdgeGateOptions.SectionName).Get<EdgeGateOptions>() ?? new EdgeGateOptions();

builder.Services.Configure<EdgeGateOptions>(builder.Configuration.GetSection(EdgeGateOptions.SectionName));
builder.Services.AddSingleton(new PayloadRewriter(opts.Rewrite));
builder.Services.AddSingleton(new RewriteStats(opts.Rewrite.RecentBufferSize));
builder.Services.AddTransient<EdgeGateMiddleware>();

// Hand-rolled forwarder. No auto-redirect (3xx passes through), no auto-decompress
// (bodies pass through as sent).
builder.Services
    .AddHttpClient<IPayloadForwarder, HttpClientForwarder>()
    .ConfigurePrimaryHttpMessageHandler(() => new SocketsHttpHandler
    {
        AllowAutoRedirect = false,
        AutomaticDecompression = DecompressionMethods.None
    });

var app = builder.Build();

StructuredLog.Info("edge gate starting", fields: new Dictionary<string, object?>
{
    ["version"] = Version,
    ["mode"] = opts.Mode.ToString(),
    ["strategy"] = opts.Rewrite.Strategy.ToString(),
    ["fail_mode"] = opts.Rewrite.FailMode.ToString(),
    ["downstream"] = opts.Downstream.BaseUrl,
    ["path_patterns"] = opts.Match.PathPatterns
});

app.UseMiddleware<ErrorHandlingMiddleware>();
app.UseMiddleware<RequestIdMiddleware>();

// Local management endpoints are handled here and never forwarded downstream.
app.Use(async (ctx, next) =>
{
    var path = ctx.Request.Path;
    var stats = ctx.RequestServices.GetRequiredService<RewriteStats>();
    var o = ctx.RequestServices.GetRequiredService<Microsoft.Extensions.Options.IOptions<EdgeGateOptions>>().Value;
    var uptime = (long)(DateTimeOffset.UtcNow - stats.StartedUtc).TotalSeconds;

    if (HttpMethods.IsGet(ctx.Request.Method) && path == "/health")
    {
        await WriteJson(ctx, 200, new { status = "ok", service = StructuredLog.Service, version = Version, uptime_seconds = uptime });
        return;
    }

    if (HttpMethods.IsGet(ctx.Request.Method) && path == "/api/v1/status")
    {
        await WriteJson(ctx, 200, new
        {
            service = StructuredLog.Service,
            version = Version,
            mode = o.Mode.ToString(),
            strategy = o.Rewrite.Strategy.ToString(),
            fail_mode = o.Rewrite.FailMode.ToString(),
            require_morning_utc_for_z = o.Rewrite.RequireMorningUtcForZ,
            downstream = o.Downstream.BaseUrl,
            match = new { methods = o.Match.Methods, path_patterns = o.Match.PathPatterns },
            counters = new
            {
                matched = stats.Matched,
                rewritten_requests = stats.RewrittenRequests,
                shadow_would_rewrite = stats.ShadowWouldRewrite,
                field_rewrites = stats.FieldRewrites,
                errors = stats.Errors,
                skipped = stats.Skipped
            },
            uptime_seconds = uptime
        });
        return;
    }

    if (HttpMethods.IsGet(ctx.Request.Method) && path == "/api/v1/rewrites/recent")
    {
        var take = 50;
        if (ctx.Request.Query.TryGetValue("take", out var tv) && int.TryParse(tv, out var parsed))
            take = Math.Clamp(parsed, 1, 1000);
        await WriteJson(ctx, 200, new { count = stats.Recent(take).Count, items = stats.Recent(take) });
        return;
    }

    await next();
});

// Everything else is proxied.
app.Run(async ctx =>
{
    var mw = ctx.RequestServices.GetRequiredService<EdgeGateMiddleware>();
    await mw.InvokeAsync(ctx);
});

app.Run();

static async Task WriteJson(HttpContext ctx, int status, object body)
{
    ctx.Response.StatusCode = status;
    ctx.Response.ContentType = "application/json";
    await ctx.Response.WriteAsync(JsonSerializer.Serialize(body,
        new JsonSerializerOptions { PropertyNamingPolicy = null }));
}

// Exposed for the test/integration harness.
public partial class Program { }

using System.Text.Json;
using DoaneEdgeGate.Forwarding;

namespace DoaneEdgeGate.Middleware;

/// <summary>
/// Catches unhandled exceptions and returns the Doane standard error shape
/// { error, code, request_id }. A downstream transport failure becomes 502; any
/// other unhandled error becomes 500.
/// </summary>
public sealed class ErrorHandlingMiddleware
{
    private readonly RequestDelegate _next;

    public ErrorHandlingMiddleware(RequestDelegate next) => _next = next;

    public async Task InvokeAsync(HttpContext context)
    {
        var rid = context.Items.TryGetValue("request_id", out var r) ? r?.ToString() ?? "" : "";
        try
        {
            await _next(context);
        }
        catch (DownstreamException ex)
        {
            StructuredLog.Error("downstream forward failed", rid,
                new Dictionary<string, object?> { ["error"] = ex.Message, ["inner"] = ex.InnerException?.Message });
            await Write(context, 502, "downstream_unavailable", rid);
        }
        catch (Exception ex)
        {
            StructuredLog.Error("unhandled error", rid,
                new Dictionary<string, object?> { ["error"] = ex.Message });
            await Write(context, 500, "internal_error", rid);
        }
    }

    private static async Task Write(HttpContext context, int status, string code, string rid)
    {
        if (context.Response.HasStarted) return;
        context.Response.Clear();
        context.Response.StatusCode = status;
        context.Response.ContentType = "application/json";
        var payload = JsonSerializer.Serialize(new
        {
            error = code == "downstream_unavailable"
                ? "the downstream Colleague Web API could not be reached"
                : "the edge gate hit an unexpected error",
            code,
            request_id = rid
        });
        await context.Response.WriteAsync(payload);
    }
}

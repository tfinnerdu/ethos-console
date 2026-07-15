namespace DoaneEdgeGate.Middleware;

/// <summary>
/// Ensures every request carries a request_id: honors an inbound X-Request-Id if
/// present, otherwise mints one. Stored in HttpContext.Items and echoed on the
/// response so it threads through logs and the error shape.
/// </summary>
public sealed class RequestIdMiddleware
{
    private const string Header = "X-Request-Id";
    private readonly RequestDelegate _next;

    public RequestIdMiddleware(RequestDelegate next) => _next = next;

    public async Task InvokeAsync(HttpContext context)
    {
        var incoming = context.Request.Headers[Header].FirstOrDefault();
        var rid = string.IsNullOrWhiteSpace(incoming) ? Guid.NewGuid().ToString("n") : incoming!;
        context.Items["request_id"] = rid;

        context.Response.OnStarting(() =>
        {
            context.Response.Headers[Header] = rid;
            return Task.CompletedTask;
        });

        await _next(context);
    }
}

using System.Text;
using DoaneEdgeGate.Core;
using DoaneEdgeGate.Forwarding;
using Microsoft.Extensions.Options;

namespace DoaneEdgeGate.Middleware;

/// <summary>
/// Terminal middleware: every request that is not a local management endpoint
/// ends here and is forwarded downstream. Matched Instant Enrollment requests are
/// rewritten (Active), observed (Shadow), or passed straight through (Off).
/// </summary>
public sealed class EdgeGateMiddleware
{
    private readonly IOptions<EdgeGateOptions> _options;
    private readonly IPayloadForwarder _forwarder;
    private readonly PayloadRewriter _rewriter;
    private readonly RewriteStats _stats;

    public EdgeGateMiddleware(IOptions<EdgeGateOptions> options, IPayloadForwarder forwarder,
        PayloadRewriter rewriter, RewriteStats stats)
    {
        _options = options;
        _forwarder = forwarder;
        _rewriter = rewriter;
        _stats = stats;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var opts = _options.Value;
        var rid = context.Items.TryGetValue("request_id", out var r) ? r?.ToString() ?? "" : "";
        var endpoint = $"{context.Request.Method} {context.Request.Path}";

        // Off, or not a request we watch -> pass straight through.
        if (opts.Mode == RewriteMode.Off
            || !MethodMatches(opts.Match, context.Request.Method)
            || !PathMatches(opts.Match.PathPatterns, context.Request.Path))
        {
            await _forwarder.ForwardAsync(context, bodyOverride: null, rid);
            return;
        }

        _stats.MarkMatched();

        // Only JSON, uncompressed bodies can be safely rewritten. Anything else is
        // forwarded untouched (fail-safe) so we never corrupt a body we don't
        // fully understand.
        var isJson = (context.Request.ContentType ?? "").Contains("json", StringComparison.OrdinalIgnoreCase);
        var isEncoded = context.Request.Headers.ContainsKey("Content-Encoding");
        if (!isJson || isEncoded)
        {
            _stats.MarkSkipped();
            StructuredLog.Info("matched but not rewritable; forwarding unchanged", rid,
                new Dictionary<string, object?> { ["endpoint"] = endpoint, ["is_json"] = isJson, ["content_encoded"] = isEncoded });
            await _forwarder.ForwardAsync(context, bodyOverride: null, rid);
            return;
        }

        var original = await ReadBodyAsync(context);
        var toSend = original;
        RewriteOutcome? outcome = null;

        if (opts.Mode == RewriteMode.Shadow)
        {
            try
            {
                outcome = _rewriter.Rewrite(Encoding.UTF8.GetString(original));
                if (outcome.Changed)
                    StructuredLog.Info("shadow: would rewrite", rid,
                        new Dictionary<string, object?> { ["endpoint"] = endpoint, ["fields"] = outcome.Records.Count });
            }
            catch (Exception ex)
            {
                _stats.MarkError();
                StructuredLog.Warn("shadow: rewrite failed (no effect in shadow)", rid,
                    new Dictionary<string, object?> { ["endpoint"] = endpoint, ["error"] = ex.Message });
            }
            // Shadow never mutates.
        }
        else // Active
        {
            try
            {
                outcome = _rewriter.Rewrite(Encoding.UTF8.GetString(original));
                if (outcome.Changed)
                {
                    toSend = Encoding.UTF8.GetBytes(outcome.Json);
                    StructuredLog.Info("rewrote payload", rid,
                        new Dictionary<string, object?> { ["endpoint"] = endpoint, ["fields"] = outcome.Records.Count });
                }
            }
            catch (Exception ex)
            {
                _stats.MarkError();
                StructuredLog.Error("rewrite failed", rid,
                    new Dictionary<string, object?> { ["endpoint"] = endpoint, ["error"] = ex.Message, ["fail_mode"] = opts.Rewrite.FailMode.ToString() });

                if (opts.Rewrite.FailMode == FailMode.Closed)
                {
                    await WriteErrorAsync(context, 502, "rewrite_failed", rid);
                    return;
                }
                // Fail-open: forward the original body. Never drop an enrollment.
                toSend = original;
                outcome = null;
            }
        }

        // Capturing the created record ID needs the downstream RESPONSE, which
        // only exists once we forward — so stats recording (which carries the ID)
        // happens after forwarding, not before. This is the join-key fix from
        // DOB-Repair-Tandem-Flow.md section 5: without it, a gate log entry can
        // only be matched to the Colleague record it produced by fuzzy identity
        // matching later, which is the weaker inference the log exists to avoid.
        var shouldCapture = opts.Rewrite.CaptureResponseRecordId && outcome?.Changed == true;
        var capturedRecordId = await _forwarder.ForwardAsync(context, toSend, rid, shouldCapture);

        if (outcome?.Changed == true)
        {
            if (opts.Mode == RewriteMode.Shadow)
                _stats.RecordShadow(rid, endpoint, outcome.Records, capturedRecordId);
            else
                _stats.RecordActive(rid, endpoint, outcome.Records, capturedRecordId);
        }
    }

    private static async Task<byte[]> ReadBodyAsync(HttpContext context)
    {
        using var ms = new MemoryStream();
        await context.Request.Body.CopyToAsync(ms);
        return ms.ToArray();
    }

    private static bool MethodMatches(MatchOptions match, string method) =>
        match.Methods.Any(m => string.Equals(m, method, StringComparison.OrdinalIgnoreCase));

    internal static bool PathMatches(IReadOnlyList<string> patterns, PathString path)
    {
        var p = path.Value ?? "";
        foreach (var pattern in patterns)
        {
            if (string.IsNullOrEmpty(pattern)) continue;
            if (pattern.EndsWith('*'))
            {
                if (p.StartsWith(pattern[..^1], StringComparison.OrdinalIgnoreCase)) return true;
            }
            else if (string.Equals(p, pattern, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }
        return false;
    }

    private static async Task WriteErrorAsync(HttpContext context, int status, string code, string requestId)
    {
        context.Response.StatusCode = status;
        context.Response.ContentType = "application/json";
        await context.Response.WriteAsync(
            $"{{\"error\":\"edge gate could not process the request\",\"code\":\"{code}\",\"request_id\":\"{requestId}\"}}");
    }
}

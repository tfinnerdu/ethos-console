using DoaneEdgeGate.Core;
using Microsoft.Extensions.Options;

namespace DoaneEdgeGate.Forwarding;

/// <summary>
/// Zero-third-party reverse-proxy forwarder. Deliberately conservative: it does
/// not auto-decompress, does not follow redirects (3xx is passed through so the
/// client sees exactly what the Web API returned), and copies every header except
/// the hop-by-hop set and length/host which it manages itself.
/// </summary>
public sealed class HttpClientForwarder : IPayloadForwarder
{
    // RFC 7230 hop-by-hop headers plus ones the transport must own.
    private static readonly HashSet<string> HopByHop = new(StringComparer.OrdinalIgnoreCase)
    {
        "Connection", "Keep-Alive", "Proxy-Authenticate", "Proxy-Authorization",
        "TE", "Trailer", "Trailers", "Transfer-Encoding", "Upgrade",
        "Host", "Content-Length"
    };

    private readonly HttpClient _client;
    private readonly DownstreamOptions _downstream;
    private readonly HashSet<string> _responseIdFieldNames;

    public HttpClientForwarder(HttpClient client, IOptions<EdgeGateOptions> options)
    {
        _client = client;
        _downstream = options.Value.Downstream;
        _responseIdFieldNames = new HashSet<string>(
            options.Value.Rewrite.ResponseIdFieldNames, StringComparer.OrdinalIgnoreCase);
    }

    public async Task<string?> ForwardAsync(HttpContext context, byte[]? bodyOverride, string requestId, bool captureResponseId = false)
    {
        var req = context.Request;
        var baseUrl = _downstream.BaseUrl.TrimEnd('/');
        var target = $"{baseUrl}{req.Path}{req.QueryString}";

        using var outbound = new HttpRequestMessage(new HttpMethod(req.Method), target);

        // Body
        var methodHasBody = HttpMethods.IsPost(req.Method) || HttpMethods.IsPut(req.Method)
            || HttpMethods.IsPatch(req.Method) || HttpMethods.IsDelete(req.Method);
        if (methodHasBody)
        {
            HttpContent content = bodyOverride != null
                ? new ByteArrayContent(bodyOverride)
                : new StreamContent(req.Body);
            if (!string.IsNullOrEmpty(req.ContentType))
                content.Headers.TryAddWithoutValidation("Content-Type", req.ContentType);
            outbound.Content = content;
        }

        // Copy request headers (skip hop-by-hop; Content-Type already set on content)
        foreach (var h in req.Headers)
        {
            if (HopByHop.Contains(h.Key) || string.Equals(h.Key, "Content-Type", StringComparison.OrdinalIgnoreCase))
                continue;
            if (!outbound.Headers.TryAddWithoutValidation(h.Key, h.Value.ToArray()) && outbound.Content != null)
                outbound.Content.Headers.TryAddWithoutValidation(h.Key, h.Value.ToArray());
        }

        HttpResponseMessage response;
        try
        {
            response = await _client.SendAsync(outbound, HttpCompletionOption.ResponseHeadersRead, context.RequestAborted);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            throw new DownstreamException($"forward to '{target}' failed", ex);
        }

        using (response)
        {
            context.Response.StatusCode = (int)response.StatusCode;

            foreach (var h in response.Headers)
                if (!HopByHop.Contains(h.Key))
                    context.Response.Headers[h.Key] = h.Value.ToArray();

            foreach (var h in response.Content.Headers)
                if (!HopByHop.Contains(h.Key))
                    context.Response.Headers[h.Key] = h.Value.ToArray();

            // Let Kestrel set the length/encoding for the copied stream.
            context.Response.Headers.Remove("transfer-encoding");

            // Only buffer (instead of stream) when the caller actually wants the
            // created record ID — this is the narrow, already-rare "matched and
            // rewritten" subset of traffic. Everything else keeps streaming with
            // zero extra memory cost.
            var isJsonResponse = (response.Content.Headers.ContentType?.MediaType ?? "")
                .Contains("json", StringComparison.OrdinalIgnoreCase);

            if (captureResponseId && response.IsSuccessStatusCode && isJsonResponse)
            {
                var bytes = await response.Content.ReadAsByteArrayAsync(context.RequestAborted);
                await context.Response.Body.WriteAsync(bytes, context.RequestAborted);
                return ResponseIdExtractor.TryExtract(bytes, _responseIdFieldNames);
            }

            await response.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
            return null;
        }
    }
}

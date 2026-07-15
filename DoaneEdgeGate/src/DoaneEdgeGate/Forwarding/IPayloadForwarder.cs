namespace DoaneEdgeGate.Forwarding;

/// <summary>
/// Forwards the current request to the downstream Colleague Web API and copies the
/// response back. If <paramref name="bodyOverride"/> is non-null it is sent as the
/// request body (the rewritten payload); if null, the original request body stream
/// is streamed through unchanged.
///
/// When <paramref name="captureResponseId"/> is true, the response body is
/// buffered (instead of streamed) so it can be inspected for a created record ID
/// before being written back to the client unchanged — see
/// DoaneEdgeGate.Core.ResponseIdExtractor. The returned value is that captured ID,
/// or null if capture was not requested, the response wasn't JSON, or no
/// configured field name was found. This never affects what the client receives.
/// </summary>
public interface IPayloadForwarder
{
    Task<string?> ForwardAsync(HttpContext context, byte[]? bodyOverride, string requestId, bool captureResponseId = false);
}

/// <summary>Downstream returned a transport-level failure (refused, timeout, etc.).</summary>
public sealed class DownstreamException : Exception
{
    public DownstreamException(string message, Exception inner) : base(message, inner) { }
}

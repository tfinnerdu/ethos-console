using System.Security.Cryptography;
using System.Text;

namespace DoaneEdgeGate.Core;

/// <summary>
/// Gates GET /api/v1/status and GET /api/v1/rewrites/recent behind a shared
/// secret (the X-Management-Key request header) once the app is actually
/// running in production. Both endpoints expose operationally sensitive
/// detail — /status reveals the internal Downstream:BaseUrl, and
/// /rewrites/recent carries the actual, unredacted applicant birth dates
/// this gate intercepted (RewriteRecord.Original/Rewritten) — so neither is
/// safe to leave open on a deployment fronting live enrollment traffic.
/// Left unenforced outside production so local testing and demos need no
/// extra config. GET /health is never gated by this, in any environment —
/// it carries nothing sensitive and backs liveness/readiness probes that
/// must never depend on this being configured correctly.
/// </summary>
public static class ManagementAuth
{
    public static bool IsAuthorized(string configuredKey, string? suppliedKey, bool isProduction)
    {
        if (!isProduction)
            return true;

        // No key configured means nothing can ever authorize successfully —
        // fail closed rather than silently leaving the endpoint open because
        // an operator forgot to set it.
        if (string.IsNullOrEmpty(configuredKey))
            return false;

        var supplied = suppliedKey ?? "";
        var configuredBytes = Encoding.UTF8.GetBytes(configuredKey);
        var suppliedBytes = Encoding.UTF8.GetBytes(supplied);
        return CryptographicOperations.FixedTimeEquals(suppliedBytes, configuredBytes);
    }
}

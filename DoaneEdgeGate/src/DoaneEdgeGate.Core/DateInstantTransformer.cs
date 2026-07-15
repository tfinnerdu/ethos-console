using System.Globalization;
using System.Text.RegularExpressions;

namespace DoaneEdgeGate.Core;

public enum TransformOutcome
{
    /// <summary>Left as-is. See Reason for why.</summary>
    Unchanged,
    /// <summary>Rewritten to a bare date. Value holds the new date-only string.</summary>
    Rewritten
}

public readonly record struct TransformResult(TransformOutcome Outcome, string Value, string Reason)
{
    public bool Changed => Outcome == TransformOutcome.Rewritten;

    public static TransformResult Keep(string original, string reason) =>
        new(TransformOutcome.Unchanged, original, reason);

    public static TransformResult Rewrite(string dateOnly, string reason) =>
        new(TransformOutcome.Rewritten, dateOnly, reason);
}

/// <summary>
/// Reduces an ISO date/instant to the date the registrant intended (bare
/// yyyy-MM-dd), or leaves the value untouched if it does not match the bug
/// signature.
///
/// Why the date substring is the right answer, not timezone math:
/// The Self-Service date picker produces LOCAL MIDNIGHT of the chosen date and
/// Angular serializes it with toISOString(), i.e. as UTC ("...Z"). For every US
/// (Western-hemisphere) timezone, local midnight converts to a SAME-DATE morning
/// UTC time (midnight + 4..10h). So the date portion of the UTC string is still
/// the intended calendar date. The day is only lost later, when the .NET Web API
/// converts that instant back to server-local (Central) and truncates. Forwarding
/// the bare date portion as date-only means the server never does that conversion,
/// so the intended date survives. No knowledge of the client's timezone is needed.
///
/// Known limitation: for a registrant physically in a UTC-AHEAD zone (Europe/Asia/
/// Australia) at submission time, local midnight serializes to the PREVIOUS UTC
/// date, so the substring is already one day early before it reaches this gate and
/// we cannot recover it from a "Z" instant (the offset is gone). That population is
/// small for Instant Enrollment but real for international applicants; the true fix
/// remains the client sending date-only. Offset-form instants ("...-05:00") carry
/// the local wall-clock date directly and are handled correctly for all zones.
/// </summary>
public static class DateInstantTransformer
{
    // yyyy-MM-dd
    private static readonly Regex DateOnly =
        new(@"^\d{4}-\d{2}-\d{2}$", RegexOptions.Compiled);

    // yyyy-MM-ddTHH:mm[:ss[.fff...]] optionally followed by Z or +/-HH:mm
    private static readonly Regex Instant =
        new(@"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$",
            RegexOptions.Compiled);

    public static TransformResult Transform(string? value, bool requireMorningUtcForZ)
    {
        if (string.IsNullOrWhiteSpace(value))
            return TransformResult.Keep(value ?? "", "empty");

        var v = value.Trim();

        // Already a bare date -> fail-safe no-op. This is what makes the gate
        // become inert automatically once Ellucian fixes the client.
        if (DateOnly.IsMatch(v))
        {
            return IsRealDate(v)
                ? TransformResult.Keep(value!, "already-date-only")
                : TransformResult.Keep(value!, "date-only-but-invalid");
        }

        var m = Instant.Match(v);
        if (!m.Success)
            return TransformResult.Keep(value!, "not-iso-instant");

        var datePart = m.Groups[1].Value;
        if (!IsRealDate(datePart))
            return TransformResult.Keep(value!, "invalid-date-part");

        var zone = m.Groups[4].Value; // "", "Z", or "+/-HH:mm"

        if (zone.Length == 0)
        {
            // Naive local datetime (no zone). The wall-clock date is the intended
            // date; drop the time.
            return TransformResult.Rewrite(datePart, "naive-localdate");
        }

        if (zone != "Z")
        {
            // Explicit offset: the wall-clock date shown IS the local date.
            return TransformResult.Rewrite(datePart, "offset-form-localdate");
        }

        // UTC ("Z"). Guard: only treat as the bug signature if the UTC time is a
        // morning time consistent with a Western local-midnight origin.
        if (requireMorningUtcForZ)
        {
            var hour = int.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture);
            if (hour >= 12)
                return TransformResult.Keep(value!, "z-afternoon-not-bug-signature");
        }

        return TransformResult.Rewrite(datePart, "z-utc-datesubstring");
    }

    private static bool IsRealDate(string yyyyMMdd) =>
        DateOnly.IsMatch(yyyyMMdd) &&
        DateTime.TryParseExact(yyyyMMdd, "yyyy-MM-dd",
            CultureInfo.InvariantCulture, DateTimeStyles.None, out _);
}

namespace DoaneEdgeGate.Core;

/// <summary>
/// Run mode for the edge gate. This is the master safety switch.
///   Off    - pure passthrough. The gate does nothing; every request is
///            forwarded byte-for-byte. Deploy in this mode first.
///   Shadow - the transform runs and every would-be rewrite is logged and
///            counted, but the ORIGINAL body is forwarded unchanged. Use this to
///            validate against real traffic before mutating anything.
///   Active - matched requests are rewritten before forwarding.
/// The intended lifecycle is Off -> Shadow (validate) -> Active (only after
/// Phase 0 confirms the payload carries a UTC instant).
/// </summary>
public enum RewriteMode
{
    Off,
    Shadow,
    Active
}

/// <summary>
/// What to do if the rewrite step throws for a matched request.
///   Open   - forward the ORIGINAL body unchanged and log the error. This is the
///            default and the recommended setting: the gate sits in the path of
///            every registration, so a bug in it must never be able to drop an
///            enrollment.
///   Closed - return an error to the client. Only use if a silent passthrough of
///            a possibly-corrupt date is worse for you than a failed submission.
/// </summary>
public enum FailMode
{
    Open,
    Closed
}

/// <summary>
/// How the rewriter decides which JSON fields to touch.
///   FieldAllowlist - only string properties whose name is in DateFieldNames are
///                    considered. Safest and most surgical. Default.
///   ShapeAll       - any string value on a matched request that looks like an
///                    ISO instant is considered, regardless of field name. Use
///                    this if the bug shifts every date-only field in the flow
///                    (it does), not just birth date, and you would rather catch
///                    them all than maintain a field list.
/// In both strategies a value is only rewritten if it actually matches the
/// instant signature; a field in the allowlist that already holds a bare date is
/// left untouched (fail-safe).
/// </summary>
public enum RewriteStrategy
{
    FieldAllowlist,
    ShapeAll
}

public sealed class EdgeGateOptions
{
    public const string SectionName = "EdgeGate";

    public RewriteMode Mode { get; set; } = RewriteMode.Off;

    public DownstreamOptions Downstream { get; set; } = new();
    public MatchOptions Match { get; set; } = new();
    public RewriteOptions Rewrite { get; set; } = new();
}

public sealed class DownstreamOptions
{
    /// <summary>
    /// Base URL of the real Colleague Web API this gate forwards to, e.g.
    /// "http://localhost:8080" or "https://colleague-webapi.internal.doane.edu".
    /// The incoming path and query string are appended unchanged.
    /// </summary>
    public string BaseUrl { get; set; } = "";

    /// <summary>Timeout for the forwarded call, in seconds.</summary>
    public int TimeoutSeconds { get; set; } = 100;
}

public sealed class MatchOptions
{
    /// <summary>HTTP methods that are eligible for rewriting. Others pass through.</summary>
    public List<string> Methods { get; set; } = new() { "POST", "PUT" };

    /// <summary>
    /// Request path patterns that identify the Instant Enrollment person-create
    /// call(s). A request is eligible only if its path matches one of these.
    /// Patterns support a trailing '*' wildcard (prefix match) or exact match;
    /// matching is case-insensitive. Fill these from the Phase 0 network capture.
    /// If empty, NOTHING matches (safe default - the gate stays inert until you
    /// tell it what to look at).
    /// </summary>
    public List<string> PathPatterns { get; set; } = new();
}

public sealed class RewriteOptions
{
    public RewriteStrategy Strategy { get; set; } = RewriteStrategy.FieldAllowlist;

    public FailMode FailMode { get; set; } = FailMode.Open;

    /// <summary>
    /// JSON property names treated as dates under FieldAllowlist. Case-insensitive.
    /// Defaults cover the common Colleague/Self-Service spellings; adjust to match
    /// the actual payload field(s) seen in Phase 0.
    /// </summary>
    public List<string> DateFieldNames { get; set; } = new()
    {
        "birthDate", "dateOfBirth", "dob", "birthdate", "BirthDate"
    };

    /// <summary>
    /// When rewriting a UTC ("...Z") instant, only rewrite if the UTC time-of-day
    /// is before noon. A date picker that produced local midnight in any Western-
    /// hemisphere zone serializes to a same-date morning UTC time, which is the
    /// exact signature of this bug. A Z instant whose time is noon or later did
    /// not come from a Western local-midnight origin, so we leave it alone rather
    /// than risk shifting a legitimately different value. Default true.
    /// </summary>
    public bool RequireMorningUtcForZ { get; set; } = true;

    /// <summary>Emit a log line for values that were examined but left unchanged.</summary>
    public bool LogUnchanged { get; set; } = false;

    /// <summary>How many recent rewrite records to keep in memory for /api/v1/rewrites/recent.</summary>
    public int RecentBufferSize { get; set; } = 200;

    /// <summary>
    /// After a matched request that was rewritten (Active) or would have been
    /// rewritten (Shadow), inspect the downstream JSON response for the created
    /// record's ID and attach it to the logged rewrite record. See
    /// DOB-Repair-Tandem-Flow.md section 5: without this, a gate log entry can
    /// only be joined to the Colleague record it produced by fuzzy identity
    /// matching later, which is the weaker inference the log was meant to avoid.
    /// Only buffers the response body (instead of streaming it) for this narrow,
    /// already-rare subset of traffic — ordinary passthrough traffic is
    /// unaffected. Default true.
    /// </summary>
    public bool CaptureResponseRecordId { get; set; } = true;

    /// <summary>
    /// JSON property names checked on the downstream response body when
    /// CaptureResponseRecordId is enabled. Case-insensitive. Defaults cover
    /// common REST create-response spellings; adjust to match what the real
    /// Colleague Web API create-person response actually returns.
    /// </summary>
    public List<string> ResponseIdFieldNames { get; set; } = new()
    {
        "id", "personId", "recordId", "Id"
    };
}

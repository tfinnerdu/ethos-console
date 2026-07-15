namespace DoaneEdgeGate.Core;

/// <summary>
/// One field that the rewriter touched (or, in Shadow mode, would have touched).
/// The set of these for a request is both the audit trail and the pre-shift
/// source of truth: it captures exactly what the browser sent, keyed to the
/// request, before any correction. That is precisely the signal the nightly
/// detector wants - it turns "infer the true date from a twin" into "compare
/// against what they actually typed".
/// </summary>
public sealed record RewriteRecord(
    string FieldPath,
    string Original,
    string Rewritten,
    string Reason);

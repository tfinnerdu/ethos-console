using DoaneEdgeGate.Core;

namespace DoaneEdgeGate;

/// <summary>
/// Process-lifetime counters and a bounded buffer of recent rewrites. Registered
/// as a singleton. This is what makes Shadow mode useful: you can watch, over
/// real traffic, exactly what the gate WOULD change before you ever flip to Active.
/// </summary>
public sealed class RewriteStats
{
    private long _matched, _rewrittenRequests, _shadowWouldRewrite, _fieldRewrites, _errors, _skipped;
    private readonly object _lock = new();
    private readonly Queue<RecentEntry> _recent = new();
    private readonly int _capacity;

    public RewriteStats(int capacity) => _capacity = Math.Max(1, capacity);

    public DateTimeOffset StartedUtc { get; } = DateTimeOffset.UtcNow;

    public long Matched => Interlocked.Read(ref _matched);
    public long RewrittenRequests => Interlocked.Read(ref _rewrittenRequests);
    public long ShadowWouldRewrite => Interlocked.Read(ref _shadowWouldRewrite);
    public long FieldRewrites => Interlocked.Read(ref _fieldRewrites);
    public long Errors => Interlocked.Read(ref _errors);
    public long Skipped => Interlocked.Read(ref _skipped);

    public void MarkMatched() => Interlocked.Increment(ref _matched);
    public void MarkError() => Interlocked.Increment(ref _errors);
    public void MarkSkipped() => Interlocked.Increment(ref _skipped);

    public void RecordActive(string requestId, string endpoint, IReadOnlyList<RewriteRecord> records, string? capturedRecordId = null)
    {
        Interlocked.Increment(ref _rewrittenRequests);
        Add(requestId, endpoint, "active", records, capturedRecordId);
    }

    public void RecordShadow(string requestId, string endpoint, IReadOnlyList<RewriteRecord> records, string? capturedRecordId = null)
    {
        Interlocked.Increment(ref _shadowWouldRewrite);
        Add(requestId, endpoint, "shadow", records, capturedRecordId);
    }

    private void Add(string requestId, string endpoint, string mode, IReadOnlyList<RewriteRecord> records, string? capturedRecordId)
    {
        var real = records.Where(r => !r.Reason.StartsWith("unchanged:", StringComparison.Ordinal)).ToList();
        Interlocked.Add(ref _fieldRewrites, real.Count);
        lock (_lock)
        {
            foreach (var r in real)
            {
                _recent.Enqueue(new RecentEntry(DateTimeOffset.UtcNow, requestId, endpoint, mode,
                    r.FieldPath, r.Original, r.Rewritten, r.Reason, capturedRecordId));
                if (_recent.Count > _capacity) _recent.Dequeue();
            }
        }
    }

    public IReadOnlyList<RecentEntry> Recent(int take)
    {
        lock (_lock)
            return _recent.Reverse().Take(Math.Max(0, take)).ToList();
    }

    public sealed record RecentEntry(
        DateTimeOffset TimestampUtc, string RequestId, string Endpoint, string Mode,
        string FieldPath, string Original, string Rewritten, string Reason,
        string? CapturedRecordId = null);
}

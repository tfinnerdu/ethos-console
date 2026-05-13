using EthosCn.Domain.Enums;

namespace EthosCn.Domain.Entities;

public class AuditEntry
{
    public long AuditId { get; set; }
    public DateTimeOffset Timestamp { get; set; }
    public string UserId { get; set; } = string.Empty;
    public string UserDisplayName { get; set; } = string.Empty;
    public AuditAction Action { get; set; }
    public string TargetType { get; set; } = string.Empty;
    public string? TargetIdentifier { get; set; }
    public string? BeforeState { get; set; }
    public string? AfterState { get; set; }
    public AuditOutcome Outcome { get; set; }
    public string? FailureReason { get; set; }
    public Guid CorrelationId { get; set; }
    public string? SourceIp { get; set; }
}

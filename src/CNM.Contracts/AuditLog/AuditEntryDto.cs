namespace CNM.Contracts.AuditLog;

public record AuditEntryDto(
    long AuditId,
    DateTimeOffset Timestamp,
    string UserId,
    string UserDisplayName,
    string Action,
    string TargetType,
    string? TargetIdentifier,
    string? BeforeState,
    string? AfterState,
    string Outcome,
    string? FailureReason,
    Guid CorrelationId,
    string? SourceIp
);

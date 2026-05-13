namespace EthosCn.Contracts.AuditLog;

public record AuditLogQueryDto(
    int Page = 1,
    int PageSize = 50,
    string? UserId = null,
    string? TargetIdentifier = null,
    DateTimeOffset? From = null,
    DateTimeOffset? To = null
);

public record PagedAuditLogDto(
    IReadOnlyList<AuditEntryDto> Items,
    int TotalCount,
    int Page,
    int PageSize
);

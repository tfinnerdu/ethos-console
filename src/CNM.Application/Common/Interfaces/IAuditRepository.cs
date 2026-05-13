using CNM.Domain.Entities;
using CNM.Domain.Enums;

namespace CNM.Application.Common.Interfaces;

public interface IAuditRepository
{
    Task WriteAsync(AuditEntry entry, CancellationToken cancellationToken = default);

    Task<(IReadOnlyList<AuditEntry> Items, int TotalCount)> QueryAsync(
        int page,
        int pageSize,
        string? userId = null,
        string? targetIdentifier = null,
        DateTimeOffset? from = null,
        DateTimeOffset? to = null,
        CancellationToken cancellationToken = default);
}

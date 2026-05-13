using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;

namespace EthosCn.Application.Common.Interfaces;

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

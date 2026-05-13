using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using EthosCn.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

namespace EthosCn.Infrastructure.Repositories;

internal sealed class AuditRepository(CnmDbContext db) : IAuditRepository
{
    public async Task WriteAsync(AuditEntry entry, CancellationToken cancellationToken = default)
    {
        db.AuditLog.Add(entry);
        await db.SaveChangesAsync(cancellationToken);
    }

    public async Task<(IReadOnlyList<AuditEntry> Items, int TotalCount)> QueryAsync(
        int page,
        int pageSize,
        string? userId = null,
        string? targetIdentifier = null,
        DateTimeOffset? from = null,
        DateTimeOffset? to = null,
        CancellationToken cancellationToken = default)
    {
        var query = db.AuditLog.AsNoTracking();

        if (userId is not null)
            query = query.Where(e => e.UserId == userId);

        if (targetIdentifier is not null)
            query = query.Where(e => e.TargetIdentifier == targetIdentifier);

        if (from is not null)
            query = query.Where(e => e.Timestamp >= from.Value);

        if (to is not null)
            query = query.Where(e => e.Timestamp <= to.Value);

        var total = await query.CountAsync(cancellationToken);

        var items = await query
            .OrderByDescending(e => e.Timestamp)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return (items, total);
    }
}

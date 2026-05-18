using EthosCn.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace EthosCn.Infrastructure.Health;

internal sealed class CnmDatabaseHealthCheck(CnmDbContext db) : IHealthCheck
{
    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        if (!await db.Database.CanConnectAsync(cancellationToken))
            return HealthCheckResult.Unhealthy("Cannot connect to CnmDb.");

        var pending = await db.Database.GetPendingMigrationsAsync(cancellationToken);
        var pendingList = pending.ToList();
        if (pendingList.Count > 0)
            return HealthCheckResult.Degraded(
                $"{pendingList.Count} pending migration(s): {string.Join(", ", pendingList)}");

        return HealthCheckResult.Healthy();
    }
}

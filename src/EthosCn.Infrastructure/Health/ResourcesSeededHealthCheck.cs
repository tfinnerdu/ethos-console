using EthosCn.Application.Common.Interfaces;
using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace EthosCn.Infrastructure.Health;

internal sealed class ResourcesSeededHealthCheck(IResourceRepository resources) : IHealthCheck
{
    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        var all = await resources.GetAllAsync(cancellationToken);
        return all.Count > 0
            ? HealthCheckResult.Healthy($"{all.Count} subscribed resources loaded.")
            : HealthCheckResult.Unhealthy("Resource repository returned empty — DI or seeding problem.");
    }
}

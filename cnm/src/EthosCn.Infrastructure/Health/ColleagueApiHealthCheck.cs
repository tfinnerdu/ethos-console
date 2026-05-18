using EthosCn.Infrastructure.Colleague.WebApi;
using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace EthosCn.Infrastructure.Health;

internal sealed class ColleagueApiHealthCheck(IColleagueWebApiClient client) : IHealthCheck
{
    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            cts.CancelAfter(TimeSpan.FromSeconds(5));

            var about = await client.GetAboutAsync(cts.Token);
            var version = about.ProductVersion ?? "(version unknown)";
            return HealthCheckResult.Healthy($"Colleague Web API responding. Version: {version}");
        }
        catch (OperationCanceledException)
        {
            return HealthCheckResult.Degraded("Colleague Web API timed out after 5s.");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Degraded($"Colleague Web API unreachable: {ex.Message}");
        }
    }
}

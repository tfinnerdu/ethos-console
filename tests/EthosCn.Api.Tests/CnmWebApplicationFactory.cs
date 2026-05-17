using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace EthosCn.Api.Tests;

/// <summary>
/// Shared factory for API integration tests.
/// Sets Development environment so DevAuthHandler runs (no Azure AD needed).
/// Swaps IAuditRepository for an in-memory no-op so tests don't touch the
/// file system or require a database.
/// </summary>
public class CnmWebApplicationFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");

        builder.ConfigureServices(services =>
        {
            services.Replace(ServiceDescriptor.Scoped<IAuditRepository, NoOpAuditRepository>());
        });
    }
}

internal sealed class NoOpAuditRepository : IAuditRepository
{
    public Task WriteAsync(AuditEntry entry, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task<(IReadOnlyList<AuditEntry> Items, int TotalCount)> QueryAsync(
        int page, int pageSize,
        string? userId = null, string? targetIdentifier = null,
        DateTimeOffset? from = null, DateTimeOffset? to = null,
        CancellationToken cancellationToken = default)
        => Task.FromResult<(IReadOnlyList<AuditEntry>, int)>(([], 0));
}

using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace EthosCn.Api.Tests;

/// <summary>
/// Shared factory for API integration tests.
/// Sets Development environment so DevAuthHandler runs (no Azure AD needed).
/// Swaps IAuditRepository for an in-memory no-op so tests don't touch the
/// file system or require a database. Points CnmDbContext at a per-factory
/// temp SQLite file so tests do NOT write to the user-visible
/// &lt;repo&gt;/console/instance/cnm.db.
/// </summary>
public class CnmWebApplicationFactory : WebApplicationFactory<Program>
{
    private readonly string _tempDbPath = Path.Combine(
        Path.GetTempPath(),
        $"cnm-test-{Guid.NewGuid():N}.db");

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");

        builder.ConfigureAppConfiguration((_, cfg) =>
        {
            cfg.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["Cnm:UseSqlite"] = "true",
                ["ConnectionStrings:CnmDb"] = $"Data Source={_tempDbPath}",
            });
        });

        builder.ConfigureServices(services =>
        {
            services.Replace(ServiceDescriptor.Scoped<IAuditRepository, NoOpAuditRepository>());
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing && File.Exists(_tempDbPath))
        {
            try { File.Delete(_tempDbPath); }
            catch { /* best-effort cleanup */ }
        }
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

using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using Microsoft.AspNetCore.Hosting;

namespace EthosCn.Infrastructure.Repositories;

/// <summary>
/// Development-only audit repository. Appends human-readable entries to
/// .hub-logs/audit.txt at the solution root. Never registered in non-dev environments.
/// QueryAsync returns empty — read the file directly for dev audit inspection.
/// </summary>
internal sealed class FileAuditRepository(IWebHostEnvironment env) : IAuditRepository
{
    private readonly string _path = Path.Combine(
        Path.GetFullPath(Path.Combine(env.ContentRootPath, "..", "..", "..")),
        ".hub-logs",
        "audit.txt");

    public async Task WriteAsync(AuditEntry entry, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);

        var line = $"[{entry.Timestamp:yyyy-MM-dd HH:mm:ss}Z] " +
                   $"{entry.Action,-8} | {entry.TargetType,-24} | {entry.TargetIdentifier ?? "-",-40} | " +
                   $"{entry.UserId,-20} | {entry.SourceIp ?? "-",-16} | {entry.Outcome}";

        if (entry.FailureReason is not null)
            line += $" | {entry.FailureReason}";

        await File.AppendAllTextAsync(_path, line + Environment.NewLine, cancellationToken);
    }

    public Task<(IReadOnlyList<AuditEntry> Items, int TotalCount)> QueryAsync(
        int page, int pageSize,
        string? userId = null, string? targetIdentifier = null,
        DateTimeOffset? from = null, DateTimeOffset? to = null,
        CancellationToken cancellationToken = default)
    {
        // Dev audit is append-only text; query not implemented here.
        // Read .hub-logs/audit.txt directly for local inspection.
        IReadOnlyList<AuditEntry> empty = [];
        return Task.FromResult((empty, 0));
    }
}

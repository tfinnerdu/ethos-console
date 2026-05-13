using CNM.Domain.Entities;
using CNM.Domain.Enums;
using CNM.Infrastructure.Persistence;
using CNM.Infrastructure.Repositories;
using FluentAssertions;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace CNM.Infrastructure.Tests.Persistence;

public class AuditRepositoryTests
{
    private static CnmDbContext BuildInMemoryContext()
    {
        var opts = new DbContextOptionsBuilder<CnmDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;
        return new CnmDbContext(opts);
    }

    [Fact]
    public async Task WriteAsync_persists_entry()
    {
        await using var db = BuildInMemoryContext();
        var repo = new AuditRepository(db);

        var entry = new AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = "user@doane.edu",
            UserDisplayName = "Test User",
            Action = AuditAction.View,
            TargetType = "ChangeNotification",
            TargetIdentifier = "cn-001",
            Outcome = AuditOutcome.Success,
            CorrelationId = Guid.NewGuid()
        };

        await repo.WriteAsync(entry);

        var (items, total) = await repo.QueryAsync(1, 10);
        total.Should().Be(1);
        items[0].UserId.Should().Be("user@doane.edu");
    }

    [Fact]
    public async Task QueryAsync_filters_by_targetIdentifier()
    {
        await using var db = BuildInMemoryContext();
        var repo = new AuditRepository(db);

        await repo.WriteAsync(new AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = "u1",
            UserDisplayName = "U1",
            Action = AuditAction.View,
            TargetType = "ChangeNotification",
            TargetIdentifier = "cn-001",
            Outcome = AuditOutcome.Success,
            CorrelationId = Guid.NewGuid()
        });

        await repo.WriteAsync(new AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = "u2",
            UserDisplayName = "U2",
            Action = AuditAction.View,
            TargetType = "ChangeNotification",
            TargetIdentifier = "cn-002",
            Outcome = AuditOutcome.Success,
            CorrelationId = Guid.NewGuid()
        });

        var (items, total) = await repo.QueryAsync(1, 10, targetIdentifier: "cn-001");
        total.Should().Be(1);
        items[0].TargetIdentifier.Should().Be("cn-001");
    }
}

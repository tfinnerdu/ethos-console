using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using EthosCn.Infrastructure.Repositories;
using FluentAssertions;
using Microsoft.AspNetCore.Hosting;
using NSubstitute;
using Xunit;

namespace EthosCn.Infrastructure.Tests.Repositories;

public class FileAuditRepositoryTests : IDisposable
{
    private readonly string _tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());

    private FileAuditRepository BuildRepo()
    {
        // ContentRootPath set to a fake "src/EthosCn.Api" inside our temp dir so
        // the repository navigates up two levels to find ".hub-logs".
        var apiDir = Path.Combine(_tempDir, "src", "EthosCn.Api");
        Directory.CreateDirectory(apiDir);

        var env = Substitute.For<IWebHostEnvironment>();
        env.ContentRootPath.Returns(apiDir);
        return new FileAuditRepository(env);
    }

    private static AuditEntry MakeEntry() => new()
    {
        Timestamp = new DateTimeOffset(2025, 1, 15, 10, 30, 0, TimeSpan.Zero),
        UserId = "user@doane.edu",
        UserDisplayName = "Test User",
        Action = AuditAction.View,
        TargetType = "ChangeNotification",
        TargetIdentifier = "cn-001",
        Outcome = AuditOutcome.Success,
        CorrelationId = Guid.NewGuid(),
        SourceIp = "10.0.0.1"
    };

    [Fact]
    public async Task WriteAsync_creates_audit_file()
    {
        var repo = BuildRepo();
        await repo.WriteAsync(MakeEntry());

        var auditFile = Path.Combine(_tempDir, ".hub-logs", "audit.txt");
        File.Exists(auditFile).Should().BeTrue();
    }

    [Fact]
    public async Task WriteAsync_appends_readable_line()
    {
        var repo = BuildRepo();
        await repo.WriteAsync(MakeEntry());

        var auditFile = Path.Combine(_tempDir, ".hub-logs", "audit.txt");
        var content = await File.ReadAllTextAsync(auditFile);
        content.Should().Contain("user@doane.edu");
        content.Should().Contain("cn-001");
        content.Should().Contain("Success");
        content.Should().Contain("View");
    }

    [Fact]
    public async Task WriteAsync_appends_multiple_entries()
    {
        var repo = BuildRepo();
        await repo.WriteAsync(MakeEntry());
        await repo.WriteAsync(MakeEntry());

        var auditFile = Path.Combine(_tempDir, ".hub-logs", "audit.txt");
        var lines = await File.ReadAllLinesAsync(auditFile);
        lines.Where(l => !string.IsNullOrWhiteSpace(l)).Should().HaveCount(2);
    }

    [Fact]
    public async Task WriteAsync_includes_failure_reason_when_present()
    {
        var repo = BuildRepo();
        var entry = MakeEntry();
        entry.Outcome = AuditOutcome.Failure;
        entry.FailureReason = "Not found";

        await repo.WriteAsync(entry);

        var auditFile = Path.Combine(_tempDir, ".hub-logs", "audit.txt");
        var content = await File.ReadAllTextAsync(auditFile);
        content.Should().Contain("Not found");
    }

    [Fact]
    public async Task QueryAsync_returns_empty_list()
    {
        var repo = BuildRepo();
        var (items, total) = await repo.QueryAsync(1, 50);

        items.Should().BeEmpty();
        total.Should().Be(0);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDir))
            Directory.Delete(_tempDir, recursive: true);
    }
}

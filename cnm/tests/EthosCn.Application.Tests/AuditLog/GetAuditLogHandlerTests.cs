using EthosCn.Application.AuditLog.Queries;
using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.AuditLog;

public class GetAuditLogHandlerTests
{
    private readonly IAuditRepository _audit = Substitute.For<IAuditRepository>();

    private static AuditEntry Entry(string userId) => new()
    {
        AuditId = 1,
        Timestamp = DateTimeOffset.UtcNow,
        UserId = userId,
        UserDisplayName = userId,
        Action = AuditAction.View,
        TargetType = "ChangeNotification",
        Outcome = AuditOutcome.Success,
        CorrelationId = Guid.NewGuid()
    };

    [Fact]
    public async Task Returns_paged_result_with_correct_metadata()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[Entry("u1"), Entry("u2")], 42));

        var handler = new GetAuditLogHandler(_audit);
        var result = await handler.Handle(new GetAuditLogQuery(Page: 2, PageSize: 10), CancellationToken.None);

        result.TotalCount.Should().Be(42);
        result.Page.Should().Be(2);
        result.PageSize.Should().Be(10);
        result.Items.Should().HaveCount(2);
    }

    [Fact]
    public async Task Maps_entries_to_dtos()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[Entry("audit-user")], 1));

        var handler = new GetAuditLogHandler(_audit);
        var result = await handler.Handle(new GetAuditLogQuery(), CancellationToken.None);

        result.Items[0].UserId.Should().Be("audit-user");
        result.Items[0].Action.Should().Be("View");
        result.Items[0].Outcome.Should().Be("Success");
    }

    [Fact]
    public async Task Returns_empty_page_when_no_entries()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[], 0));

        var handler = new GetAuditLogHandler(_audit);
        var result = await handler.Handle(new GetAuditLogQuery(), CancellationToken.None);

        result.TotalCount.Should().Be(0);
        result.Items.Should().BeEmpty();
    }

    [Fact]
    public async Task Passes_filters_through_to_repository()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[], 0));

        var handler = new GetAuditLogHandler(_audit);
        await handler.Handle(
            new GetAuditLogQuery(Page: 3, PageSize: 25, UserId: "filter-user", TargetIdentifier: "cn-001"),
            CancellationToken.None);

        await _audit.Received(1).QueryAsync(
            3, 25,
            userId: "filter-user",
            targetIdentifier: "cn-001",
            cancellationToken: Arg.Any<CancellationToken>());
    }
}

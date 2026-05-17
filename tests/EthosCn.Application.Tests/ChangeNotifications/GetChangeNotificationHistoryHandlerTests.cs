using EthosCn.Application.ChangeNotifications.Queries;
using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.ChangeNotifications;

public class GetChangeNotificationHistoryHandlerTests
{
    private readonly IAuditRepository _audit = Substitute.For<IAuditRepository>();

    [Fact]
    public async Task Returns_mapped_audit_entries_for_notification()
    {
        var correlationId = Guid.NewGuid();
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs((
                (IReadOnlyList<AuditEntry>)
                [
                    new AuditEntry
                    {
                        AuditId = 1,
                        Timestamp = DateTimeOffset.UtcNow,
                        UserId = "user@doane.edu",
                        UserDisplayName = "Test User",
                        Action = AuditAction.View,
                        TargetType = "ChangeNotification",
                        TargetIdentifier = "cn-001",
                        Outcome = AuditOutcome.Success,
                        CorrelationId = correlationId
                    }
                ],
                1));

        var handler = new GetChangeNotificationHistoryHandler(_audit);
        var result = await handler.Handle(
            new GetChangeNotificationHistoryQuery("cn-001"), CancellationToken.None);

        result.Should().HaveCount(1);
        result[0].UserId.Should().Be("user@doane.edu");
        result[0].Action.Should().Be("View");
        result[0].Outcome.Should().Be("Success");
    }

    [Fact]
    public async Task Returns_empty_list_when_no_history()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[], 0));

        var handler = new GetChangeNotificationHistoryHandler(_audit);
        var result = await handler.Handle(
            new GetChangeNotificationHistoryQuery("cn-999"), CancellationToken.None);

        result.Should().BeEmpty();
    }

    [Fact]
    public async Task Queries_by_notification_id_as_target_identifier()
    {
        _audit.QueryAsync(default, default, default, default, default, default, default)
            .ReturnsForAnyArgs(((IReadOnlyList<AuditEntry>)[], 0));

        var handler = new GetChangeNotificationHistoryHandler(_audit);
        await handler.Handle(new GetChangeNotificationHistoryQuery("cn-007"), CancellationToken.None);

        await _audit.Received(1).QueryAsync(
            Arg.Any<int>(), Arg.Any<int>(),
            targetIdentifier: "cn-007",
            cancellationToken: Arg.Any<CancellationToken>());
    }
}

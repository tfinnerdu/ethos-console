using EthosCn.Application.ChangeNotifications.Queries;
using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.ChangeNotifications;

public class GetChangeNotificationByIdHandlerTests
{
    private readonly IChangeNotificationRepository _repo = Substitute.For<IChangeNotificationRepository>();
    private readonly IAuditRepository _audit = Substitute.For<IAuditRepository>();
    private readonly ICurrentUserService _user = Substitute.For<ICurrentUserService>();

    public GetChangeNotificationByIdHandlerTests()
    {
        _user.UserId.Returns("test-user");
        _user.DisplayName.Returns("Test User");
    }

    [Fact]
    public async Task Returns_mapped_dto_when_notification_found()
    {
        _repo.GetByIdAsync("cn-001", default)
            .ReturnsForAnyArgs(new ChangeNotification
            {
                Id = "cn-001",
                ResourceName = "persons",
                Description = "Person change notification",
                Status = NotificationStatus.Enabled,
                ParagraphCode = "ETHOS.PERSONS.PARA",
                ProcessCode = "INTG-PERSON"
            });

        var handler = new GetChangeNotificationByIdHandler(_repo, _audit, _user);
        var result = await handler.Handle(new GetChangeNotificationByIdQuery("cn-001"), CancellationToken.None);

        result.Should().NotBeNull();
        result!.Id.Should().Be("cn-001");
        result.ResourceName.Should().Be("persons");
        result.Status.Should().Be("Enabled");
        result.ParagraphCode.Should().Be("ETHOS.PERSONS.PARA");
    }

    [Fact]
    public async Task Returns_null_when_notification_not_found()
    {
        _repo.GetByIdAsync(default!, default).ReturnsForAnyArgs((ChangeNotification?)null);

        var handler = new GetChangeNotificationByIdHandler(_repo, _audit, _user);
        var result = await handler.Handle(new GetChangeNotificationByIdQuery("missing"), CancellationToken.None);

        result.Should().BeNull();
    }

    [Fact]
    public async Task Writes_success_audit_entry_when_found()
    {
        _repo.GetByIdAsync(default!, default)
            .ReturnsForAnyArgs(new ChangeNotification { Id = "cn-001", ResourceName = "persons" });

        var handler = new GetChangeNotificationByIdHandler(_repo, _audit, _user);
        await handler.Handle(new GetChangeNotificationByIdQuery("cn-001"), CancellationToken.None);

        await _audit.Received(1).WriteAsync(
            Arg.Is<AuditEntry>(e => e.Outcome == AuditOutcome.Success && e.TargetIdentifier == "cn-001"),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Writes_failure_audit_entry_when_not_found()
    {
        _repo.GetByIdAsync(default!, default).ReturnsForAnyArgs((ChangeNotification?)null);

        var handler = new GetChangeNotificationByIdHandler(_repo, _audit, _user);
        await handler.Handle(new GetChangeNotificationByIdQuery("missing"), CancellationToken.None);

        await _audit.Received(1).WriteAsync(
            Arg.Is<AuditEntry>(e => e.Outcome == AuditOutcome.Failure),
            Arg.Any<CancellationToken>());
    }
}

using EthosCn.Application.ChangeNotifications.Queries;
using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.ChangeNotifications;

public class GetParagraphHandlerTests
{
    private readonly IChangeNotificationRepository _repo = Substitute.For<IChangeNotificationRepository>();
    private readonly IAuditRepository _audit = Substitute.For<IAuditRepository>();
    private readonly ICurrentUserService _user = Substitute.For<ICurrentUserService>();

    public GetParagraphHandlerTests()
    {
        _user.UserId.Returns("test-user");
        _user.DisplayName.Returns("Test User");
    }

    [Fact]
    public async Task Returns_paragraph_dto_when_source_found()
    {
        _repo.GetParagraphSourceAsync("ETHOS.PARA", default)
            .ReturnsForAnyArgs("SUBROUTINE ETHOS.PARA\nEND");

        var handler = new GetParagraphHandler(_repo, _audit, _user);
        var result = await handler.Handle(
            new GetParagraphQuery("cn-001", "ETHOS.PARA"), CancellationToken.None);

        result.Should().NotBeNull();
        result!.Code.Should().Be("ETHOS.PARA");
        result.Source.Should().Contain("SUBROUTINE");
    }

    [Fact]
    public async Task Returns_null_when_paragraph_source_not_found()
    {
        _repo.GetParagraphSourceAsync(default!, default).ReturnsForAnyArgs((string?)null);

        var handler = new GetParagraphHandler(_repo, _audit, _user);
        var result = await handler.Handle(
            new GetParagraphQuery("cn-001", "MISSING.PARA"), CancellationToken.None);

        result.Should().BeNull();
    }

    [Fact]
    public async Task Writes_view_paragraph_audit_entry()
    {
        _repo.GetParagraphSourceAsync(default!, default)
            .ReturnsForAnyArgs("SUBROUTINE ETHOS.PARA\nEND");

        var handler = new GetParagraphHandler(_repo, _audit, _user);
        await handler.Handle(new GetParagraphQuery("cn-001", "ETHOS.PARA"), CancellationToken.None);

        await _audit.Received(1).WriteAsync(
            Arg.Is<AuditEntry>(e =>
                e.Action == AuditAction.ViewParagraph &&
                e.TargetType == "Paragraph" &&
                e.TargetIdentifier == "ETHOS.PARA"),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Writes_failure_audit_when_paragraph_not_found()
    {
        _repo.GetParagraphSourceAsync(default!, default).ReturnsForAnyArgs((string?)null);

        var handler = new GetParagraphHandler(_repo, _audit, _user);
        await handler.Handle(new GetParagraphQuery("cn-001", "MISSING"), CancellationToken.None);

        await _audit.Received(1).WriteAsync(
            Arg.Is<AuditEntry>(e => e.Outcome == AuditOutcome.Failure),
            Arg.Any<CancellationToken>());
    }
}

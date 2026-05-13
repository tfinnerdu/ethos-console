using CNM.Application.ChangeNotifications.Queries;
using CNM.Application.Common.Interfaces;
using CNM.Domain.Entities;
using CNM.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace CNM.Application.Tests.ChangeNotifications;

public class GetChangeNotificationsHandlerTests
{
    private readonly IChangeNotificationRepository _repo = Substitute.For<IChangeNotificationRepository>();
    private readonly IAuditRepository _audit = Substitute.For<IAuditRepository>();
    private readonly ICurrentUserService _user = Substitute.For<ICurrentUserService>();

    public GetChangeNotificationsHandlerTests()
    {
        _user.UserId.Returns("test-user");
        _user.DisplayName.Returns("Test User");
    }

    [Fact]
    public async Task Returns_mapped_list_items()
    {
        _repo.GetAllAsync(default, default, default)
            .ReturnsForAnyArgs([
                new ChangeNotification
                {
                    Id = "cn-001",
                    ResourceName = "persons",
                    Description = "Person change notification",
                    Status = NotificationStatus.Enabled,
                    ParagraphCode = "ETHOS.PERSONS.PARA"
                }
            ]);

        var handler = new GetChangeNotificationsHandler(_repo, _audit, _user);
        var result = await handler.Handle(new GetChangeNotificationsQuery(), CancellationToken.None);

        result.Should().HaveCount(1);
        result[0].Id.Should().Be("cn-001");
        result[0].Status.Should().Be("Enabled");
        result[0].HasParagraph.Should().BeTrue();
    }
}

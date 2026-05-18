using EthosCn.Application.Common.Interfaces;
using EthosCn.Application.Diagnostics.Queries;
using EthosCn.Domain.Entities;
using EthosCn.Domain.Enums;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.Diagnostics;

public class GetSubscriptionPublishingDiagnosticHandlerTests
{
    private readonly IResourceRepository _resources = Substitute.For<IResourceRepository>();
    private readonly IChangeNotificationRepository _notifications = Substitute.For<IChangeNotificationRepository>();

    private static ChangeNotification Cn(string name) =>
        new() { Id = name, ResourceName = name };

    private static EedmResource Resource(string name) =>
        new() { Name = name, DisplayName = name };

    [Fact]
    public async Task Identifies_resources_subscribed_but_not_published()
    {
        _resources.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)[Resource("persons"), Resource("students")]);
        _notifications.GetAllAsync(cancellationToken: default).ReturnsForAnyArgs(
            (IReadOnlyList<ChangeNotification>)[Cn("persons")]);

        var handler = new GetSubscriptionPublishingDiagnosticHandler(_resources, _notifications);
        var result = await handler.Handle(new GetSubscriptionPublishingDiagnosticQuery(), CancellationToken.None);

        result.SubscribedNotPublished.Should().ContainSingle().Which.Should().Be("students");
    }

    [Fact]
    public async Task Identifies_resources_published_but_not_subscribed()
    {
        _resources.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)[Resource("persons")]);
        _notifications.GetAllAsync(cancellationToken: default).ReturnsForAnyArgs(
            (IReadOnlyList<ChangeNotification>)[Cn("persons"), Cn("courses")]);

        var handler = new GetSubscriptionPublishingDiagnosticHandler(_resources, _notifications);
        var result = await handler.Handle(new GetSubscriptionPublishingDiagnosticQuery(), CancellationToken.None);

        result.PublishedNotSubscribed.Should().ContainSingle().Which.Should().Be("courses");
    }

    [Fact]
    public async Task Identifies_aligned_resources()
    {
        _resources.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)[Resource("persons"), Resource("students")]);
        _notifications.GetAllAsync(cancellationToken: default).ReturnsForAnyArgs(
            (IReadOnlyList<ChangeNotification>)[Cn("persons"), Cn("students")]);

        var handler = new GetSubscriptionPublishingDiagnosticHandler(_resources, _notifications);
        var result = await handler.Handle(new GetSubscriptionPublishingDiagnosticQuery(), CancellationToken.None);

        result.Aligned.Should().BeEquivalentTo(["persons", "students"]);
        result.SubscribedNotPublished.Should().BeEmpty();
        result.PublishedNotSubscribed.Should().BeEmpty();
    }

    [Fact]
    public async Task Reports_correct_totals()
    {
        _resources.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)[Resource("persons"), Resource("students")]);
        _notifications.GetAllAsync(cancellationToken: default).ReturnsForAnyArgs(
            (IReadOnlyList<ChangeNotification>)[Cn("persons"), Cn("courses"), Cn("sections")]);

        var handler = new GetSubscriptionPublishingDiagnosticHandler(_resources, _notifications);
        var result = await handler.Handle(new GetSubscriptionPublishingDiagnosticQuery(), CancellationToken.None);

        result.TotalSubscribed.Should().Be(2);
        result.TotalPublished.Should().Be(3);
    }

    [Fact]
    public async Task Comparison_is_case_insensitive()
    {
        _resources.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)[Resource("Persons")]);
        _notifications.GetAllAsync(cancellationToken: default).ReturnsForAnyArgs(
            (IReadOnlyList<ChangeNotification>)[Cn("persons")]);

        var handler = new GetSubscriptionPublishingDiagnosticHandler(_resources, _notifications);
        var result = await handler.Handle(new GetSubscriptionPublishingDiagnosticQuery(), CancellationToken.None);

        result.Aligned.Should().ContainSingle();
        result.SubscribedNotPublished.Should().BeEmpty();
    }
}

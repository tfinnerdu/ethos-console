using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.Diagnostics;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class DiagnosticsEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task GetSubscriptionPublishing_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/diagnostics/subscription-publishing");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task GetSubscriptionPublishing_returns_diff_dto()
    {
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<SubscriptionPublishingDiffDto>(
            "/api/v1/diagnostics/subscription-publishing");
        dto.Should().NotBeNull();
        dto!.TotalSubscribed.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task GetSubscriptionPublishing_all_subscribed_appear_as_not_published_when_colleague_stub_returns_empty()
    {
        // The Colleague stub returns an empty list, so every subscribed resource
        // should appear in SubscribedNotPublished.
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<SubscriptionPublishingDiffDto>(
            "/api/v1/diagnostics/subscription-publishing");
        dto!.SubscribedNotPublished.Should().HaveCount(dto.TotalSubscribed);
        dto.Aligned.Should().BeEmpty();
        dto.PublishedNotSubscribed.Should().BeEmpty();
    }
}

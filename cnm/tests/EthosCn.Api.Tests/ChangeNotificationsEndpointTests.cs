using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.ChangeNotifications;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class ChangeNotificationsEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task GetAll_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task GetAll_returns_list()
    {
        var client = factory.CreateClient();
        var items = await client.GetFromJsonAsync<List<ChangeNotificationListItemDto>>(
            "/api/v1/change-notifications");
        items.Should().NotBeNull();
    }

    [Fact]
    public async Task GetAll_with_resource_filter_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications?resource=persons");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task GetAll_with_status_filter_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications?status=Enabled");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task GetById_returns_404_for_unknown_id()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications/does-not-exist");
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task GetParagraph_returns_404_for_unknown_notification()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications/does-not-exist/paragraph");
        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }

    [Fact]
    public async Task GetHistory_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/change-notifications/any-id/history");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Theory]
    [InlineData("PUT",    "/api/v1/change-notifications/cn-001")]
    [InlineData("POST",   "/api/v1/change-notifications")]
    [InlineData("POST",   "/api/v1/change-notifications/cn-001/enable")]
    [InlineData("POST",   "/api/v1/change-notifications/cn-001/disable")]
    [InlineData("POST",   "/api/v1/change-notifications/bulk/status")]
    [InlineData("DELETE", "/api/v1/change-notifications/cn-001")]
    public async Task Write_endpoints_return_501(string method, string url)
    {
        var client = factory.CreateClient();
        var request = new HttpRequestMessage(new HttpMethod(method), url);
        if (method is "PUT" or "POST")
            request.Content = new StringContent("{}", System.Text.Encoding.UTF8, "application/json");

        var response = await client.SendAsync(request);
        response.StatusCode.Should().Be(HttpStatusCode.NotImplemented);
    }
}

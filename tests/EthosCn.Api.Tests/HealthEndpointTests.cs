using System.Net;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class HealthEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Health_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/health");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Health_response_contains_status_ok()
    {
        var client = factory.CreateClient();
        var body = await client.GetStringAsync("/api/v1/health");
        body.Should().Contain("ok");
    }
}

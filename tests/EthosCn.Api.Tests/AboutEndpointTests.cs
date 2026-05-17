using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.About;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class AboutEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Get_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/about");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Get_returns_about_dto()
    {
        var client = factory.CreateClient();
        // Version is null until Colleague is connected; shape must still deserialize cleanly.
        var dto = await client.GetFromJsonAsync<ColleagueAboutDto>("/api/v1/about");
        dto.Should().NotBeNull();
    }
}

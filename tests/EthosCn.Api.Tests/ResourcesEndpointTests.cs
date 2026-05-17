using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.Resources;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class ResourcesEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Get_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/resources");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Get_returns_all_41_subscribed_resources()
    {
        var client = factory.CreateClient();
        var items = await client.GetFromJsonAsync<List<EedmResourceDto>>("/api/v1/resources");
        items.Should().HaveCount(41);
    }

    [Fact]
    public async Task Get_includes_standard_eedm_resources()
    {
        var client = factory.CreateClient();
        var items = await client.GetFromJsonAsync<List<EedmResourceDto>>("/api/v1/resources");
        items!.Select(r => r.Name).Should().Contain("persons", "sections", "students");
    }

    [Fact]
    public async Task Get_includes_vendor_d45_resources()
    {
        var client = factory.CreateClient();
        var items = await client.GetFromJsonAsync<List<EedmResourceDto>>("/api/v1/resources");
        items!.Where(r => r.Name.StartsWith("d45-")).Should().HaveCount(4);
    }

    [Fact]
    public async Task Get_includes_institution_x_dp_resources()
    {
        var client = factory.CreateClient();
        var items = await client.GetFromJsonAsync<List<EedmResourceDto>>("/api/v1/resources");
        items!.Where(r => r.Name.StartsWith("x-dp-")).Should().HaveCount(2);
    }
}

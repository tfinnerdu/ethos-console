using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.Me;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class MeEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Get_returns_200()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/me");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Get_returns_dev_user_identity()
    {
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<UserInfoDto>("/api/v1/me");
        dto.Should().NotBeNull();
        dto!.UserId.Should().Be("dev-user");
    }

    [Fact]
    public async Task Get_includes_admin_role_for_dev_user()
    {
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<UserInfoDto>("/api/v1/me");
        dto!.Roles.Should().Contain("CNM.Admin");
    }
}

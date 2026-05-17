using System.Net;
using System.Net.Http.Json;
using EthosCn.Contracts.AuditLog;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class AuditLogEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Get_returns_200_for_admin_user()
    {
        // Dev user has CNM.Admin role via DevAuthHandler.
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/audit-log");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task Get_returns_paged_result()
    {
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<PagedAuditLogDto>("/api/v1/audit-log");
        dto.Should().NotBeNull();
        dto!.Page.Should().Be(1);
        dto.PageSize.Should().Be(50);
    }

    [Fact]
    public async Task Get_with_custom_page_size_reflects_in_response()
    {
        var client = factory.CreateClient();
        var dto = await client.GetFromJsonAsync<PagedAuditLogDto>("/api/v1/audit-log?page=1&pageSize=10");
        dto!.PageSize.Should().Be(10);
    }
}

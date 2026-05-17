using System.Net;
using System.Text.Json;
using FluentAssertions;
using Xunit;

namespace EthosCn.Api.Tests;

public class HealthDeepEndpointTests(CnmWebApplicationFactory factory)
    : IClassFixture<CnmWebApplicationFactory>
{
    [Fact]
    public async Task Deep_returns_json_with_check_entries()
    {
        var client = factory.CreateClient();
        var response = await client.GetAsync("/api/v1/health/deep");

        // 200 = healthy, 503 = degraded/unhealthy — either is a valid response shape.
        response.StatusCode.Should().BeOneOf(HttpStatusCode.OK, HttpStatusCode.ServiceUnavailable);

        var body = await response.Content.ReadAsStringAsync();
        var doc = JsonDocument.Parse(body);
        doc.RootElement.TryGetProperty("status", out _).Should().BeTrue();
        doc.RootElement.TryGetProperty("checks", out var checks).Should().BeTrue();
        checks.EnumerateObject().Should().NotBeEmpty();
    }

    [Fact]
    public async Task Deep_includes_database_check()
    {
        var client = factory.CreateClient();
        var body = await client.GetStringAsync(
            "/api/v1/health/deep").ContinueWith(t =>
        {
            // Accept either status code — just want the body.
            return t.Result;
        });

        // Swallow the exception from non-2xx; we just want to inspect the body.
        var response = await client.GetAsync("/api/v1/health/deep");
        var json = await response.Content.ReadAsStringAsync();
        json.Should().Contain("database");
    }

    [Fact]
    public async Task Deep_includes_colleague_api_check()
    {
        var response = await factory.CreateClient().GetAsync("/api/v1/health/deep");
        var json = await response.Content.ReadAsStringAsync();
        json.Should().Contain("colleague-api");
    }

    [Fact]
    public async Task Deep_includes_resources_seeded_check()
    {
        var response = await factory.CreateClient().GetAsync("/api/v1/health/deep");
        var json = await response.Content.ReadAsStringAsync();
        json.Should().Contain("resources-seeded");
    }
}

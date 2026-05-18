using EthosCn.Infrastructure.Colleague.WebApi;
using FluentAssertions;
using NSubstitute;
using EthosCn.Application.Common.Interfaces;
using EthosCn.Infrastructure.Colleague.WebApi;
using Xunit;

namespace EthosCn.Infrastructure.Tests.Repositories;

/// <summary>
/// Characterization tests for the ChangeNotificationRepository stub.
///
/// These tests are NOT aspirational — they document the current known behavior
/// of the intentional stub that exists until §0.2 pre-work is complete.
///
/// If you wire up the real Colleague Web API and one of these "returns empty"
/// assertions fails, that's the test doing its job: delete the test (or replace
/// it with a real assertion) once the implementation is live.
/// </summary>
public class ChangeNotificationRepositoryStubTests
{
    private readonly IChangeNotificationRepository _repo =
        new ChangeNotificationRepository(Substitute.For<IColleagueWebApiClient>());

    [Fact]
    public async Task GetAllAsync_returns_empty_list_while_stubbed()
    {
        // Known stub behavior — §0.2 will replace this with real data.
        var result = await _repo.GetAllAsync();
        result.Should().BeEmpty(
            "ChangeNotificationRepository is intentionally stubbed until §0.2. " +
            "If you see real data here, replace this test with a real assertion.");
    }

    [Fact]
    public async Task GetAllAsync_with_resource_filter_returns_empty_while_stubbed()
    {
        var result = await _repo.GetAllAsync(resourceFilter: "persons");
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetAllAsync_with_status_filter_returns_empty_while_stubbed()
    {
        var result = await _repo.GetAllAsync(statusFilter: "Enabled");
        result.Should().BeEmpty();
    }

    [Fact]
    public async Task GetByIdAsync_returns_null_while_stubbed()
    {
        var result = await _repo.GetByIdAsync("any-id");
        result.Should().BeNull(
            "ChangeNotificationRepository.GetByIdAsync is intentionally stubbed. " +
            "Replace this test when §0.2 is implemented.");
    }

    [Fact]
    public async Task GetParagraphSourceAsync_returns_null_while_stubbed()
    {
        var result = await _repo.GetParagraphSourceAsync("ETHOS.PARA");
        result.Should().BeNull(
            "GetParagraphSourceAsync is intentionally stubbed until §0.1 DAS path is wired.");
    }

    [Fact]
    public async Task GetAllAsync_does_not_call_colleague_client_while_stubbed()
    {
        // Confirms the stub truly does not touch the client, so it is safe
        // to run without VPN / Colleague credentials.
        var mockClient = Substitute.For<IColleagueWebApiClient>();
        var repo = new ChangeNotificationRepository(mockClient);

        await repo.GetAllAsync();

        // No methods on IColleagueWebApiClient should have been called.
        mockClient.ReceivedCalls().Should().BeEmpty(
            "The stub must not call Colleague Web API — it must be safe to run offline.");
    }
}

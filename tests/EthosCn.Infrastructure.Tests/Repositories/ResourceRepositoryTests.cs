using EthosCn.Infrastructure.Colleague.WebApi;
using FluentAssertions;
using Xunit;

namespace EthosCn.Infrastructure.Tests.Repositories;

public class ResourceRepositoryTests
{
    private static readonly ResourceRepository Repo = new();

    [Fact]
    public async Task Returns_41_subscribed_resources()
    {
        var result = await Repo.GetAllAsync();
        result.Should().HaveCount(41);
    }

    [Fact]
    public async Task Contains_35_standard_eedm_resources()
    {
        var result = await Repo.GetAllAsync();
        result.Where(r => !r.Name.StartsWith("d45-") && !r.Name.StartsWith("x-"))
              .Should().HaveCount(35);
    }

    [Fact]
    public async Task Contains_4_vendor_d45_resources()
    {
        var result = await Repo.GetAllAsync();
        result.Where(r => r.Name.StartsWith("d45-")).Should().HaveCount(4);
    }

    [Fact]
    public async Task Contains_2_institution_x_dp_resources()
    {
        var result = await Repo.GetAllAsync();
        result.Where(r => r.Name.StartsWith("x-dp-")).Should().HaveCount(2);
    }

    [Fact]
    public async Task All_resources_have_display_names()
    {
        var result = await Repo.GetAllAsync();
        result.Should().AllSatisfy(r => r.DisplayName.Should().NotBeNullOrWhiteSpace());
    }

    [Fact]
    public async Task All_resources_have_unique_names()
    {
        var result = await Repo.GetAllAsync();
        result.Select(r => r.Name).Should().OnlyHaveUniqueItems();
    }

    [Theory]
    [InlineData("persons")]
    [InlineData("students")]
    [InlineData("sections")]
    [InlineData("courses")]
    [InlineData("x-dp-comments")]
    [InlineData("x-dp-restricted-comments")]
    [InlineData("d45-user-account")]
    public async Task Contains_expected_resource(string name)
    {
        var result = await Repo.GetAllAsync();
        result.Select(r => r.Name).Should().Contain(name);
    }
}

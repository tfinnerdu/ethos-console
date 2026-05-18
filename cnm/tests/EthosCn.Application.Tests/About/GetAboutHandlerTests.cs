using EthosCn.Application.About.Queries;
using EthosCn.Application.Common.Interfaces;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.About;

public class GetAboutHandlerTests
{
    private readonly IColleagueAboutRepository _repo = Substitute.For<IColleagueAboutRepository>();

    [Fact]
    public async Task Returns_version_from_repository()
    {
        _repo.GetVersionAsync(default).ReturnsForAnyArgs("2.9.0.0");

        var handler = new GetAboutHandler(_repo);
        var result = await handler.Handle(new GetAboutQuery(), CancellationToken.None);

        result.Version.Should().Be("2.9.0.0");
    }

    [Fact]
    public async Task Returns_null_version_when_colleague_unavailable()
    {
        _repo.GetVersionAsync(default).ReturnsForAnyArgs((string?)null);

        var handler = new GetAboutHandler(_repo);
        var result = await handler.Handle(new GetAboutQuery(), CancellationToken.None);

        result.Version.Should().BeNull();
    }
}

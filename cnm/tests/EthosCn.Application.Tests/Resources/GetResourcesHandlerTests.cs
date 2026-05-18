using EthosCn.Application.Common.Interfaces;
using EthosCn.Application.Resources.Queries;
using EthosCn.Domain.Entities;
using FluentAssertions;
using NSubstitute;
using Xunit;

namespace EthosCn.Application.Tests.Resources;

public class GetResourcesHandlerTests
{
    private readonly IResourceRepository _repo = Substitute.For<IResourceRepository>();

    [Fact]
    public async Task Returns_mapped_resource_dtos()
    {
        _repo.GetAllAsync(default).ReturnsForAnyArgs(
            (IReadOnlyList<EedmResource>)
            [
                new EedmResource { Name = "persons",  DisplayName = "Persons",  Description = null },
                new EedmResource { Name = "students", DisplayName = "Students", Description = "Student records" },
            ]);

        var handler = new GetResourcesHandler(_repo);
        var result = await handler.Handle(new GetResourcesQuery(), CancellationToken.None);

        result.Should().HaveCount(2);
        result[0].Name.Should().Be("persons");
        result[1].Description.Should().Be("Student records");
    }

    [Fact]
    public async Task Returns_empty_list_when_no_resources()
    {
        _repo.GetAllAsync(default).ReturnsForAnyArgs((IReadOnlyList<EedmResource>)[]);

        var handler = new GetResourcesHandler(_repo);
        var result = await handler.Handle(new GetResourcesQuery(), CancellationToken.None);

        result.Should().BeEmpty();
    }
}

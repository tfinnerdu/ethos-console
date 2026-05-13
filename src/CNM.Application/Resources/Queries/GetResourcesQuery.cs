using CNM.Application.Common.Interfaces;
using CNM.Contracts.Resources;
using MediatR;

namespace CNM.Application.Resources.Queries;

public record GetResourcesQuery : IRequest<IReadOnlyList<EedmResourceDto>>;

internal sealed class GetResourcesHandler(
    IResourceRepository repository
) : IRequestHandler<GetResourcesQuery, IReadOnlyList<EedmResourceDto>>
{
    public async Task<IReadOnlyList<EedmResourceDto>> Handle(
        GetResourcesQuery request,
        CancellationToken cancellationToken)
    {
        var resources = await repository.GetAllAsync(cancellationToken);

        return resources
            .Select(r => new EedmResourceDto(r.Name, r.DisplayName, r.Description))
            .ToList();
    }
}

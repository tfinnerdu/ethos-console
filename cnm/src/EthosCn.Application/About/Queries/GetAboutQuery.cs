using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.About;
using MediatR;

namespace EthosCn.Application.About.Queries;

public record GetAboutQuery : IRequest<ColleagueAboutDto>;

internal sealed class GetAboutHandler(
    IColleagueAboutRepository repository
) : IRequestHandler<GetAboutQuery, ColleagueAboutDto>
{
    public async Task<ColleagueAboutDto> Handle(GetAboutQuery request, CancellationToken cancellationToken)
    {
        var version = await repository.GetVersionAsync(cancellationToken);
        return new ColleagueAboutDto(version);
    }
}

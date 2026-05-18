using EthosCn.Application.Common.Interfaces;

namespace EthosCn.Infrastructure.Colleague.WebApi.About;

internal sealed class ColleagueAboutRepository(IColleagueWebApiClient client) : IColleagueAboutRepository
{
    public async Task<string?> GetVersionAsync(CancellationToken cancellationToken = default)
    {
        var response = await client.GetAboutAsync(cancellationToken);
        return response.ProductVersion;
    }
}

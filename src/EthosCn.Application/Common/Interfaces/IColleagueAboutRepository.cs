namespace EthosCn.Application.Common.Interfaces;

public interface IColleagueAboutRepository
{
    Task<string?> GetVersionAsync(CancellationToken cancellationToken = default);
}

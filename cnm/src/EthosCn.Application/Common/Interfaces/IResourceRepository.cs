using EthosCn.Domain.Entities;

namespace EthosCn.Application.Common.Interfaces;

public interface IResourceRepository
{
    Task<IReadOnlyList<EedmResource>> GetAllAsync(CancellationToken cancellationToken = default);
}

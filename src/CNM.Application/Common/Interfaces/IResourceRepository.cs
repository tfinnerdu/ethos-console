using CNM.Domain.Entities;

namespace CNM.Application.Common.Interfaces;

public interface IResourceRepository
{
    Task<IReadOnlyList<EedmResource>> GetAllAsync(CancellationToken cancellationToken = default);
}

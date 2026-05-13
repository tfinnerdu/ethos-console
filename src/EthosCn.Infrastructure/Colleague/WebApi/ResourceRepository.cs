using EthosCn.Application.Common.Interfaces;
using EthosCn.Domain.Entities;

namespace EthosCn.Infrastructure.Colleague.WebApi;

/// <summary>
/// Returns the EEDM resources known to the system.
/// Initially seeded from the inventory produced in pre-work §0.1.
/// </summary>
internal sealed class ResourceRepository : IResourceRepository
{
    private static readonly IReadOnlyList<EedmResource> KnownResources =
    [
        new EedmResource { Name = "persons", DisplayName = "Person" },
        new EedmResource { Name = "students", DisplayName = "Student" },
        new EedmResource { Name = "academic-programs", DisplayName = "Academic Program" },
        new EedmResource { Name = "student-academic-credentials", DisplayName = "Academic Credential" },
        new EedmResource { Name = "sites", DisplayName = "Location / Site" },
        new EedmResource { Name = "academic-periods", DisplayName = "Term / Academic Period" },
    ];

    public Task<IReadOnlyList<EedmResource>> GetAllAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(KnownResources);
}

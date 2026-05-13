using CNM.Application.Common.Interfaces;
using CNM.Domain.Entities;
using CNM.Domain.Enums;

namespace CNM.Infrastructure.Colleague.WebApi;

/// <summary>
/// Reads change notification configuration from ColleagueWebAPI.
/// Implementation is stubbed until §0.2 endpoint inventory confirms available endpoints.
/// </summary>
internal sealed class ChangeNotificationRepository(IColleagueWebApiClient client) : IChangeNotificationRepository
{
    public Task<IReadOnlyList<ChangeNotification>> GetAllAsync(
        string? resourceFilter = null,
        string? statusFilter = null,
        CancellationToken cancellationToken = default)
    {
        // TODO: call IColleagueWebApiClient once endpoints are confirmed.
        // Return empty list for now so the API surface is exercisable end-to-end.
        IReadOnlyList<ChangeNotification> empty = [];
        return Task.FromResult(empty);
    }

    public Task<ChangeNotification?> GetByIdAsync(string id, CancellationToken cancellationToken = default)
    {
        // TODO: call IColleagueWebApiClient once endpoints are confirmed.
        return Task.FromResult<ChangeNotification?>(null);
    }

    public Task<string?> GetParagraphSourceAsync(string paragraphCode, CancellationToken cancellationToken = default)
    {
        // TODO: call IColleagueWebApiClient once endpoints are confirmed.
        return Task.FromResult<string?>(null);
    }
}

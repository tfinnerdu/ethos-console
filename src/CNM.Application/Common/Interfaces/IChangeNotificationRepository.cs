using CNM.Domain.Entities;

namespace CNM.Application.Common.Interfaces;

public interface IChangeNotificationRepository
{
    Task<IReadOnlyList<ChangeNotification>> GetAllAsync(
        string? resourceFilter = null,
        string? statusFilter = null,
        CancellationToken cancellationToken = default);

    Task<ChangeNotification?> GetByIdAsync(string id, CancellationToken cancellationToken = default);

    Task<string?> GetParagraphSourceAsync(string paragraphCode, CancellationToken cancellationToken = default);
}

using CNM.Application.Common.Interfaces;
using CNM.Contracts.ChangeNotifications;
using CNM.Domain.Enums;
using MediatR;

namespace CNM.Application.ChangeNotifications.Queries;

public record GetChangeNotificationsQuery(
    string? ResourceFilter = null,
    string? StatusFilter = null
) : IRequest<IReadOnlyList<ChangeNotificationListItemDto>>;

internal sealed class GetChangeNotificationsHandler(
    IChangeNotificationRepository repository,
    IAuditRepository audit,
    ICurrentUserService currentUser
) : IRequestHandler<GetChangeNotificationsQuery, IReadOnlyList<ChangeNotificationListItemDto>>
{
    public async Task<IReadOnlyList<ChangeNotificationListItemDto>> Handle(
        GetChangeNotificationsQuery request,
        CancellationToken cancellationToken)
    {
        var notifications = await repository.GetAllAsync(
            request.ResourceFilter,
            request.StatusFilter,
            cancellationToken);

        await audit.WriteAsync(new Domain.Entities.AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = currentUser.UserId,
            UserDisplayName = currentUser.DisplayName,
            Action = AuditAction.View,
            TargetType = "ChangeNotification",
            TargetIdentifier = "(list)",
            Outcome = AuditOutcome.Success,
            CorrelationId = Guid.NewGuid(),
            SourceIp = currentUser.SourceIp
        }, cancellationToken);

        return notifications
            .Select(n => new ChangeNotificationListItemDto(
                n.Id,
                n.ResourceName,
                n.Description,
                n.Status.ToString(),
                n.ParagraphCode is not null,
                n.LastModified))
            .ToList();
    }
}

using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.ChangeNotifications;
using EthosCn.Domain.Enums;
using MediatR;

namespace EthosCn.Application.ChangeNotifications.Queries;

public record GetChangeNotificationByIdQuery(string Id) : IRequest<ChangeNotificationDto?>;

internal sealed class GetChangeNotificationByIdHandler(
    IChangeNotificationRepository repository,
    IAuditRepository audit,
    ICurrentUserService currentUser
) : IRequestHandler<GetChangeNotificationByIdQuery, ChangeNotificationDto?>
{
    public async Task<ChangeNotificationDto?> Handle(
        GetChangeNotificationByIdQuery request,
        CancellationToken cancellationToken)
    {
        var notification = await repository.GetByIdAsync(request.Id, cancellationToken);

        var outcome = notification is not null ? AuditOutcome.Success : AuditOutcome.Failure;

        await audit.WriteAsync(new Domain.Entities.AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = currentUser.UserId,
            UserDisplayName = currentUser.DisplayName,
            Action = AuditAction.View,
            TargetType = "ChangeNotification",
            TargetIdentifier = request.Id,
            Outcome = outcome,
            FailureReason = notification is null ? "Not found" : null,
            CorrelationId = Guid.NewGuid(),
            SourceIp = currentUser.SourceIp
        }, cancellationToken);

        if (notification is null) return null;

        return new ChangeNotificationDto(
            notification.Id,
            notification.ResourceName,
            notification.Description,
            notification.Status.ToString(),
            notification.ParagraphCode,
            notification.ProcessCode,
            notification.Parameters,
            notification.EdpsRules,
            notification.LastModified);
    }
}

using CNM.Application.Common.Interfaces;
using CNM.Contracts.AuditLog;
using MediatR;

namespace CNM.Application.ChangeNotifications.Queries;

public record GetChangeNotificationHistoryQuery(string NotificationId) : IRequest<IReadOnlyList<AuditEntryDto>>;

internal sealed class GetChangeNotificationHistoryHandler(
    IAuditRepository audit
) : IRequestHandler<GetChangeNotificationHistoryQuery, IReadOnlyList<AuditEntryDto>>
{
    public async Task<IReadOnlyList<AuditEntryDto>> Handle(
        GetChangeNotificationHistoryQuery request,
        CancellationToken cancellationToken)
    {
        var (items, _) = await audit.QueryAsync(
            page: 1,
            pageSize: 200,
            targetIdentifier: request.NotificationId,
            cancellationToken: cancellationToken);

        return items
            .Select(e => new AuditEntryDto(
                e.AuditId,
                e.Timestamp,
                e.UserId,
                e.UserDisplayName,
                e.Action.ToString(),
                e.TargetType,
                e.TargetIdentifier,
                e.BeforeState,
                e.AfterState,
                e.Outcome.ToString(),
                e.FailureReason,
                e.CorrelationId,
                e.SourceIp))
            .ToList();
    }
}

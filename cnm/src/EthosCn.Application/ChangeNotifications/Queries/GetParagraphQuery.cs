using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.ChangeNotifications;
using EthosCn.Domain.Enums;
using MediatR;

namespace EthosCn.Application.ChangeNotifications.Queries;

public record GetParagraphQuery(string NotificationId, string ParagraphCode) : IRequest<ParagraphDto?>;

internal sealed class GetParagraphHandler(
    IChangeNotificationRepository repository,
    IAuditRepository audit,
    ICurrentUserService currentUser
) : IRequestHandler<GetParagraphQuery, ParagraphDto?>
{
    public async Task<ParagraphDto?> Handle(
        GetParagraphQuery request,
        CancellationToken cancellationToken)
    {
        var source = await repository.GetParagraphSourceAsync(request.ParagraphCode, cancellationToken);

        var outcome = source is not null ? AuditOutcome.Success : AuditOutcome.Failure;

        await audit.WriteAsync(new Domain.Entities.AuditEntry
        {
            Timestamp = DateTimeOffset.UtcNow,
            UserId = currentUser.UserId,
            UserDisplayName = currentUser.DisplayName,
            Action = AuditAction.ViewParagraph,
            TargetType = "Paragraph",
            TargetIdentifier = request.ParagraphCode,
            Outcome = outcome,
            CorrelationId = Guid.NewGuid(),
            SourceIp = currentUser.SourceIp
        }, cancellationToken);

        if (source is null) return null;

        return new ParagraphDto(request.ParagraphCode, source);
    }
}

using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.AuditLog;
using MediatR;

namespace EthosCn.Application.AuditLog.Queries;

public record GetAuditLogQuery(
    int Page = 1,
    int PageSize = 50,
    string? UserId = null,
    string? TargetIdentifier = null,
    DateTimeOffset? From = null,
    DateTimeOffset? To = null
) : IRequest<PagedAuditLogDto>;

internal sealed class GetAuditLogHandler(
    IAuditRepository audit
) : IRequestHandler<GetAuditLogQuery, PagedAuditLogDto>
{
    public async Task<PagedAuditLogDto> Handle(
        GetAuditLogQuery request,
        CancellationToken cancellationToken)
    {
        var (items, total) = await audit.QueryAsync(
            request.Page,
            request.PageSize,
            request.UserId,
            request.TargetIdentifier,
            request.From,
            request.To,
            cancellationToken);

        var dtos = items
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

        return new PagedAuditLogDto(dtos, total, request.Page, request.PageSize);
    }
}

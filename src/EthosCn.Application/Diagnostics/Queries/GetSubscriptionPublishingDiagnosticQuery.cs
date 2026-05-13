using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.Diagnostics;
using MediatR;

namespace EthosCn.Application.Diagnostics.Queries;

public record GetSubscriptionPublishingDiagnosticQuery : IRequest<SubscriptionPublishingDiffDto>;

internal sealed class GetSubscriptionPublishingDiagnosticHandler(
    IResourceRepository resourceRepository,
    IChangeNotificationRepository notificationRepository
) : IRequestHandler<GetSubscriptionPublishingDiagnosticQuery, SubscriptionPublishingDiffDto>
{
    public async Task<SubscriptionPublishingDiffDto> Handle(
        GetSubscriptionPublishingDiagnosticQuery request,
        CancellationToken cancellationToken)
    {
        var subscribedTask = resourceRepository.GetAllAsync(cancellationToken);
        var publishedTask = notificationRepository.GetAllAsync(cancellationToken: cancellationToken);

        await Task.WhenAll(subscribedTask, publishedTask);

        var subscribedNames = subscribedTask.Result.Select(r => r.Name).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var publishedNames = publishedTask.Result.Select(n => n.ResourceName).ToHashSet(StringComparer.OrdinalIgnoreCase);

        return new SubscriptionPublishingDiffDto(
            SubscribedNotPublished: subscribedNames.Except(publishedNames, StringComparer.OrdinalIgnoreCase).Order().ToList(),
            PublishedNotSubscribed: publishedNames.Except(subscribedNames, StringComparer.OrdinalIgnoreCase).Order().ToList(),
            Aligned: subscribedNames.Intersect(publishedNames, StringComparer.OrdinalIgnoreCase).Order().ToList(),
            TotalSubscribed: subscribedNames.Count,
            TotalPublished: publishedNames.Count
        );
    }
}

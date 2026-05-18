namespace EthosCn.Contracts.Diagnostics;

public record SubscriptionPublishingDiffDto(
    IReadOnlyList<string> SubscribedNotPublished,
    IReadOnlyList<string> PublishedNotSubscribed,
    IReadOnlyList<string> Aligned,
    int TotalSubscribed,
    int TotalPublished
);

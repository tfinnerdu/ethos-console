namespace CNM.Contracts.ChangeNotifications;

public record ChangeNotificationListItemDto(
    string Id,
    string ResourceName,
    string Description,
    string Status,
    bool HasParagraph,
    DateTimeOffset? LastModified
);

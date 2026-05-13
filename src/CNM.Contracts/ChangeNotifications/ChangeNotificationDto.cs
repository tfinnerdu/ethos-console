namespace CNM.Contracts.ChangeNotifications;

public record ChangeNotificationDto(
    string Id,
    string ResourceName,
    string Description,
    string Status,
    string? ParagraphCode,
    string? ProcessCode,
    IReadOnlyList<string> Parameters,
    IReadOnlyList<string> EdpsRules,
    DateTimeOffset? LastModified
);

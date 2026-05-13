using CNM.Domain.Enums;

namespace CNM.Domain.Entities;

public class ChangeNotification
{
    public string Id { get; init; } = string.Empty;
    public string ResourceName { get; init; } = string.Empty;
    public string Description { get; init; } = string.Empty;
    public NotificationStatus Status { get; init; }
    public string? ParagraphCode { get; init; }
    public string? ProcessCode { get; init; }
    public IReadOnlyList<string> Parameters { get; init; } = [];
    public IReadOnlyList<string> EdpsRules { get; init; } = [];
    public DateTimeOffset? LastModified { get; init; }
}

namespace EthosCn.Infrastructure.Colleague.WebApi.EventConfigs;

// Shape confirmed via pre-work §0.2 smoke test against PUT /api/event-configurations.
// Scope note: write path is v1.5+; this DTO exists for completeness.
public class PutEventConfigurationsRequest
{
    public IReadOnlyList<string> ResourceNames { get; set; } = [];
    public string Status { get; set; } = string.Empty;
}

namespace EthosCn.Infrastructure.Colleague.WebApi.EventConfigs;

// Shape confirmed via pre-work §0.2 smoke test against GET /api/event-configurations.
public class EventConfigurationResponse
{
    public string Name { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
}

namespace EthosCn.Infrastructure.Colleague.WebApi.ConfigurationEms;

// Shape confirmed via pre-work §0.2 smoke test against GET /api/configuration/ems/{configId}.
public class EmsConfigurationResponse
{
    public string? ConfigId { get; set; }
    public IReadOnlyList<EmsResourceMapEntry> ResourceMap { get; set; } = [];
}

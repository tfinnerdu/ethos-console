using EthosCn.Infrastructure.Colleague.WebApi.About;
using EthosCn.Infrastructure.Colleague.WebApi.ConfigurationEms;
using EthosCn.Infrastructure.Colleague.WebApi.EventConfigs;
using Refit;

namespace EthosCn.Infrastructure.Colleague.WebApi;

public interface IColleagueWebApiClient
{
    // Confirmed via Web API 2.9 docs + pre-work §0.2 smoke tests.
    // Response field names are placeholders until smoke tests validate exact shapes.

    [Get("/api/about")]
    Task<ColleagueAboutResponse> GetAboutAsync(CancellationToken ct = default);

    [Get("/api/configuration/ems/{configId}")]
    Task<EmsConfigurationResponse> GetEmsConfigurationAsync(string configId, CancellationToken ct = default);

    [Get("/api/event-configurations")]
    Task<IReadOnlyList<EventConfigurationResponse>> GetEventConfigurationsAsync(
        [AliasAs("resourceName")] string? resourceName = null,
        CancellationToken ct = default);

    // v1.5+ — confirmed no Envision dependency; write path deferred to v1.5.
    [Put("/api/event-configurations")]
    Task PutEventConfigurationsAsync([Body] PutEventConfigurationsRequest request, CancellationToken ct = default);

    // Optional; powers environment-awareness / API catalog views.
    [Get("/api/metadata/manifest/{apiDomain}/{apiType}")]
    Task<object> GetMetadataManifestAsync(string apiDomain, string apiType, CancellationToken ct = default);
}

using Xunit;

namespace EthosCn.Infrastructure.Tests.Colleague.WebApi;

/// <summary>
/// Contract tests against the live dev Colleague Web API.
/// Verify real response shapes match our DTOs so an Ellucian upgrade
/// surfaces as a CI failure rather than a runtime surprise.
///
/// Run only when COLLEAGUE_INTEGRATION_TESTS=true (requires VPN + dev credentials).
/// When the env var is absent the tests return immediately (vacuous pass).
/// </summary>
[Trait("Category", "Integration")]
public class ColleagueWebApiContractTests
{
    private static bool IntegrationEnabled =>
        Environment.GetEnvironmentVariable("COLLEAGUE_INTEGRATION_TESTS") == "true";

    [Fact]
    public void About_endpoint_returns_version_string()
    {
        if (!IntegrationEnabled) return;
        // TODO: build IColleagueWebApiClient from real config.
        // Assert response.ProductVersion is not null or empty.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }

    [Fact]
    public void EventConfigurations_endpoint_returns_non_empty_list()
    {
        if (!IntegrationEnabled) return;
        // TODO: GET /api/event-configurations
        // Assert list is non-empty; each item has Name + Status fields.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }

    [Fact]
    public void EventConfigurations_status_values_are_known_strings()
    {
        if (!IntegrationEnabled) return;
        // TODO: assert every Status value is one of the expected strings
        // (e.g. "Enabled", "Disabled") so the domain mapping is safe.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }

    [Fact]
    public void EmsConfiguration_endpoint_returns_resource_map()
    {
        if (!IntegrationEnabled) return;
        // TODO: GET /api/configuration/ems/{configId}
        // Assert ResourceMap is non-empty; confirm configId value from pre-work §0.1.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }

    [Fact]
    public void EmsConfiguration_resource_map_entries_have_required_fields()
    {
        if (!IntegrationEnabled) return;
        // TODO: assert each EmsResourceMapEntry has ResourceName, UrlPath, BusinessProcess.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }

    [Fact]
    public void EventConfigurations_names_are_valid_eedm_resource_names()
    {
        if (!IntegrationEnabled) return;
        // TODO: cross-reference GET /api/event-configurations names against
        // ResourceRepository to validate diagnostic logic end-to-end.
        throw new NotImplementedException("Wire up real client in §0.2 pre-work.");
    }
}

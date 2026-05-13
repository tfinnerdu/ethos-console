namespace EthosCn.Infrastructure.Colleague.WebApi.About;

// Actual shape confirmed via pre-work §0.2 smoke test against /api/about.
// Field names below are placeholder — adjust to match real response.
public class ColleagueAboutResponse
{
    public string? ProductVersion { get; set; }
    public string? ApplicationRelease { get; set; }
    public string? DatabaseRelease { get; set; }
}

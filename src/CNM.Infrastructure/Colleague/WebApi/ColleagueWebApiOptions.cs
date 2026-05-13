namespace CNM.Infrastructure.Colleague.WebApi;

public sealed class ColleagueWebApiOptions
{
    public const string SectionName = "ColleagueWebApi";

    public string BaseUrl { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
    public TimeSpan Timeout { get; set; } = TimeSpan.FromSeconds(30);
}

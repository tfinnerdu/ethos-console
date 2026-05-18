namespace EthosCn.Infrastructure.Colleague.Das;

public sealed class DasOptions
{
    public const string SectionName = "Das";

    public string BaseUrl { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
}

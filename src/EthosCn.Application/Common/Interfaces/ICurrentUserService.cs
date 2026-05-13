namespace EthosCn.Application.Common.Interfaces;

public interface ICurrentUserService
{
    string UserId { get; }
    string DisplayName { get; }
    IReadOnlyList<string> Roles { get; }
    string? SourceIp { get; }
    bool IsInRole(string role);
}

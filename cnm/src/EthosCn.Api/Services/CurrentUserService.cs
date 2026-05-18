using System.Security.Claims;
using EthosCn.Application.Common.Interfaces;

namespace EthosCn.Api.Services;

internal sealed class CurrentUserService(IHttpContextAccessor httpContextAccessor) : ICurrentUserService
{
    private ClaimsPrincipal User =>
        httpContextAccessor.HttpContext?.User ?? throw new InvalidOperationException("No HTTP context.");

    public string UserId =>
        User.FindFirstValue(ClaimTypes.Upn)
        ?? User.FindFirstValue(ClaimTypes.NameIdentifier)
        ?? string.Empty;

    public string DisplayName =>
        User.FindFirstValue(ClaimTypes.Name)
        ?? User.FindFirstValue("name")
        ?? UserId;

    public IReadOnlyList<string> Roles =>
        User.FindAll(ClaimTypes.Role).Select(c => c.Value).ToList();

    public string? SourceIp =>
        httpContextAccessor.HttpContext?.Connection.RemoteIpAddress?.ToString();

    public bool IsInRole(string role) => User.IsInRole(role);
}

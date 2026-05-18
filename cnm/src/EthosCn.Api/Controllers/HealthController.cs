using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/health")]
[AllowAnonymous]
public class HealthController : ControllerBase
{
    private static readonly DateTimeOffset StartTime = DateTimeOffset.UtcNow;

    [HttpGet]
    public IActionResult Get() => Ok(new
    {
        status = "ok",
        service = "cnm-api",
        version = typeof(HealthController).Assembly.GetName().Version?.ToString() ?? "0.0.0",
        uptime_seconds = (long)(DateTimeOffset.UtcNow - StartTime).TotalSeconds
    });
}

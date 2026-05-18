using EthosCn.Application.AuditLog.Queries;
using EthosCn.Contracts.AuditLog;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/audit-log")]
[Authorize(Policy = "CNM.Admin")]
public class AuditLogController(IMediator mediator) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<PagedAuditLogDto>> Get(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? userId = null,
        [FromQuery] string? targetIdentifier = null,
        [FromQuery] DateTimeOffset? from = null,
        [FromQuery] DateTimeOffset? to = null,
        CancellationToken ct = default)
    {
        var result = await mediator.Send(
            new GetAuditLogQuery(page, pageSize, userId, targetIdentifier, from, to), ct);
        return Ok(result);
    }
}

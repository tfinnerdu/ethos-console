using EthosCn.Application.ChangeNotifications.Queries;
using EthosCn.Contracts.ChangeNotifications;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/change-notifications")]
[Authorize(Policy = "CNM.Viewer")]
public class ChangeNotificationsController(IMediator mediator) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<ChangeNotificationListItemDto>>> GetAll(
        [FromQuery] string? resource,
        [FromQuery] string? status,
        CancellationToken ct)
    {
        var result = await mediator.Send(new GetChangeNotificationsQuery(resource, status), ct);
        return Ok(result);
    }

    [HttpGet("{id}")]
    public async Task<ActionResult<ChangeNotificationDto>> GetById(string id, CancellationToken ct)
    {
        var result = await mediator.Send(new GetChangeNotificationByIdQuery(id), ct);
        return result is null ? NotFound() : Ok(result);
    }

    [HttpGet("{id}/paragraph")]
    public async Task<ActionResult<ParagraphDto>> GetParagraph(string id, CancellationToken ct)
    {
        var notification = await mediator.Send(new GetChangeNotificationByIdQuery(id), ct);
        if (notification?.ParagraphCode is null) return NotFound();

        var result = await mediator.Send(new GetParagraphQuery(id, notification.ParagraphCode), ct);
        return result is null ? NotFound() : Ok(result);
    }

    [HttpGet("{id}/history")]
    public async Task<ActionResult<IReadOnlyList<EthosCn.Contracts.AuditLog.AuditEntryDto>>> GetHistory(
        string id, CancellationToken ct)
    {
        var result = await mediator.Send(new GetChangeNotificationHistoryQuery(id), ct);
        return Ok(result);
    }

    // v1.5+ write endpoints — 501 so disabled frontend controls get a consistent response.

    [HttpPut("{id}")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Update(string id) => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });

    [HttpPost]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Create() => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });

    [HttpPost("{id}/enable")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Enable(string id) => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });

    [HttpPost("{id}/disable")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Disable(string id) => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });

    [HttpPost("bulk/status")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult BulkStatus() => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });

    [HttpDelete("{id}")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Delete(string id) => StatusCode(501, new { error = "Not implemented in v1.", code = "NOT_IMPLEMENTED" });
}

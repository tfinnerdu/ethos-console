using CNM.Application.ChangeNotifications.Queries;
using CNM.Contracts.ChangeNotifications;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace CNM.Api.Controllers;

[ApiController]
[Route("api/change-notifications")]
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
    public async Task<ActionResult<IReadOnlyList<CNM.Contracts.AuditLog.AuditEntryDto>>> GetHistory(
        string id, CancellationToken ct)
    {
        var result = await mediator.Send(new GetChangeNotificationHistoryQuery(id), ct);
        return Ok(result);
    }

    // v1.5+ write endpoints — return 501 so the disabled frontend controls
    // get a consistent, expected response if they somehow fire.

    [HttpPut("{id}")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Update(string id) => StatusCode(501, "Not implemented in v1.");

    [HttpPost]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Create() => StatusCode(501, "Not implemented in v1.");

    [HttpPost("{id}/enable")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Enable(string id) => StatusCode(501, "Not implemented in v1.");

    [HttpPost("{id}/disable")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Disable(string id) => StatusCode(501, "Not implemented in v1.");

    [HttpDelete("{id}")]
    [Authorize(Policy = "CNM.Admin")]
    public IActionResult Delete(string id) => StatusCode(501, "Not implemented in v1.");
}

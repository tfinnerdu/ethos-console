using EthosCn.Application.Diagnostics.Queries;
using EthosCn.Contracts.Diagnostics;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/diagnostics")]
[Authorize(Policy = "CNM.Viewer")]
public class DiagnosticsController(IMediator mediator) : ControllerBase
{
    [HttpGet("subscription-publishing")]
    public async Task<ActionResult<SubscriptionPublishingDiffDto>> GetSubscriptionPublishing(CancellationToken ct)
    {
        var result = await mediator.Send(new GetSubscriptionPublishingDiagnosticQuery(), ct);
        return Ok(result);
    }
}

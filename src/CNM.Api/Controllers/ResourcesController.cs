using CNM.Application.Resources.Queries;
using CNM.Contracts.Resources;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace CNM.Api.Controllers;

[ApiController]
[Route("api/resources")]
[Authorize(Policy = "CNM.Viewer")]
public class ResourcesController(IMediator mediator) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<EedmResourceDto>>> Get(CancellationToken ct)
    {
        var result = await mediator.Send(new GetResourcesQuery(), ct);
        return Ok(result);
    }
}

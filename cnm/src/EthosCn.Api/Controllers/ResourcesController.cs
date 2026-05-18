using EthosCn.Application.Resources.Queries;
using EthosCn.Contracts.Resources;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/resources")]
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

using EthosCn.Application.About.Queries;
using EthosCn.Contracts.About;
using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/about")]
[Authorize(Policy = "CNM.Viewer")]
public class AboutController(IMediator mediator) : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<ColleagueAboutDto>> Get(CancellationToken ct)
    {
        var result = await mediator.Send(new GetAboutQuery(), ct);
        return Ok(result);
    }
}

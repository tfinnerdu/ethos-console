using EthosCn.Application.Common.Interfaces;
using EthosCn.Contracts.Me;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EthosCn.Api.Controllers;

[ApiController]
[Route("api/v1/me")]
[Authorize(Policy = "CNM.Viewer")]
public class MeController(ICurrentUserService currentUser) : ControllerBase
{
    [HttpGet]
    public ActionResult<UserInfoDto> Get()
        => Ok(new UserInfoDto(currentUser.UserId, currentUser.DisplayName, currentUser.Roles));
}

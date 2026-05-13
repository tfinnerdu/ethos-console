namespace CNM.Contracts.Me;

public record UserInfoDto(
    string UserId,
    string DisplayName,
    IReadOnlyList<string> Roles
);

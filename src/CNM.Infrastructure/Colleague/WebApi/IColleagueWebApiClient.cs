using Refit;

namespace CNM.Infrastructure.Colleague.WebApi;

/// <summary>
/// Refit interface for ColleagueWebAPI.
/// Endpoints will be populated once §0.2 (endpoint coverage check) is complete.
/// Until then, placeholder methods are stubbed to allow Infrastructure.Tests
/// contract tests to be written against whatever shape the real API exposes.
/// </summary>
public interface IColleagueWebApiClient
{
    // TODO: populate after completing pre-work §0.2 endpoint inventory.
    // Example shape (adjust to actual Colleague endpoint paths/response shapes):
    //
    // [Get("/change-notifications")]
    // Task<ApiResponse<ColleagueChangeNotificationListResponse>> GetChangeNotificationsAsync(CancellationToken ct = default);
    //
    // [Get("/change-notifications/{id}")]
    // Task<ApiResponse<ColleagueChangeNotificationResponse>> GetChangeNotificationByIdAsync(string id, CancellationToken ct = default);
}

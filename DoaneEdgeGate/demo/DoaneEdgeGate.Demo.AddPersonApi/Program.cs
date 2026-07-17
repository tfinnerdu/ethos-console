using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

// Stand-in for the real Colleague Web API's person-create call, for demoing
// DoaneEdgeGate against something other than production. Persists nothing —
// it just echoes back whatever birthDate/timestamp/timezone it received, so
// a demo can show the corrected value actually arriving downstream of the
// gate, not just the gate's own logs.
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .AllowAnyOrigin()
    .AllowAnyMethod()
    .AllowAnyHeader()));

var app = builder.Build();

app.UseCors();

app.MapGet("/health", () => Results.Ok(new { status = "ok", service = "add-person-api-demo" }));

var bareDate = new Regex(@"^\d{4}-\d{2}-\d{2}$", RegexOptions.Compiled);
var centralTimeZone = TimeZoneInfo.FindSystemTimeZoneById("America/Chicago");

// Simulates the actual bug, not just the browser's half of it. Per the doc
// comment on DoaneEdgeGate.Core's DateInstantTransformer: for every US
// timezone, local midnight serializes to a SAME-DATE morning UTC instant —
// the date substring is still correct at that point. The day is only lost
// later, when the real Colleague Web API converts that instant back to
// server-local (Central) and truncates to a date. That's what this
// reproduces: a bare date (already correct, or corrected upstream by the
// gate) has no time/offset to convert and passes through unchanged; an
// instant gets converted to Central and truncated, same as the real system.
string? SimulateColleagueDateStorage(string? raw)
{
    if (string.IsNullOrWhiteSpace(raw)) return raw;
    var trimmed = raw.Trim();
    if (bareDate.IsMatch(trimmed)) return trimmed;
    if (!DateTimeOffset.TryParse(trimmed, CultureInfo.InvariantCulture, DateTimeStyles.None, out var parsed))
        return raw; // not a recognizable date/instant — leave alone rather than crash the demo
    return TimeZoneInfo.ConvertTime(parsed, centralTimeZone).ToString("yyyy-MM-dd");
}

// Field name matches DoaneEdgeGate's own default DateFieldNames ("birthDate"
// among them) and ResponseIdFieldNames ("id") with zero extra config needed.
app.MapPost("/api/persons", async (HttpContext ctx) =>
{
    string raw;
    using (var reader = new StreamReader(ctx.Request.Body))
        raw = await reader.ReadToEndAsync();

    JsonElement body;
    try
    {
        body = JsonSerializer.Deserialize<JsonElement>(raw);
    }
    catch (JsonException)
    {
        return Results.BadRequest(new { error = "request body was not valid JSON" });
    }

    string? Get(string name) =>
        body.ValueKind == JsonValueKind.Object
            && body.TryGetProperty(name, out var v)
            && v.ValueKind == JsonValueKind.String
            ? v.GetString()
            : null;

    var receivedBirthDate = Get("birthDate");

    return Results.Ok(new
    {
        id = Guid.NewGuid().ToString("N")[..8],
        message = "AddPerson demo endpoint — nothing is persisted.",
        receivedBirthDate,
        // What the real Web API would actually end up storing — the field
        // that shows the bug in Off/Shadow (the same shifted date the gate
        // exists to prevent) and the fix in Active (matches receivedBirthDate).
        storedBirthDate = SimulateColleagueDateStorage(receivedBirthDate),
        receivedTimestamp = Get("timestamp"),
        receivedTimezone = Get("timezone"),
    });
});

app.Run();

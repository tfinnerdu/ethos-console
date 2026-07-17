using System.Text.Json;

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

    return Results.Ok(new
    {
        id = Guid.NewGuid().ToString("N")[..8],
        message = "AddPerson demo endpoint — nothing is persisted.",
        receivedBirthDate = Get("birthDate"),
        receivedTimestamp = Get("timestamp"),
        receivedTimezone = Get("timezone"),
    });
});

app.Run();

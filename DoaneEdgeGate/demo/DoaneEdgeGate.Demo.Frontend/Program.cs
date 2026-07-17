// Stand-in for Self-Service, for demoing DoaneEdgeGate without touching
// production. Serves one static page (wwwroot/index.html) that reproduces
// the actual bug — a date-picker's local-midnight value serialized as a
// morning UTC instant — and POSTs it wherever ApiBaseUrl (below) points.
// That's the one setting you repoint at the gate for the demo.
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/config", () => Results.Ok(new
{
    apiBaseUrl = app.Configuration["ApiBaseUrl"] ?? ""
}));

app.Run();

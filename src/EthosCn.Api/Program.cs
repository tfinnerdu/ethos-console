using EthosCn.Api.DevAuth;
using EthosCn.Application;
using EthosCn.Infrastructure;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Serilog;

Log.Logger = new LoggerConfiguration()
    .WriteTo.Console()
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Host.UseSerilog((ctx, services, cfg) =>
        cfg.ReadFrom.Configuration(ctx.Configuration)
           .ReadFrom.Services(services)
           .Enrich.FromLogContext()
           .WriteTo.Console());

    builder.Services
        .AddApplication()
        .AddInfrastructure(builder.Configuration, builder.Environment);

    builder.Services.AddHttpContextAccessor();
    builder.Services.AddScoped<EthosCn.Application.Common.Interfaces.ICurrentUserService,
        EthosCn.Api.Services.CurrentUserService>();

    if (builder.Environment.IsDevelopment())
    {
        builder.Services
            .AddAuthentication("DevAuth")
            .AddScheme<AuthenticationSchemeOptions, DevAuthHandler>("DevAuth", _ => { });
    }
    else
    {
        builder.Services
            .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddJwtBearer(opts => builder.Configuration.Bind("AzureAd", opts));
    }

    builder.Services.AddAuthorization(opts =>
    {
        opts.AddPolicy("CNM.Viewer", policy => policy.RequireAuthenticatedUser());
        opts.AddPolicy("CNM.Admin", policy =>
            policy.RequireAuthenticatedUser()
                  .RequireRole("CNM.Admin"));
    });

    builder.Services.AddControllers();
    builder.Services.AddEndpointsApiExplorer();
    builder.Services.AddSwaggerGen(opts =>
    {
        opts.SwaggerDoc("v1", new() { Title = "CNM API", Version = "v1" });
    });

    builder.Services.AddCors(opts =>
        opts.AddDefaultPolicy(policy =>
            policy.WithOrigins(
                    builder.Configuration.GetSection("Cors:AllowedOrigins").Get<string[]>() ?? [])
                  .AllowAnyHeader()
                  .AllowAnyMethod()
                  .AllowCredentials()));

    var app = builder.Build();

    app.UseSerilogRequestLogging();

    if (app.Environment.IsDevelopment())
    {
        app.UseSwagger();
        app.UseSwaggerUI();
    }

    app.UseCors();
    app.UseAuthentication();
    app.UseAuthorization();
    app.MapControllers();

    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application startup failed");
    throw;
}
finally
{
    Log.CloseAndFlush();
}

// Expose Program to WebApplicationFactory<Program> in integration test projects.
public partial class Program { }

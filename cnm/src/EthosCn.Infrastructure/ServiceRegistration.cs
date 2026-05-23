using EthosCn.Application.Common.Interfaces;
using EthosCn.Infrastructure.Colleague.Das;
using EthosCn.Infrastructure.Colleague.Sql;
using EthosCn.Infrastructure.Colleague.WebApi;
using EthosCn.Infrastructure.Colleague.WebApi.About;
using EthosCn.Infrastructure.Health;
using EthosCn.Infrastructure.Persistence;
using EthosCn.Infrastructure.Repositories;
using Microsoft.AspNetCore.Hosting;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Refit;

namespace EthosCn.Infrastructure;

public static class ServiceRegistration
{
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration,
        IWebHostEnvironment environment)
    {
        // Provider routing for CnmDbContext:
        //   - Cnm:UseSqlite=true  → SQLite (explicit opt-in for tests / non-Windows dev).
        //   - Development + empty ConnectionStrings:CnmDb → SQLite default at
        //     <repo>/console/instance/cnm.db so the service runs end-to-end on a fresh
        //     clone without a SQL Server. Sits next to the Flask console's SQLite.
        //   - Otherwise → SqlServer with the configured connection string (prod path).
        var connectionString = configuration.GetConnectionString("CnmDb");
        var explicitSqlite = configuration.GetValue<bool>("Cnm:UseSqlite");
        var useSqliteDefault = environment.IsDevelopment() && string.IsNullOrWhiteSpace(connectionString);

        if (explicitSqlite || useSqliteDefault)
        {
            if (string.IsNullOrWhiteSpace(connectionString))
                connectionString = $"Data Source={ResolveDefaultSqlitePath()}";

            services.AddDbContext<CnmDbContext>(opts =>
                opts.UseSqlite(
                    connectionString,
                    b => b.MigrationsAssembly(typeof(CnmDbContext).Assembly.FullName)));
        }
        else
        {
            services.AddDbContext<CnmDbContext>(opts =>
                opts.UseSqlServer(
                    connectionString,
                    sql => sql.MigrationsAssembly(typeof(CnmDbContext).Assembly.FullName)));
        }

        if (environment.IsDevelopment())
            services.AddScoped<IAuditRepository, FileAuditRepository>();
        else
            services.AddScoped<IAuditRepository, AuditRepository>();

        services
            .AddOptions<ColleagueWebApiOptions>()
            .Bind(configuration.GetSection(ColleagueWebApiOptions.SectionName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services
            .AddOptions<DasOptions>()
            .Bind(configuration.GetSection(DasOptions.SectionName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services
            .AddOptions<ColleagueSqlOptions>()
            .Bind(configuration.GetSection(ColleagueSqlOptions.SectionName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services
            .AddRefitClient<IColleagueWebApiClient>()
            .ConfigureHttpClient((sp, client) =>
            {
                var opts = configuration
                    .GetSection(ColleagueWebApiOptions.SectionName)
                    .Get<ColleagueWebApiOptions>()!;
                // Fall back to a valid placeholder so DI resolution doesn't throw
                // when ColleagueWebApi:BaseUrl isn't set in local dev.
                client.BaseAddress = new Uri(string.IsNullOrWhiteSpace(opts.BaseUrl)
                    ? "http://localhost"
                    : opts.BaseUrl);
                client.Timeout = opts.Timeout;
            })
            .AddStandardResilienceHandler();

        services.AddScoped<IChangeNotificationRepository, ChangeNotificationRepository>();
        services.AddScoped<IResourceRepository, ResourceRepository>();
        services.AddScoped<IColleagueAboutRepository, ColleagueAboutRepository>();

        services.AddHealthChecks()
            .AddCheck<CnmDatabaseHealthCheck>("database", tags: ["deep"])
            .AddCheck<ColleagueApiHealthCheck>("colleague-api", tags: ["deep"])
            .AddCheck<ResourcesSeededHealthCheck>("resources-seeded", tags: ["deep"]);

        return services;
    }

    /// <summary>
    /// Default SQLite path for the dev/local CnmDb. Lives at
    /// &lt;repo&gt;/console/instance/cnm.db so it sits next to the Flask console's
    /// SQLite file. The instance directory is created on first call.
    /// </summary>
    private static string ResolveDefaultSqlitePath()
    {
        // Walk up from the running assembly's directory until we find the
        // solution file. Falls back to BaseDirectory if the walk fails.
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "ethos-console.sln")))
            dir = dir.Parent;
        var slnDir = dir?.FullName ?? AppContext.BaseDirectory;

        var instanceDir = Path.Combine(slnDir, "console", "instance");
        Directory.CreateDirectory(instanceDir);
        return Path.Combine(instanceDir, "cnm.db");
    }
}

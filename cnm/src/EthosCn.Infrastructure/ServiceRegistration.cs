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
        services.AddDbContext<CnmDbContext>(opts =>
            opts.UseSqlServer(
                configuration.GetConnectionString("CnmDb"),
                sql => sql.MigrationsAssembly(typeof(CnmDbContext).Assembly.FullName)));

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
}

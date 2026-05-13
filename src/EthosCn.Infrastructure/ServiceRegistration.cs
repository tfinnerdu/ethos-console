using EthosCn.Application.Common.Interfaces;
using EthosCn.Infrastructure.Colleague.Das;
using EthosCn.Infrastructure.Colleague.Sql;
using EthosCn.Infrastructure.Colleague.WebApi;
using EthosCn.Infrastructure.Colleague.WebApi.About;
using EthosCn.Infrastructure.Persistence;
using EthosCn.Infrastructure.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Refit;

namespace EthosCn.Infrastructure;

public static class ServiceRegistration
{
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        services.AddDbContext<CnmDbContext>(opts =>
            opts.UseSqlServer(
                configuration.GetConnectionString("CnmDb"),
                sql => sql.MigrationsAssembly(typeof(CnmDbContext).Assembly.FullName)));

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
                client.BaseAddress = new Uri(opts.BaseUrl);
                client.Timeout = opts.Timeout;
            })
            .AddStandardResilienceHandler();

        services.AddScoped<IChangeNotificationRepository, ChangeNotificationRepository>();
        services.AddScoped<IResourceRepository, ResourceRepository>();
        services.AddScoped<IColleagueAboutRepository, ColleagueAboutRepository>();

        return services;
    }
}

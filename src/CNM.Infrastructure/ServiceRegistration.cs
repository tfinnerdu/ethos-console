using CNM.Application.Common.Interfaces;
using CNM.Infrastructure.Colleague.Das;
using CNM.Infrastructure.Colleague.Sql;
using CNM.Infrastructure.Colleague.WebApi;
using CNM.Infrastructure.Persistence;
using CNM.Infrastructure.Repositories;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Refit;

namespace CNM.Infrastructure;

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

        return services;
    }
}

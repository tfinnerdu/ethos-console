using Microsoft.Extensions.DependencyInjection;

namespace CNM.Application;

public static class ServiceRegistration
{
    public static IServiceCollection AddApplication(this IServiceCollection services)
    {
        services.AddMediatR(cfg =>
            cfg.RegisterServicesFromAssembly(typeof(ServiceRegistration).Assembly));

        return services;
    }
}

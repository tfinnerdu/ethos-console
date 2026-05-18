using EthosCn.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace EthosCn.Infrastructure.Persistence;

public class CnmDbContext(DbContextOptions<CnmDbContext> options) : DbContext(options)
{
    public DbSet<AuditEntry> AuditLog => Set<AuditEntry>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(CnmDbContext).Assembly);
    }
}

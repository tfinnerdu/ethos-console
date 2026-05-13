using CNM.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace CNM.Infrastructure.Persistence;

public class CnmDbContext(DbContextOptions<CnmDbContext> options) : DbContext(options)
{
    public DbSet<AuditEntry> AuditLog => Set<AuditEntry>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(CnmDbContext).Assembly);
    }
}

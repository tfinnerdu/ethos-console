using EthosCn.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EthosCn.Infrastructure.Persistence.Configurations;

internal sealed class AuditEntryConfiguration : IEntityTypeConfiguration<AuditEntry>
{
    public void Configure(EntityTypeBuilder<AuditEntry> builder)
    {
        builder.ToTable("AuditLog");
        builder.HasKey(e => e.AuditId);
        builder.Property(e => e.AuditId).UseIdentityColumn();
        builder.Property(e => e.UserId).HasMaxLength(256).IsRequired();
        builder.Property(e => e.UserDisplayName).HasMaxLength(512);
        builder.Property(e => e.Action).HasConversion<string>().HasMaxLength(64);
        builder.Property(e => e.TargetType).HasMaxLength(128).IsRequired();
        builder.Property(e => e.TargetIdentifier).HasMaxLength(512);
        builder.Property(e => e.Outcome).HasConversion<string>().HasMaxLength(32);
        builder.Property(e => e.SourceIp).HasMaxLength(64);
        builder.Property(e => e.BeforeState).HasColumnType("nvarchar(max)");
        builder.Property(e => e.AfterState).HasColumnType("nvarchar(max)");
        builder.Property(e => e.FailureReason).HasColumnType("nvarchar(max)");

        builder.HasIndex(e => e.Timestamp);
        builder.HasIndex(e => e.UserId);
        builder.HasIndex(e => e.TargetIdentifier);
    }
}

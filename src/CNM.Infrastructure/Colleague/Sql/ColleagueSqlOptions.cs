namespace CNM.Infrastructure.Colleague.Sql;

public sealed class ColleagueSqlOptions
{
    public const string SectionName = "ColleagueSql";

    /// <summary>Read-only connection string to the Colleague SQL primary store.</summary>
    public string ConnectionString { get; set; } = string.Empty;
}

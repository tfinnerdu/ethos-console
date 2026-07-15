using System.Text.Json;

namespace DoaneEdgeGate;

/// <summary>
/// Emits one JSON object per line to stdout: timestamp, level, service,
/// request_id, message, plus any extra fields. Matches the Doane service logging
/// standard so this drops into the same log pipeline as the Flask/Conductor stack.
/// </summary>
public static class StructuredLog
{
    public const string Service = "doane-edge-gate";

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull
    };

    public static void Write(string level, string message, string? requestId = null,
        IReadOnlyDictionary<string, object?>? fields = null)
    {
        var entry = new Dictionary<string, object?>
        {
            ["timestamp"] = DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ"),
            ["level"] = level,
            ["service"] = Service,
            ["request_id"] = requestId,
            ["message"] = message
        };
        if (fields != null)
            foreach (var kv in fields)
                entry[kv.Key] = kv.Value;

        Console.WriteLine(JsonSerializer.Serialize(entry, JsonOpts));
    }

    public static void Info(string message, string? requestId = null, IReadOnlyDictionary<string, object?>? fields = null)
        => Write("INFO", message, requestId, fields);

    public static void Warn(string message, string? requestId = null, IReadOnlyDictionary<string, object?>? fields = null)
        => Write("WARN", message, requestId, fields);

    public static void Error(string message, string? requestId = null, IReadOnlyDictionary<string, object?>? fields = null)
        => Write("ERROR", message, requestId, fields);
}

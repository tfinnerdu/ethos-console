using System.Buffers;
using System.Text;
using System.Text.Json;

namespace DoaneEdgeGate.Core;

public sealed record RewriteOutcome(bool Changed, string Json, IReadOnlyList<RewriteRecord> Records);

/// <summary>
/// Applies <see cref="DateInstantTransformer"/> to a JSON body according to the
/// configured <see cref="RewriteStrategy"/>. Rebuilds the JSON preserving
/// structure; only the matched string leaf values change.
/// </summary>
public sealed class PayloadRewriter
{
    private readonly RewriteOptions _opts;
    private readonly HashSet<string> _fieldNames;

    public PayloadRewriter(RewriteOptions opts)
    {
        _opts = opts;
        _fieldNames = new HashSet<string>(opts.DateFieldNames, StringComparer.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Returns the (possibly) rewritten JSON and the list of changes. Throws only
    /// on invalid JSON; the caller decides fail-open vs fail-closed.
    /// </summary>
    public RewriteOutcome Rewrite(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var records = new List<RewriteRecord>();

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions { SkipValidation = true }))
        {
            WriteValue(writer, doc.RootElement, path: "$", propertyEligibleByName: false, records);
        }

        var outJson = Encoding.UTF8.GetString(buffer.WrittenSpan);
        var realChanges = records.Count(r => !r.Reason.StartsWith("unchanged:", StringComparison.Ordinal));
        return new RewriteOutcome(realChanges > 0, outJson, records);
    }

    private void WriteValue(Utf8JsonWriter writer, JsonElement el, string path,
        bool propertyEligibleByName, List<RewriteRecord> records)
    {
        switch (el.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var prop in el.EnumerateObject())
                {
                    writer.WritePropertyName(prop.Name);
                    var eligible = _fieldNames.Contains(prop.Name);
                    WriteValue(writer, prop.Value, $"{path}.{prop.Name}", eligible, records);
                }
                writer.WriteEndObject();
                break;

            case JsonValueKind.Array:
                writer.WriteStartArray();
                var i = 0;
                foreach (var item in el.EnumerateArray())
                {
                    // Array elements inherit the eligibility of the property that
                    // holds the array, so an allowlisted field whose value is a
                    // list of dates is still covered.
                    WriteValue(writer, item, $"{path}[{i}]", propertyEligibleByName, records);
                    i++;
                }
                writer.WriteEndArray();
                break;

            case JsonValueKind.String:
                WriteStringLeaf(writer, el.GetString() ?? "", path, propertyEligibleByName, records);
                break;

            case JsonValueKind.Number:
                writer.WriteRawValue(el.GetRawText());
                break;

            case JsonValueKind.True:
            case JsonValueKind.False:
                writer.WriteBooleanValue(el.GetBoolean());
                break;

            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;

            default:
                writer.WriteRawValue(el.GetRawText());
                break;
        }
    }

    private void WriteStringLeaf(Utf8JsonWriter writer, string value, string path,
        bool eligibleByName, List<RewriteRecord> records)
    {
        var consider = _opts.Strategy switch
        {
            RewriteStrategy.FieldAllowlist => eligibleByName,
            RewriteStrategy.ShapeAll => true,
            _ => eligibleByName
        };

        if (!consider)
        {
            writer.WriteStringValue(value);
            return;
        }

        var result = DateInstantTransformer.Transform(value, _opts.RequireMorningUtcForZ);
        if (result.Changed)
        {
            records.Add(new RewriteRecord(path, value, result.Value, result.Reason));
            writer.WriteStringValue(result.Value);
        }
        else
        {
            if (_opts.LogUnchanged && !string.IsNullOrWhiteSpace(value))
                records.Add(new RewriteRecord(path, value, value, "unchanged:" + result.Reason));
            writer.WriteStringValue(value);
        }
    }
}

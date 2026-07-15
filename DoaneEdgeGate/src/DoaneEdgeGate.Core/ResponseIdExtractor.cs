using System.Text.Json;

namespace DoaneEdgeGate.Core;

/// <summary>
/// Closes the join-key gap documented in DOB-Repair-Tandem-Flow.md section 5: a
/// gate log entry is keyed to the HTTP request (request_id + submitted DOB), but
/// at the moment of the person-create POST the resulting Colleague record ID
/// usually does not exist yet. The gate sees the Web API's response, though, which
/// typically returns the new record's identifier — capturing it here gives a
/// direct join from "what was submitted/rewritten" to "which record it became",
/// instead of falling back to a weaker fuzzy identity join later.
///
/// Never throws. A response that isn't JSON, doesn't parse, or has none of the
/// configured field names simply yields no match — this must never be able to
/// break forwarding the response back to the client.
/// </summary>
public static class ResponseIdExtractor
{
    private const int MaxDepth = 4;

    public static string? TryExtract(byte[] json, IReadOnlySet<string> fieldNames)
    {
        if (json.Length == 0 || fieldNames.Count == 0)
            return null;

        try
        {
            using var doc = JsonDocument.Parse(json);
            return Find(doc.RootElement, fieldNames, depth: 0);
        }
        catch
        {
            // Fail-safe: malformed/unexpected response shape is not this
            // extractor's problem to solve or surface.
            return null;
        }
    }

    private static string? Find(JsonElement el, IReadOnlySet<string> names, int depth)
    {
        if (depth > MaxDepth)
            return null;

        if (el.ValueKind == JsonValueKind.Object)
        {
            // Breadth before depth: prefer a match at this level over a
            // same-named field buried in a nested object, since the common
            // shape is a flat { "id": "...", ... } response.
            foreach (var prop in el.EnumerateObject())
            {
                if (names.Contains(prop.Name) && TryStringify(prop.Value, out var value))
                    return value;
            }
            foreach (var prop in el.EnumerateObject())
            {
                var found = Find(prop.Value, names, depth + 1);
                if (found != null) return found;
            }
        }
        else if (el.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in el.EnumerateArray())
            {
                var found = Find(item, names, depth + 1);
                if (found != null) return found;
            }
        }

        return null;
    }

    private static bool TryStringify(JsonElement value, out string result)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.String:
                result = value.GetString() ?? "";
                return result.Length > 0;
            case JsonValueKind.Number:
                result = value.GetRawText();
                return true;
            default:
                result = "";
                return false;
        }
    }
}

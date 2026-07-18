using System.Text;
using System.Text.Json;
using DoaneEdgeGate.Core;

// ---------------------------------------------------------------------------
// Dependency-free test harness. Exits non-zero on any failure so it works as a
// build gate. Every case below is a realistic scenario from the PD0002124 blast
// radius. The point is not just "does it run" but "does it rewrite exactly the
// bug signature and refuse to touch anything else."
// ---------------------------------------------------------------------------

var t = new Harness();

// === DateInstantTransformer: the core bug signature ===
// Angular serializes local midnight to UTC. For US zones that is a same-date
// morning UTC time, so the date substring is the intended date.
t.Rewrites("Eastern midnight -> date survives",
    "1980-04-03T04:00:00Z", "1980-04-03");
t.Rewrites("Central midnight with millis",
    "1980-04-03T05:00:00.000Z", "1980-04-03");
t.Rewrites("Pacific midnight",
    "1980-04-03T07:00:00Z", "1980-04-03");
t.Rewrites("Mountain midnight, no millis",
    "1980-04-03T06:00:00Z", "1980-04-03");

// The scenario that produced the original -1 day corruption end to end: a
// registrant picks Jan 1 1976; without the gate the server truncates to
// 1975-12-31. The gate forwards the bare date so the year boundary holds.
t.Rewrites("year-boundary: Jan 1 does not become Dec 31",
    "1976-01-01T05:00:00Z", "1976-01-01");

// === Offset and naive forms ===
t.Rewrites("explicit negative offset carries local wall-clock date",
    "1980-04-03T00:00:00-05:00", "1980-04-03");
t.Rewrites("explicit positive offset: wall-clock date is intended",
    "1980-04-03T00:00:00+02:00", "1980-04-03");
t.Rewrites("naive local datetime (no zone) drops the time",
    "1980-04-03T00:00:00", "1980-04-03");

// === Fail-safe no-ops: the gate must leave these alone ===
t.Keeps("already date-only becomes a no-op (survives an Ellucian fix)",
    "1980-04-03", "already-date-only");
t.Keeps("empty string", "", "empty");
t.Keeps("whitespace only", "   ", "empty");
t.Keeps("plain non-date text", "not a date", "not-iso-instant");
t.Keeps("bare but impossible date", "1980-13-45", "date-only-but-invalid");
t.Keeps("instant with impossible date part (Feb 30)",
    "1980-02-30T04:00:00Z", "invalid-date-part");
t.Keeps("time-only, no date, is not an instant we touch",
    "T04:00:00Z", "not-iso-instant");

// === The morning-UTC guard ===
// A Z instant in the afternoon did not come from a Western local-midnight
// origin, so with the guard on we do not touch it.
t.Keeps("afternoon Z is not the bug signature (guard on)",
    "1980-04-03T18:00:00Z", "z-afternoon-not-bug-signature");
t.Keeps("noon exactly is treated as afternoon (>= 12)",
    "1980-04-03T12:00:00Z", "z-afternoon-not-bug-signature");
t.RewritesRaw("just before noon still rewrites (11:59)",
    "1980-04-03T11:59:59Z", "1980-04-03", requireMorningUtcForZ: true);
t.RewritesRaw("guard off: afternoon Z rewrites too",
    "1980-04-03T18:00:00Z", "1980-04-03", requireMorningUtcForZ: false);

// === Whitespace trimming ===
t.Rewrites("leading/trailing whitespace is trimmed",
    " 1980-04-03T04:00:00Z ", "1980-04-03");

// === PayloadRewriter: FieldAllowlist (default) ===
var allowlist = new RewriteOptions { Strategy = RewriteStrategy.FieldAllowlist };

t.Payload("allowlisted birthDate rewritten, other fields untouched",
    allowlist,
    """{"birthDate":"1980-04-03T04:00:00Z","firstName":"Ann"}""",
    expectChanged: true,
    check: json =>
    {
        var root = JsonDocument.Parse(json).RootElement;
        t.Eq("birthDate", "1980-04-03", root.GetProperty("birthDate").GetString());
        t.Eq("firstName", "Ann", root.GetProperty("firstName").GetString());
    });

t.Payload("nested dob rewritten",
    allowlist,
    """{"person":{"dob":"1990-06-15T04:00:00Z"}}""",
    expectChanged: true,
    check: json =>
    {
        var root = JsonDocument.Parse(json).RootElement;
        t.Eq("nested dob", "1990-06-15",
            root.GetProperty("person").GetProperty("dob").GetString());
    });

t.Payload("array of dates under allowlisted field is covered",
    allowlist,
    """{"birthDate":["1980-04-03T04:00:00Z","1975-12-31T05:00:00Z"]}""",
    expectChanged: true,
    check: json =>
    {
        var arr = JsonDocument.Parse(json).RootElement.GetProperty("birthDate");
        t.Eq("arr[0]", "1980-04-03", arr[0].GetString());
        t.Eq("arr[1]", "1975-12-31", arr[1].GetString());
    });

t.Payload("non-allowlisted date field left alone under FieldAllowlist",
    allowlist,
    """{"enrollDate":"2025-09-02T04:00:00Z"}""",
    expectChanged: false,
    check: json =>
        t.Eq("enrollDate untouched", "2025-09-02T04:00:00Z",
            JsonDocument.Parse(json).RootElement.GetProperty("enrollDate").GetString()));

t.Payload("allowlisted field already bare is a no-op",
    allowlist,
    """{"birthDate":"1980-04-03"}""",
    expectChanged: false, check: _ => { });

t.Payload("non-date value in allowlisted field untouched",
    allowlist,
    """{"dob":"hello"}""",
    expectChanged: false, check: _ => { });

t.Payload("numbers, bools, nulls preserved; only birthDate changes",
    allowlist,
    """{"birthDate":"1980-04-03T04:00:00Z","age":44,"active":true,"mid":null}""",
    expectChanged: true,
    check: json =>
    {
        var root = JsonDocument.Parse(json).RootElement;
        t.Eq("birthDate", "1980-04-03", root.GetProperty("birthDate").GetString());
        t.Eq("age", 44, root.GetProperty("age").GetInt32());
        t.Eq("active", true, root.GetProperty("active").GetBoolean());
        t.Assert("mid is null", root.GetProperty("mid").ValueKind == JsonValueKind.Null);
    });

t.Payload("multiple allowlisted fields both rewritten",
    allowlist,
    """{"birthDate":"1980-04-03T04:00:00Z","dateOfBirth":"1979-12-31T05:00:00Z"}""",
    expectChanged: true,
    check: json =>
    {
        var root = JsonDocument.Parse(json).RootElement;
        t.Eq("birthDate", "1980-04-03", root.GetProperty("birthDate").GetString());
        t.Eq("dateOfBirth", "1979-12-31", root.GetProperty("dateOfBirth").GetString());
    });

// === PayloadRewriter: ShapeAll ===
// Catches every date-only field in the flow, not just DOB. The bug shifts them
// all identically, so this is the "belt and suspenders" strategy.
var shape = new RewriteOptions { Strategy = RewriteStrategy.ShapeAll };
t.Payload("ShapeAll rewrites any instant regardless of field name",
    shape,
    """{"enrollDate":"2025-09-02T04:00:00Z","note":"hi","birthDate":"1980-04-03T04:00:00Z"}""",
    expectChanged: true,
    check: json =>
    {
        var root = JsonDocument.Parse(json).RootElement;
        t.Eq("enrollDate", "2025-09-02", root.GetProperty("enrollDate").GetString());
        t.Eq("note untouched", "hi", root.GetProperty("note").GetString());
        t.Eq("birthDate", "1980-04-03", root.GetProperty("birthDate").GetString());
    });

// === Records are captured for the audit trail / pre-shift source of truth ===
t.PayloadRecords("rewrite record captures original and rewritten",
    allowlist,
    """{"birthDate":"1980-04-03T04:00:00Z"}""",
    recs =>
    {
        t.Eq("record count", 1, recs.Count);
        t.Eq("record.FieldPath", "$.birthDate", recs[0].FieldPath);
        t.Eq("record.Original", "1980-04-03T04:00:00Z", recs[0].Original);
        t.Eq("record.Rewritten", "1980-04-03", recs[0].Rewritten);
    });

// === Error path: invalid JSON throws so the middleware can fail-open ===
t.Throws("invalid JSON throws (caller decides fail-open vs closed)",
    () => new PayloadRewriter(allowlist).Rewrite("{ not valid json "));

// === ResponseIdExtractor: joining a gate log entry to the record it produced ===
var idFields = new HashSet<string>(new[] { "id", "personId", "recordId", "Id" }, StringComparer.OrdinalIgnoreCase);

t.Extracts("flat object: top-level id matches",
    idFields, """{"id":"12345","firstName":"Ann"}""", "12345");
t.Extracts("case-insensitive field name match",
    idFields, """{"ID":"12345"}""", "12345");
t.Extracts("numeric id is stringified",
    idFields, """{"id":98765}""", "98765");
t.Extracts("nested object: id found one level down",
    idFields, """{"person":{"personId":"P-1"}}""", "P-1");
t.Extracts("array of objects: id found inside first matching element",
    idFields, """{"results":[{"recordId":"R-1"}]}""", "R-1");
t.Extracts("prefers a shallower match over a deeper one",
    idFields, """{"id":"OUTER","nested":{"id":"INNER"}}""", "OUTER");

t.ExtractsNothing("no configured field name present", idFields, """{"firstName":"Ann"}""");
t.ExtractsNothing("empty object", idFields, "{}");
t.ExtractsNothing("empty body", idFields, "");
t.ExtractsNothing("malformed JSON does not throw", idFields, "{ not valid json");
t.ExtractsNothing("matching field with empty string value is not a usable id", idFields, """{"id":""}""");
t.ExtractsNothing("matching field with null value is not a usable id", idFields, """{"id":null}""");
t.ExtractsNothing("no field names configured", new HashSet<string>(), """{"id":"12345"}""");
t.ExtractsNothing("depth beyond MaxDepth is not searched",
    idFields, """{"a":{"b":{"c":{"d":{"e":{"id":"too-deep"}}}}}}""");

// === ManagementAuth: gates /api/v1/status and /api/v1/rewrites/recent ===
// Both endpoints carry operationally sensitive detail in production —
// including the actual unredacted applicant birth dates this gate
// intercepted — so this is deliberately fail-closed: no configured key
// means nothing can ever authorize, not "leave it open."
t.Check("outside production, always authorized regardless of key",
    ManagementAuth.IsAuthorized("real-key", null, isProduction: false));
t.Check("outside production, authorized even with no key configured at all",
    ManagementAuth.IsAuthorized("", null, isProduction: false));
t.Check("production + matching key is authorized",
    ManagementAuth.IsAuthorized("real-key", "real-key", isProduction: true));
t.Check("production + wrong key is NOT authorized",
    !ManagementAuth.IsAuthorized("real-key", "wrong-key", isProduction: true));
t.Check("production + no supplied key is NOT authorized",
    !ManagementAuth.IsAuthorized("real-key", null, isProduction: true));
t.Check("production + empty supplied key is NOT authorized",
    !ManagementAuth.IsAuthorized("real-key", "", isProduction: true));
t.Check("production + no configured key is NOT authorized even with a supplied key (fail-closed, not fail-open)",
    !ManagementAuth.IsAuthorized("", "anything", isProduction: true));
t.Check("production + no configured key and no supplied key is NOT authorized",
    !ManagementAuth.IsAuthorized("", null, isProduction: true));
t.Check("key comparison is case-sensitive",
    !ManagementAuth.IsAuthorized("Real-Key", "real-key", isProduction: true));

// === In-process HTTP path: middleware pipeline + forwarder (no network) ===
await IntegrationChecks.Run(t);

return t.Report();


// ---------------------------------------------------------------------------
sealed class Harness
{
    private int _pass, _fail;

    public void Rewrites(string name, string input, string expected)
        => RewritesRaw(name, input, expected, requireMorningUtcForZ: true);

    public void RewritesRaw(string name, string? input, string expected, bool requireMorningUtcForZ)
    {
        var r = DateInstantTransformer.Transform(input, requireMorningUtcForZ);
        if (r.Changed && r.Value == expected)
            Ok(name);
        else
            Bad(name, $"expected rewrite to '{expected}', got outcome={r.Outcome} value='{r.Value}' reason={r.Reason}");
    }

    public void Keeps(string name, string? input, string expectedReason)
    {
        var r = DateInstantTransformer.Transform(input, requireMorningUtcForZ: true);
        if (!r.Changed && r.Reason == expectedReason)
            Ok(name);
        else
            Bad(name, $"expected no-op reason '{expectedReason}', got outcome={r.Outcome} value='{r.Value}' reason={r.Reason}");
    }

    public void Payload(string name, RewriteOptions opts, string json, bool expectChanged, Action<string> check)
    {
        try
        {
            var outcome = new PayloadRewriter(opts).Rewrite(json);
            if (outcome.Changed != expectChanged)
            {
                Bad(name, $"expected Changed={expectChanged}, got {outcome.Changed}");
                return;
            }
            check(outcome.Json);
            Ok(name);
        }
        catch (Exception ex)
        {
            Bad(name, "threw: " + ex.Message);
        }
    }

    public void PayloadRecords(string name, RewriteOptions opts, string json, Action<IReadOnlyList<RewriteRecord>> check)
    {
        try { check(new PayloadRewriter(opts).Rewrite(json).Records); Ok(name); }
        catch (Exception ex) { Bad(name, "threw: " + ex.Message); }
    }

    public void Throws(string name, Action action)
    {
        try { action(); Bad(name, "expected an exception, none thrown"); }
        catch { Ok(name); }
    }

    public void Extracts(string name, IReadOnlySet<string> fieldNames, string json, string expected)
    {
        var got = ResponseIdExtractor.TryExtract(Encoding.UTF8.GetBytes(json), fieldNames);
        if (got == expected)
            Ok(name);
        else
            Bad(name, $"expected '{expected}', got '{got ?? "null"}'");
    }

    public void ExtractsNothing(string name, IReadOnlySet<string> fieldNames, string json)
    {
        var got = ResponseIdExtractor.TryExtract(Encoding.UTF8.GetBytes(json), fieldNames);
        if (got == null)
            Ok(name);
        else
            Bad(name, $"expected null, got '{got}'");
    }

    public void Eq<T>(string label, T expected, T actual)
    {
        if (!Equals(expected, actual))
            throw new Exception($"{label}: expected '{expected}', got '{actual}'");
    }

    public void Assert(string label, bool condition)
    {
        if (!condition) throw new Exception(label + ": condition false");
    }

    public void Check(string name, bool ok, string why = "")
    {
        if (ok) Ok(name); else Bad(name, why);
    }

    private void Ok(string name) { _pass++; Console.WriteLine("  ok   " + name); }
    private void Bad(string name, string why) { _fail++; Console.WriteLine("  FAIL " + name + " -- " + why); }

    public int Report()
    {
        Console.WriteLine();
        Console.WriteLine($"--- DoaneEdgeGate.Core: {_pass} passed, {_fail} failed ---");
        return _fail == 0 ? 0 : 1;
    }
}

# DOB Repair - Tandem Flow: DoaneEdgeGate + DoaneDOBReconcile

How the two tools fit together to fix PD0002124 (the Instant Enrollment -1 day DOB
shift): one stops new corruption at the edge, the other cleans up what already
happened. This doc is the operational glue between them - who does what, in what
order, and where the honest limits are.

---

## 1. Two fronts, one bug

The bug: an IE registrant east of Central picks a date; the browser serializes local
midnight as a UTC instant; the Web API truncates it to server-local and lands one
day early. It has been doing this silently for about four years, so there are two
distinct problems:

- New records still being created shifted, every day IE runs. -> DoaneEdgeGate
  (prevention): sits in the IE request path and rewrites the payload to a bare date
  before the Web API can truncate it. Forward-looking.
- A backlog of already-shifted records sitting in Colleague. -> DoaneDOBReconcile
  (cleanup): scans PERSON data, finds likely-shifted DOBs by evidence, and proposes
  human-gated corrections. Backward-looking. Never writes to Colleague itself.

Neither replaces the other. The gate does nothing about the four years already in
the database; the detector does nothing to stop tomorrow's registrations from
shifting. You need both, plus the real Ellucian client fix as the eventual
destination that retires the gate.

---

## 2. The shared guardrail

Both tools hold the same line: no unattended write to a person's DOB.

- The gate rewrites a payload IN FLIGHT, before the record exists. It is not mutating
  a stored value; it is stopping a bad value from ever being stored. There is no
  record to get wrong.
- The detector PROPOSES; humans DISPOSE. It exports accepted corrections; the actual
  write to Colleague happens outside the tool via an audited, human-approved path.

This matters because the original bug WAS a silent, unattended DOB mutation. The
whole design refuses to fight that with another silent mutation.

---

## 3. Data flow

Prevention path (real time):

    IE browser POST (DOB as UTC instant)
      -> DoaneEdgeGate: match -> rewrite DOB to bare date -> LOG the rewrite
      -> Colleague Web API (stores the correct date)
      -> Colleague

Cleanup path (nightly + human review):

    PERSON export CSV (ODS / Informer / Ethos-to-CSV)
      -> detector CLI: pairs records, scores identity, buckets HIGH/MEDIUM/REVIEW
      -> candidates.csv
      -> review UI: human accepts / rejects / defers (decisions.db)
      -> GET /api/v1/export/corrections
      -> human-gated apply (audited Ethos PUT to persons, or manual NAE)
      -> Colleague

The link between them is the gate's rewrite log: request_id, original instant,
rewritten date, timestamp, endpoint. That log is the pre-shift source of truth - it
records exactly what the browser sent, which is the one thing the backlog does not
preserve.

---

## 4. Lifecycle - what each tool is doing at each stage

Being precise here, because the value of the gate log to the detector changes by
stage.

Stage 0 - before the gate exists (today):
- Detector works alone. It has no record of what registrants actually typed, so it
  INFERS the true date from evidence: a duplicate/twin record with the same identity
  but a one-day-later DOB, where the IE record is the earlier (corrupted) one. This
  is real signal but it is inference, and it only fires when a usable twin exists.

Stage 1 - gate in Shadow:
- The gate is wired but not mutating. Records are still created shifted (Shadow does
  not rewrite), BUT the gate now LOGS the correct date for each IE submission. For
  any record corrupted during this window, you have log-backed truth, not inference.
  This is the highest-value window for feeding the detector: pair the shifted stored
  record with the gate's logged intended date and the correction is high-confidence.

Stage 2 - gate Active:
- The gate rewrites at write time. New IE records are stored correctly, so there is
  nothing to clean going forward. The detector's job narrows to two things: draining
  the pre-gate backlog, and MONITORING - the count of new IE-origin HIGH candidates
  should fall to zero and stay there. If it does not, the gate config drifted (see
  the version-fragility note) and the monitor just caught it.

So the gate log is per-record truth mainly for Stage 1 (and for any Stage 2 records
that slip through: a fail-open passthrough, or a date-only field not yet covered
before you widen to ShapeAll). The four-year backlog has no gate log and remains the
detector's inference job - but understanding the exact mechanism (backward-only
shift, year-boundary behavior) is what let the detector's shift model be correct in
the first place.

---

## 5. The honest gap: joining a gate log entry to a Colleague record

The gate log entry is keyed to the HTTP request (request_id + the submitted DOB). At
the moment of the person-create POST, the resulting Colleague record ID usually does
not exist yet - it is being created. So "compare the stored record's DOB to what
they typed" needs a join key that the request side alone does not have.

Two ways to close this, in order of preference:

1. Capture the created record ID from the RESPONSE. The gate is a proxy; it sees the
   Web API's response, which typically returns the new record's identifier. Logging
   request_id + submitted DOB + the created ID from the response gives a clean,
   direct join to the Colleague record. This is a small, worthwhile enhancement to
   the gate if you want Stage 1 log entries to be directly correctable. Mind the PII:
   log the minimum needed and route it through the same on-prem handling as other
   sensitive fields (pii-guard) rather than dumping full payloads.

2. Fuzzy-join on identity. Without the record ID, match a log entry to a record by
   name + email + submission time. Workable, but it is inference again - weaker than
   option 1 and the very thing the log was supposed to let you stop doing.

Recommendation: if you intend to lean on the gate log for Stage 1 cleanup, add the
response-side record ID to the log first. If you are mainly running the gate for
prevention and letting the detector drain the backlog by twin-inference, the log is
still valuable as corroboration and as the monitor signal, and you can defer the
enhancement.

I would rather you know this join is not free than discover it when you try to wire
the two together.

---

## 6. Operating cadence

- Real time: gate runs Active, rewriting and logging every IE registration.
- Nightly (Conductor, DLM-style): fresh PERSON export -> detector CLI -> regenerate
  candidates -> flag candidates not already in decisions.db as NEW -> notify the
  review team if new HIGH appeared.
- Weekly (or as queue warrants): review team works the HIGH queue in the UI,
  accept/reject/defer. Accepted corrections export; a human applies them via the
  audited path.
- Ongoing: watch the new-IE-HIGH trend. Post-Active it should trend to zero. A
  non-zero trend is a signal, not noise - investigate gate config drift.

---

## 7. Success, defined

- Gate: new IE-origin HIGH candidates from the detector trend to zero after Active.
  That is the gate proving itself through the detector's eyes.
- Detector: the pre-gate backlog HIGH count drains through the review cadence toward
  zero, with every correction human-approved and audited.
- Both retire when Ellucian ships client-side date-only serialization. The gate
  becomes an automatic no-op (already-bare dates pass untouched) and can be removed;
  the detector stays useful only until the backlog is clean.

Prevention stops the bleeding. Cleanup heals the scar. The Ellucian fix is the cure;
until it lands, these two are the treatment.

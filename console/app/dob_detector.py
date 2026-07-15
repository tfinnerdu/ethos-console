"""DOB shift detection engine (PD0002124).

Finds PERSON records whose Date of Birth was silently shifted -1 day by the
Colleague Self-Service Instant Enrollment timezone defect, without touching
records that are already correct.

Core idea
---------
The bug only ever subtracts a day, and only for registrants east of the
server (Doane = Central). So the corrupted value is always EARLIER than the
true value by exactly one day. Two independent signals can surface this:

1. Cross-person pairing (`_classify_pair`) - two records that plausibly
   describe the same human whose DOBs are exactly one calendar day apart,
   disambiguated by origin (Instant Enrollment vs authoritative).
2. Same-person corroboration (`_classify_self_corroboration`) - a SINGLE
   PERSON record whose current DOB differs by exactly one day from a DOB
   independently resubmitted later on the same person_id via a different
   channel (e.g. a transcript order, a financial aid application - anything
   where the person restates their own DOB on a later, separate occasion).
   No identity-matching is needed since it's definitionally the same person.

CONFIRMED FINDING (direct data audit, not a design assumption): cross-person
pairing has very low real-world yield for this specific bug. No duplicate
PERSON records with differing birth dates are being created by IE - the
original "shifted DOB fails a duplicate-check, IE creates a new twin PERSON"
hypothesis does not describe what's actually happening in this data. For a
brand-new registrant (no prior PERSON record), the shifted DOB is stored as
the ONLY record of that value - there is no twin to pair against BY
CONSTRUCTION, not just by bad luck. Given Instant Enrollment predominantly
serves non-typical/new registrants rather than already-enrolled students,
this unpaired population is likely most of the actual damage, not an edge
case. Practical effect: `_classify_pair`'s HIGH/MEDIUM/REVIEW output should
be treated as a real but low-yield signal (still worth running - it costs
nothing and will catch genuine duplicates from other causes too), while
same-person corroboration is the primary mechanism with any real reach into
the historical backlog. The ELEVATED_RISK worklist (unpaired IE record, no
corroboration available, Eastern-state address) is correspondingly a
outreach/verification list for follow-up contact, NOT a correction list -
nothing on it should ever be auto-applied or bulk-corrected.

Confidence tiers
----------------
HIGH     - EITHER: strong cross-person identity match + exactly one-day gap +
           the EARLIER-dated record is Instant-Enroll-created and the
           LATER-dated record is authoritative (non-IE); OR a same-person
           corroboration match (no identity-matching ambiguity, since it's
           the same person_id by construction). We propose: set the DOB to
           the later/corroborating date (corrupted + 1 day).
MEDIUM   - strong cross-person identity match + one-day gap, but origin is
           unknown or both records share the same origin. Later date is a
           tentative "probably true" hint. No auto-correction.
REVIEW   - identity match (cross-person OR same-person) but the IE-side date
           is the LATER one (gap points the wrong way for this bug). Likely a
           plain data-entry typo or two different people. Flag; do not
           propose +1.

Nothing here writes to Colleague. This module only classifies candidates; the
routes layer (app/routes/dob_repair.py) is responsible for persisting human
decisions and exporting an approved-corrections CSV.

Direction assumption: this engine encodes the "-1 day / backward" signature
confirmed against real Instant Enrollment traffic. If that signature is ever
shown to be different, flip SHIFT_DIRECTION below.

Origin-code portability: IE_ORIGIN_VALUES below holds generic, portable text
labels. A real Colleague extract's origin/operator-code column will usually
carry institution-specific values instead (e.g. a numeric web-registration
operator ID, or "GUEST"/"WEBCASHIER"-style process names) that will never
match this default set. Pass `extra_ie_origin_values` to `analyze()` (wired
to DOB_RECONCILE_IE_ORIGIN_CODES in app/routes/dob_repair.py) rather than
hardcoding institution-specific operator codes into this shared module.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Optional, Union, IO


# -1 means the bug subtracts a day (corrupted value is earlier than true value).
SHIFT_DIRECTION = -1

# Origin values that mean "created by Instant Enrollment". Compared uppercased.
IE_ORIGIN_VALUES = {"INSTANT_ENROLL", "INSTANT ENROLLMENT", "IE", "SS_IE"}

# US states predominantly in the Eastern time zone (east of a Central server).
# The -1 shift only hits registrants east of the server, so an unpaired IE
# record with an Eastern-state address is the elevated-risk population. This
# is a PRIORITIZATION proxy only: the real trigger is the browser timezone at
# registration, which the mailing address does not prove. Straddle states
# (FL, IN, KY, MI, TN) are included because their population center is Eastern.
EASTERN_TZ_STATES = {
    "CT", "DE", "DC", "FL", "GA", "IN", "KY", "ME", "MD", "MA", "MI",
    "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "SC", "TN", "VT", "VA", "WV",
}


def is_eastern_state(state: str) -> bool:
    return _clean(state) in EASTERN_TZ_STATES


# Identity scoring weights. A pair is treated as the same person at or above
# IDENTITY_THRESHOLD. Tunable via config without touching logic.
WEIGHTS = {
    "last_exact": 2,
    "first_exact": 2,
    "first_initial": 1,   # only when full first names do not match exactly
    "middle_exact": 1,
    "zip_exact": 2,
    "street_exact": 2,
    "city_state_exact": 1,
    "email_exact": 3,
    "phone_exact": 3,
}
IDENTITY_THRESHOLD = 6
MAX_IDENTITY_SCORE = sum(WEIGHTS[k] for k in WEIGHTS if k != "first_initial")

# Sentinel identity_score for same-person corroboration matches (see
# _classify_self_corroboration). There is no identity-matching ambiguity to
# score -- it's the same person_id by construction -- so this is set above
# any possible cross-person pairing score, to sort first within a bucket.
SELF_CORROBORATION_SCORE = MAX_IDENTITY_SCORE + 1

# Date formats accepted on input. First match wins.
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%m/%d/%y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
]

# Default column mapping. Override any of these via config so the detector
# matches whatever export you have (ODS, Informer, Ethos-to-CSV, Colleague
# export).
#
# corroborating_dob / corroborating_source are OPTIONAL -- omit them (or leave
# the column blank/absent) for exports that don't have a same-person
# corroboration source; _classify_self_corroboration() is a no-op when
# corroborating_dob is unset. See the module docstring for why this signal
# matters more than cross-person pairing for this specific bug.
DEFAULT_COLUMNS = {
    "person_id": "person_id",
    "last_name": "last_name",
    "first_name": "first_name",
    "middle_name": "middle_name",
    "birth_date": "birth_date",
    "addr_line1": "addr_line1",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "email": "email",
    "phone": "phone",
    "origin": "origin",
    "created_date": "created_date",
    "corroborating_dob": "corroborating_dob",
    "corroborating_source": "corroborating_source",
}


# --------------------------------------------------------------------------- #
# Normalization helpers
# --------------------------------------------------------------------------- #

def _clean(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).upper()


def _digits(value: Optional[str]) -> str:
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def _zip5(value: Optional[str]) -> str:
    d = _digits(value)
    return d[:5]


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse a DOB string into a date, or None if unparseable/blank."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# Record model
# --------------------------------------------------------------------------- #

@dataclass
class Record:
    person_id: str
    last_name: str
    first_name: str
    middle_name: str
    birth_date: Optional[date]
    addr_line1: str
    city: str
    state: str
    zip: str
    email: str
    phone: str
    origin: str
    created_date: str
    raw_birth_date: str = ""
    # Optional: a DOB independently resubmitted later by the same person_id
    # via a different channel (transcript order, financial aid application,
    # etc.) -- see the module docstring. Blank/absent in exports that don't
    # have one; _classify_self_corroboration() no-ops when this is None.
    corroborating_dob: Optional[date] = None
    corroborating_source: str = ""

    @property
    def is_ie(self) -> bool:
        return _clean(self.origin) in IE_ORIGIN_VALUES

    def block_key(self) -> str:
        """Blocking key keeps comparison O(n) instead of O(n^2). Records only
        get compared inside the same block. Key = normalized last name +
        first initial + zip5 (falls back to city when zip is missing)."""
        last = _clean(self.last_name)
        first_init = _clean(self.first_name)[:1]
        geo = _zip5(self.zip) or _clean(self.city)
        return f"{last}|{first_init}|{geo}"


def record_from_row(row: dict, columns: dict) -> Record:
    def g(field_name: str) -> str:
        col = columns.get(field_name, field_name)
        return row.get(col, "") or ""

    raw_dob = g("birth_date")
    return Record(
        person_id=g("person_id").strip(),
        last_name=g("last_name"),
        first_name=g("first_name"),
        middle_name=g("middle_name"),
        birth_date=parse_date(raw_dob),
        addr_line1=g("addr_line1"),
        city=g("city"),
        state=g("state"),
        zip=g("zip"),
        email=g("email"),
        phone=g("phone"),
        origin=g("origin"),
        created_date=g("created_date"),
        raw_birth_date=raw_dob,
        corroborating_dob=parse_date(g("corroborating_dob")),
        corroborating_source=g("corroborating_source"),
    )


# --------------------------------------------------------------------------- #
# Identity scoring
# --------------------------------------------------------------------------- #

def identity_score(a: Record, b: Record) -> int:
    """Points for how strongly two records look like the same person."""
    score = 0
    la, lb = _clean(a.last_name), _clean(b.last_name)
    fa, fb = _clean(a.first_name), _clean(b.first_name)

    if la and la == lb:
        score += WEIGHTS["last_exact"]
    if fa and fa == fb:
        score += WEIGHTS["first_exact"]
    elif fa and fb and fa[:1] == fb[:1]:
        score += WEIGHTS["first_initial"]

    ma, mb = _clean(a.middle_name), _clean(b.middle_name)
    if ma and ma == mb:
        score += WEIGHTS["middle_exact"]

    za, zb = _zip5(a.zip), _zip5(b.zip)
    if za and za == zb:
        score += WEIGHTS["zip_exact"]

    sa, sb = _clean(a.addr_line1), _clean(b.addr_line1)
    if sa and sa == sb:
        score += WEIGHTS["street_exact"]

    ca, cb = _clean(a.city), _clean(b.city)
    sta, stb = _clean(a.state), _clean(b.state)
    if ca and ca == cb and sta and sta == stb:
        score += WEIGHTS["city_state_exact"]

    ea, eb = _clean(a.email), _clean(b.email)
    if ea and ea == eb:
        score += WEIGHTS["email_exact"]

    pa, pb = _digits(a.phone), _digits(b.phone)
    if pa and pa == pb and len(pa) >= 10:
        score += WEIGHTS["phone_exact"]

    return score


# --------------------------------------------------------------------------- #
# Candidate model + classification
# --------------------------------------------------------------------------- #

@dataclass
class Candidate:
    candidate_id: str
    bucket: str                       # HIGH | MEDIUM | REVIEW
    identity_score: int
    gap_days: int                     # signed: (later - earlier), always 1 here
    record_a: Record                  # earlier DOB
    record_b: Record                  # later DOB
    suggested_true_dob: Optional[date]
    proposed_person_id: Optional[str]  # only set for HIGH (safe auto-proposal)
    proposed_from: Optional[date]
    proposed_to: Optional[date]
    rationale: str = ""

    def as_row(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "bucket": self.bucket,
            "identity_score": self.identity_score,
            "gap_days": self.gap_days,
            "earlier_person_id": self.record_a.person_id,
            "earlier_dob": _fmt(self.record_a.birth_date),
            "earlier_origin": self.record_a.origin,
            "later_person_id": self.record_b.person_id,
            "later_dob": _fmt(self.record_b.birth_date),
            "later_origin": self.record_b.origin,
            "name": f"{self.record_b.first_name} {self.record_b.last_name}".strip(),
            "suggested_true_dob": _fmt(self.suggested_true_dob),
            "proposed_person_id": self.proposed_person_id or "",
            "proposed_from": _fmt(self.proposed_from),
            "proposed_to": _fmt(self.proposed_to),
            "rationale": self.rationale,
        }


def _fmt(d: Optional[date]) -> str:
    return d.isoformat() if d else ""


def _is_ie(r: Record, extra_ie_origin_values: Optional[frozenset] = None) -> bool:
    """Like Record.is_ie, but also matches any institution-specific operator
    codes passed in (see the module docstring's "Origin-code portability"
    note). Does not mutate the shared IE_ORIGIN_VALUES module constant, so
    concurrent analyze() calls with different extra values never interfere."""
    if extra_ie_origin_values:
        return r.is_ie or _clean(r.origin) in extra_ie_origin_values
    return r.is_ie


def _classify_pair(
    a: Record, b: Record, score: int, extra_ie_origin_values: Optional[frozenset] = None,
) -> Optional[Candidate]:
    """a and b are same-block; identity strength is `score`. Returns a
    Candidate if the DOB gap is exactly one day, else None."""
    if a.birth_date is None or b.birth_date is None:
        return None

    delta = (b.birth_date - a.birth_date).days
    if abs(delta) != 1:
        return None

    # Order so record_a is the earlier DOB, record_b the later DOB.
    earlier, later = (a, b) if a.birth_date < b.birth_date else (b, a)
    cid = _candidate_id(earlier.person_id, later.person_id)

    ie_earlier = _is_ie(earlier, extra_ie_origin_values)
    ie_later = _is_ie(later, extra_ie_origin_values)

    # HIGH: backward-shift signature. Earlier record is IE (corrupted), later
    # record is authoritative (not IE). True DOB = later date.
    if SHIFT_DIRECTION == -1 and ie_earlier and not ie_later:
        return Candidate(
            candidate_id=cid,
            bucket="HIGH",
            identity_score=score,
            gap_days=1,
            record_a=earlier,
            record_b=later,
            suggested_true_dob=later.birth_date,
            proposed_person_id=earlier.person_id,
            proposed_from=earlier.birth_date,
            proposed_to=later.birth_date,
            rationale=(
                "Instant-Enroll record is exactly one day BEFORE an "
                "authoritative record for the same person. Matches the "
                "-1 day timezone signature. Proposed: set IE DOB to the "
                "authoritative (later) date."
            ),
        )

    # REVIEW: IE record is the LATER one. Wrong direction for this bug, so it
    # is more likely a typo or two different people. No +1 proposal.
    if ie_later and not ie_earlier:
        return Candidate(
            candidate_id=cid,
            bucket="REVIEW",
            identity_score=score,
            gap_days=1,
            record_a=earlier,
            record_b=later,
            suggested_true_dob=None,
            proposed_person_id=None,
            proposed_from=None,
            proposed_to=None,
            rationale=(
                "One-day gap but the Instant-Enroll record is the LATER "
                "date, which does not fit the -1 day shift. Likely a "
                "data-entry typo or two distinct people. Human decision "
                "required."
            ),
        )

    # MEDIUM: origin unknown or both same origin. Surface both; tentatively
    # the later date is more likely true (bug only subtracts) but do not
    # auto-apply.
    return Candidate(
        candidate_id=cid,
        bucket="MEDIUM",
        identity_score=score,
        gap_days=1,
        record_a=earlier,
        record_b=later,
        suggested_true_dob=later.birth_date,
        proposed_person_id=None,
        proposed_from=None,
        proposed_to=None,
        rationale=(
            "Same person, DOBs exactly one day apart, but origin does not "
            "cleanly separate corrupted from authoritative. Later date is "
            "a tentative guess for the true DOB. Confirm before any change."
        ),
    )


def _classify_self_corroboration(
    r: Record, extra_ie_origin_values: Optional[frozenset] = None,
) -> Optional[Candidate]:
    """Same-person corroboration: r.corroborating_dob is a DOB independently
    resubmitted later, on the SAME person_id, via a different channel (a
    transcript order, a financial aid application, etc.) -- not a second
    PERSON record. See the module docstring for why this is the primary
    detection mechanism with real reach into the historical backlog, unlike
    cross-person pairing (_classify_pair).

    Reuses the Candidate/record_a/record_b shape so the existing review UI,
    decision persistence, and CSV export need no changes -- record_a and
    record_b simply share the same person_id here, by construction.
    """
    if r.birth_date is None or r.corroborating_dob is None:
        return None

    delta = (r.birth_date - r.corroborating_dob).days
    if delta == 0:
        return None  # no discrepancy
    if abs(delta) != 1:
        # Not this bug's signature (exactly one day). A multi-day/multi-year
        # gap is a different, unrelated data-quality issue -- out of scope
        # for this detector; surfacing it here would bury the real PD0002124
        # signal in noise. Flag separately outside this tool if needed.
        return None

    corroborated = replace(
        r, birth_date=r.corroborating_dob,
        origin=r.corroborating_source or "CORROBORATING_SOURCE",
    )
    cid = f"{r.person_id}__corroborated"
    source_label = r.corroborating_source or "an independently submitted DOB"

    if delta == SHIFT_DIRECTION:
        # r.birth_date is exactly one day BEFORE the corroborating date --
        # matches the -1 day timezone signature.
        return Candidate(
            candidate_id=cid,
            bucket="HIGH",
            identity_score=SELF_CORROBORATION_SCORE,
            gap_days=1,
            record_a=r,
            record_b=corroborated,
            suggested_true_dob=r.corroborating_dob,
            proposed_person_id=r.person_id,
            proposed_from=r.birth_date,
            proposed_to=r.corroborating_dob,
            rationale=(
                f"PERSON DOB is exactly one day earlier than {source_label} "
                f"for the SAME person_id -- no identity-matching uncertainty, "
                f"since it's definitionally the same person. Matches the -1 "
                f"day timezone signature. Proposed: correct the PERSON DOB "
                f"to the corroborating date."
            ),
        )

    # Wrong direction for this bug: current DOB is LATER than the
    # corroborating date. Likely a typo on one side or an unrelated edit.
    return Candidate(
        candidate_id=cid,
        bucket="REVIEW",
        identity_score=SELF_CORROBORATION_SCORE,
        gap_days=1,
        record_a=corroborated,
        record_b=r,
        suggested_true_dob=None,
        proposed_person_id=None,
        proposed_from=None,
        proposed_to=None,
        rationale=(
            f"One-day gap against {source_label} for the SAME person_id, "
            f"but the current PERSON DOB is the LATER date, which does not "
            f"fit the -1 day shift. Human decision required."
        ),
    )


def _candidate_id(id1: str, id2: str) -> str:
    """Stable id for a pair regardless of argument order."""
    a, b = sorted([id1, id2])
    return f"{a}__{b}"


# --------------------------------------------------------------------------- #
# Top-level analysis
# --------------------------------------------------------------------------- #

@dataclass
class AnalysisResult:
    candidates: list = field(default_factory=list)      # list[Candidate]
    elevated_risk: list = field(default_factory=list)   # list[Record] unpaired IE
    unparseable_dob: list = field(default_factory=list)  # list[Record]
    summary: dict = field(default_factory=dict)


def analyze(
    records: list,
    identity_threshold: int = IDENTITY_THRESHOLD,
    extra_ie_origin_values: Optional[set] = None,
) -> AnalysisResult:
    result = AnalysisResult()
    extra_origin = frozenset(_clean(v) for v in extra_ie_origin_values) if extra_ie_origin_values else None

    # Group into blocks so we only compare plausibly related records.
    blocks: dict = {}
    for r in records:
        if r.raw_birth_date and r.birth_date is None:
            result.unparseable_dob.append(r)
        blocks.setdefault(r.block_key(), []).append(r)

    paired_person_ids: set = set()

    # Same-person corroboration FIRST (see module docstring: this is the
    # primary signal with real reach into the backlog). Runs before the
    # cross-person pairing loop's paired_person_ids only matters for
    # elevated_risk exclusion below, so order between the two loops doesn't
    # otherwise matter -- but doing this one first means a record that's
    # both self-corroborated AND cross-paired is excluded from elevated_risk
    # regardless of which mechanism fires.
    for r in records:
        cand = _classify_self_corroboration(r, extra_origin)
        if cand is not None:
            result.candidates.append(cand)
            paired_person_ids.add(r.person_id)

    for _key, group in blocks.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a.person_id == b.person_id:
                    continue
                score = identity_score(a, b)
                if score < identity_threshold:
                    continue
                cand = _classify_pair(a, b, score, extra_origin)
                if cand is not None:
                    result.candidates.append(cand)
                    paired_person_ids.add(a.person_id)
                    paired_person_ids.add(b.person_id)

    # Elevated-risk lone records: Instant-Enroll-created, has a DOB, never
    # paired or corroborated, AND the address is in an Eastern-time state.
    # CONFIRMED (see module docstring): cross-person pairing has very low
    # real-world yield for this bug, and new registrants have no twin BY
    # CONSTRUCTION -- so for most of the true backlog, this is the only
    # bucket that will ever surface them, and it genuinely cannot be
    # confirmed from data alone. Treat this as an outreach/verification
    # contact list, not a correction list. Central/Western/unknown-state
    # unpaired IE records are low prior and deliberately omitted to keep the
    # worklist signal-heavy rather than the whole IE cohort.
    for r in records:
        if (
            _is_ie(r, extra_origin)
            and r.birth_date is not None
            and r.person_id not in paired_person_ids
            and is_eastern_state(r.state)
        ):
            result.elevated_risk.append(r)

    # De-duplicate candidates (a pair can surface once per block key at most,
    # but guard anyway) and sort worst-first for review.
    seen: set = set()
    unique = []
    for c in result.candidates:
        if c.candidate_id in seen:
            continue
        seen.add(c.candidate_id)
        unique.append(c)
    order = {"HIGH": 0, "MEDIUM": 1, "REVIEW": 2}
    unique.sort(key=lambda c: (order.get(c.bucket, 9), -c.identity_score))
    result.candidates = unique

    result.summary = {
        "total_records": len(records),
        "candidates_total": len(unique),
        "high": sum(1 for c in unique if c.bucket == "HIGH"),
        "medium": sum(1 for c in unique if c.bucket == "MEDIUM"),
        "review": sum(1 for c in unique if c.bucket == "REVIEW"),
        "elevated_risk": len(result.elevated_risk),
        "unparseable_dob": len(result.unparseable_dob),
    }
    return result


# --------------------------------------------------------------------------- #
# CSV loading
# --------------------------------------------------------------------------- #

def load_records(source: Union[str, IO[str]], columns: Optional[dict] = None) -> list:
    """Load Records from a PERSON export CSV.

    `source` is either a path (str) or an already-open text-mode file-like
    object (e.g. an uploaded file decoded to text) — callers in the routes
    layer hand this either a server-side path or an in-memory upload.
    """
    cols = dict(DEFAULT_COLUMNS)
    if columns:
        cols.update(columns)

    if isinstance(source, str):
        with open(source, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            return [record_from_row(row, cols) for row in reader]

    reader = csv.DictReader(source)
    return [record_from_row(row, cols) for row in reader]

"""In-depth test pass for the DOB shift detection engine (PD0002124).

Every case below is a realistic scenario from the blast radius. The point is
not just "does it run" but "does it flag the right records and, more
importantly, refuse to touch the clean ones."

Ported from the standalone DoaneDOBReconcile tool's tests/test_detector.py.
"""
import os
import unittest
from datetime import date

from app import dob_detector as detector

SAMPLE = os.path.join(os.path.dirname(__file__), "fixtures", "dob_sample_persons.csv")


def _find(result, id1, id2):
    cid = detector._candidate_id(id1, id2)
    for c in result.candidates:
        if c.candidate_id == cid:
            return c
    return None


class TestDateParsing(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(detector.parse_date("4/3/1980"), date(1980, 4, 3))
        self.assertEqual(detector.parse_date("1980-04-03"), date(1980, 4, 3))
        self.assertEqual(detector.parse_date("04/03/1980"), date(1980, 4, 3))
        self.assertEqual(detector.parse_date("1980-04-03T04:00:00.000"), date(1980, 4, 3))

    def test_blank_and_garbage(self):
        self.assertIsNone(detector.parse_date(""))
        self.assertIsNone(detector.parse_date(None))
        self.assertIsNone(detector.parse_date("not a date"))


class TestDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = detector.load_records(SAMPLE)
        cls.result = detector.analyze(cls.records)

    def test_high_confidence_backward_shift(self):
        # John Smith: IE 4/2 vs authoritative 4/3, same person. Classic bug.
        c = _find(self.result, "1001", "1002")
        self.assertIsNotNone(c)
        self.assertEqual(c.bucket, "HIGH")
        self.assertEqual(c.proposed_person_id, "1001")
        self.assertEqual(c.proposed_from, date(1980, 4, 2))
        self.assertEqual(c.proposed_to, date(1980, 4, 3))

    def test_year_boundary_shift(self):
        # Robert King: IE 12/31/1975 vs authoritative 1/1/1976. The -1 shift
        # crosses a year boundary, so the year is wrong too. Must still resolve.
        c = _find(self.result, "3001", "3002")
        self.assertIsNotNone(c)
        self.assertEqual(c.bucket, "HIGH")
        self.assertEqual(c.proposed_from, date(1975, 12, 31))
        self.assertEqual(c.proposed_to, date(1976, 1, 1))

    def test_same_zone_clean_not_flagged(self):
        # Mary Jones: both records DOB 6/15/1990 (gap 0). A correct in-zone
        # registrant. Must NOT appear as a candidate.
        c = _find(self.result, "2001", "2002")
        self.assertIsNone(c)

    def test_forward_gap_is_review_not_proposal(self):
        # Tom Lee: IE record is LATER by a day. Wrong direction for the bug.
        # Flag for review, never propose +1.
        c = _find(self.result, "5001", "5002")
        self.assertIsNotNone(c)
        self.assertEqual(c.bucket, "REVIEW")
        self.assertIsNone(c.proposed_person_id)
        self.assertIsNone(c.suggested_true_dob)

    def test_unknown_origin_is_medium(self):
        # Carla Diaz: one-day gap, both origins blank. Ambiguous which is true.
        # MEDIUM, tentative later-date suggestion, no auto-proposal.
        c = _find(self.result, "6001", "6002")
        self.assertIsNotNone(c)
        self.assertEqual(c.bucket, "MEDIUM")
        self.assertIsNone(c.proposed_person_id)
        self.assertEqual(c.suggested_true_dob, date(1998, 8, 10))

    def test_different_people_not_paired(self):
        # Two James Nolans, one day apart, but DIFFERENT addresses/emails/phones.
        # Identity score stays below threshold. Precision guard: no candidate.
        c = _find(self.result, "7001", "7002")
        self.assertIsNone(c)

    def test_elevated_risk_flagged_for_reconciliation(self):
        # Park (OH), Ford (FL), Nolan-1 (MA): IE-created, DOB present, no twin,
        # Eastern-state address. Elevated risk, needs an authoritative DOB.
        ids = {r.person_id for r in self.result.elevated_risk}
        self.assertIn("4001", ids)  # OH
        self.assertIn("8001", ids)  # FL
        self.assertIn("7001", ids)  # MA, unmatched James Nolan

    def test_elevated_risk_excludes_central_zone(self):
        # Mary Jones (NE, Central) is a clean same-zone IE record with no
        # suspicious twin. It must NOT be flagged as elevated risk.
        ids = {r.person_id for r in self.result.elevated_risk}
        self.assertNotIn("2001", ids)

    def test_elevated_risk_excludes_paired_records(self):
        # A record that WAS paired must not also show up as elevated risk.
        ids = {r.person_id for r in self.result.elevated_risk}
        self.assertNotIn("1001", ids)
        self.assertNotIn("3001", ids)

    def test_summary_counts(self):
        s = self.result.summary
        self.assertEqual(s["high"], 2)            # Smith, King
        self.assertEqual(s["medium"], 1)          # Diaz
        self.assertEqual(s["review"], 1)          # Lee
        self.assertEqual(s["elevated_risk"], 3)   # Park, Ford, Nolan-1


class TestExtraIeOriginValues(unittest.TestCase):
    """Institution-specific operator codes (e.g. a numeric web-registration
    operator ID) that won't match the generic IE_ORIGIN_VALUES defaults."""

    def _rec(self, **kw):
        base = dict(
            person_id="x", last_name="", first_name="", middle_name="",
            birth_date=None, addr_line1="", city="", state="", zip="",
            email="", phone="", origin="", created_date="",
        )
        base.update(kw)
        return detector.Record(**base)

    def test_default_origin_values_do_not_match_operator_code(self):
        r = self._rec(origin="0420024")
        self.assertFalse(r.is_ie)

    def test_extra_origin_values_recognized_via_is_ie_helper(self):
        r = self._rec(origin="0420024")
        self.assertTrue(detector._is_ie(r, frozenset({"0420024"})))

    def test_extra_origin_values_do_not_mutate_shared_default_set(self):
        r = self._rec(origin="0420024")
        detector._is_ie(r, frozenset({"0420024"}))
        self.assertNotIn("0420024", detector.IE_ORIGIN_VALUES)

    def test_analyze_with_extra_ie_origin_values_flags_elevated_risk(self):
        r = self._rec(
            person_id="9001", last_name="Rivera", first_name="Ana",
            birth_date=date(1999, 3, 4), state="NY", origin="0420024",
        )
        result = detector.analyze([r], extra_ie_origin_values={"0420024"})
        self.assertIn("9001", {rec.person_id for rec in result.elevated_risk})

    def test_analyze_without_extra_ie_origin_values_misses_it(self):
        r = self._rec(
            person_id="9002", last_name="Rivera", first_name="Ana",
            birth_date=date(1999, 3, 4), state="NY", origin="0420024",
        )
        result = detector.analyze([r])
        self.assertNotIn("9002", {rec.person_id for rec in result.elevated_risk})


class TestSelfCorroboration(unittest.TestCase):
    """Same-person_id corroboration: an independently-resubmitted DOB from a
    later event (transcript order, financial aid application, etc.) for the
    SAME person, rather than a second person_id. See the module docstring —
    this is the primary mechanism with real reach into the backlog, since a
    direct audit found cross-person duplicate pairing has very low yield."""

    def _rec(self, **kw):
        base = dict(
            person_id="p1", last_name="Alvarez", first_name="Maria",
            middle_name="", birth_date=None, addr_line1="", city="",
            state="", zip="", email="", phone="", origin="INSTANT_ENROLL",
            created_date="",
        )
        base.update(kw)
        return detector.Record(**base)

    def test_backward_shift_matches_bug_signature_high(self):
        # PERSON DOB is one day BEFORE the corroborating date -- the bug.
        r = self._rec(
            birth_date=date(2001, 7, 12), corroborating_dob=date(2001, 7, 13),
            corroborating_source="transcript_order",
        )
        cand = detector._classify_self_corroboration(r)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.bucket, "HIGH")
        self.assertEqual(cand.proposed_person_id, "p1")
        self.assertEqual(cand.proposed_from, date(2001, 7, 12))
        self.assertEqual(cand.proposed_to, date(2001, 7, 13))
        self.assertIn("transcript_order", cand.rationale)

    def test_wrong_direction_is_review_not_proposal(self):
        # PERSON DOB is one day AFTER the corroborating date -- wrong
        # direction for this bug (typo or unrelated edit).
        r = self._rec(
            birth_date=date(2001, 7, 13), corroborating_dob=date(2001, 7, 12),
        )
        cand = detector._classify_self_corroboration(r)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.bucket, "REVIEW")
        self.assertIsNone(cand.proposed_person_id)

    def test_matching_dates_not_flagged(self):
        r = self._rec(birth_date=date(2001, 7, 12), corroborating_dob=date(2001, 7, 12))
        self.assertIsNone(detector._classify_self_corroboration(r))

    def test_multi_day_gap_out_of_scope_not_flagged(self):
        # A 9-year gap is a different, unrelated data-quality issue, not this
        # bug's -1-day signature -- must not be surfaced by this detector.
        r = self._rec(birth_date=date(1976, 2, 23), corroborating_dob=date(1967, 2, 23))
        self.assertIsNone(detector._classify_self_corroboration(r))

    def test_no_corroborating_dob_is_a_noop(self):
        r = self._rec(birth_date=date(2001, 7, 12), corroborating_dob=None)
        self.assertIsNone(detector._classify_self_corroboration(r))

    def test_no_birth_date_is_a_noop(self):
        r = self._rec(birth_date=None, corroborating_dob=date(2001, 7, 13))
        self.assertIsNone(detector._classify_self_corroboration(r))

    def test_identity_score_is_sentinel_above_max_pair_score(self):
        r = self._rec(birth_date=date(2001, 7, 12), corroborating_dob=date(2001, 7, 13))
        cand = detector._classify_self_corroboration(r)
        self.assertEqual(cand.identity_score, detector.SELF_CORROBORATION_SCORE)
        self.assertGreater(detector.SELF_CORROBORATION_SCORE, detector.MAX_IDENTITY_SCORE)

    def test_analyze_integrates_self_corroboration_and_excludes_from_elevated_risk(self):
        # A self-corroborated record must appear in candidates as HIGH, and
        # must NOT also double up in elevated_risk (it's already resolved).
        r = self._rec(
            person_id="p9", birth_date=date(2001, 7, 12),
            corroborating_dob=date(2001, 7, 13), state="NY",
        )
        result = detector.analyze([r])
        self.assertEqual(result.summary["high"], 1)
        self.assertEqual(len(result.elevated_risk), 0)

    def test_extra_ie_origin_values_threaded_into_self_corroboration(self):
        r = self._rec(
            person_id="p10", origin="0420024",
            birth_date=date(2001, 7, 12), corroborating_dob=date(2001, 7, 13),
        )
        # Not IE by the generic defaults -- corroboration logic itself
        # doesn't require is_ie (it's a DOB-delta check), but the rationale
        # and elevated_risk interplay should still respect the configured
        # origin codes elsewhere in analyze(). Confirm analyze() doesn't
        # error and still classifies the corroboration correctly regardless.
        result = detector.analyze([r], extra_ie_origin_values={"0420024"})
        self.assertEqual(result.summary["high"], 1)


class TestIdentityScoring(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(
            person_id="x", last_name="", first_name="", middle_name="",
            birth_date=None, addr_line1="", city="", state="", zip="",
            email="", phone="", origin="", created_date="",
        )
        base.update(kw)
        return detector.Record(**base)

    def test_same_person_scores_high(self):
        a = self._rec(last_name="Smith", first_name="John", zip="23220",
                      addr_line1="120 Elm St", email="j@x.com", phone="8045551212")
        b = self._rec(last_name="Smith", first_name="John", zip="23220",
                      addr_line1="120 Elm St", email="j@x.com", phone="8045551212")
        self.assertGreaterEqual(detector.identity_score(a, b),
                                detector.IDENTITY_THRESHOLD)

    def test_name_only_below_threshold(self):
        # Same common name, nothing else. Should not be treated as same person.
        a = self._rec(last_name="Smith", first_name="John")
        b = self._rec(last_name="Smith", first_name="John")
        self.assertLess(detector.identity_score(a, b),
                        detector.IDENTITY_THRESHOLD)


if __name__ == "__main__":
    unittest.main(verbosity=2)

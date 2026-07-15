-- Example query for DOB_RECONCILE_SQL_FILE (DOB Repair "Fetch via SQL" source).
--
-- This is a STARTING TEMPLATE against real Colleague base tables (PERSON,
-- STUDENTS, STUDENT_ACAD_CRED, TRANSCRIPT_ORDERS, etc.), reflecting a working
-- pattern confirmed against real data — but the specific operator codes,
-- term-description filter, and reg-time-period code below are
-- institution-specific. Adapt them to your own instance; don't copy-paste
-- verbatim. Copy this file, edit your copy, and point DOB_RECONCILE_SQL_FILE
-- at it.
--
-- Requirements enforced by app/dob_sql_source.py before this ever runs:
--   - exactly one statement (no trailing/leading extra statements)
--   - must start with SELECT or WITH
--   - must not contain INSERT/UPDATE/DELETE/DROP/ALTER/EXEC/MERGE/TRUNCATE/
--     CREATE/GRANT/REVOKE/sp_*/INTO anywhere in the statement (INTO is
--     blocked because T-SQL's SELECT ... INTO creates a table)
--   (that text-level check is a footgun-catcher, not the real security
--   boundary — grant the DOB_RECONCILE_DB_USER login SELECT-only permission
--   on these views at the database level; see warning.md)
--
-- Output columns MUST be aliased exactly as below — these are the names
-- app/dob_detector.py's DEFAULT_COLUMNS maps onto the same Record shape the
-- CSV upload path produces. corroborating_dob/corroborating_source are
-- OPTIONAL — omit that join entirely if you have no same-person corroboration
-- source; the detector no-ops on a missing/blank corroborating_dob.
--
-- IMPORTANT — avoid join fan-out: STUDENT_ACAD_CRED/TERMS/STUDENT_COURSE_SEC
-- below are per-registration granularity (one row per course a student is
-- registered for). None of their columns are SELECTed — they only establish
-- "does this person have a qualifying registration" — so they're wrapped in
-- EXISTS(...) rather than INNER JOINed. INNER JOINing them directly
-- re-emits one PERSON row per matching course registration, silently
-- inflating the row count (confirmed: one real pull returned 34,230 rows for
-- only 15,319 distinct people — 55% pure duplicate rows — before this fix).
--
-- ORIGIN: PERSON_ADD_OPERATOR carries the actual operator/process code that
-- created the PERSON record, not a human-readable "INSTANT_ENROLL"-style
-- label — app/dob_detector.py's IE_ORIGIN_VALUES defaults won't match it.
-- Set DOB_RECONCILE_IE_ORIGIN_CODES in .env to whatever codes your own web
-- registration/guest/cashier self-service processes actually use (confirm
-- with a query like Q0 below before trusting this filter) — do NOT hardcode
-- institution-specific operator codes into app/dob_detector.py itself.
--
-- CORROBORATION: TRANSCRIPT_ORDERS is one example of a same-person,
-- independently-resubmitted DOB source (see app/dob_detector.py's module
-- docstring for why this matters more than cross-person duplicate pairing
-- for this specific bug — a direct audit found no duplicate PERSON records
-- with differing birth dates are being created by this bug, so the
-- historical backlog has little to no twin to pair against). Financial aid
-- application data or any other "person restates their own DOB on a later,
-- separate occasion" source works the same way — swap the join if you have
-- a better one. Only rows where the two dates differ by exactly one day are
-- this bug's signature; larger deltas are a different, unrelated
-- data-quality issue and are intentionally left for the detector to ignore.

-- Q0 — run this FIRST to confirm which PERSON_ADD_OPERATOR codes actually
-- correspond to your self-service web registration path before trusting the
-- WHERE filter below. Do not assume the values below without checking:
--   SELECT p.PERSON_ADD_OPERATOR, COUNT(*) AS n
--   FROM PERSON p
--   GROUP BY p.PERSON_ADD_OPERATOR
--   ORDER BY n DESC;

SELECT
    p.ID                                                       AS person_id,
    UPPER(LTRIM(RTRIM(p.LAST_NAME)))                           AS last_name,
    UPPER(LTRIM(RTRIM(p.FIRST_NAME)))                          AS first_name,
    UPPER(LTRIM(RTRIM(ISNULL(p.MIDDLE_NAME, ''))))             AS middle_name,
    p.BIRTH_DATE                                               AS birth_date,
    UPPER(LTRIM(RTRIM(ISNULL(al.ADDRESS_LINES, ''))))          AS addr_line1,
    UPPER(LTRIM(RTRIM(ISNULL(a.CITY, ''))))                    AS city,
    UPPER(LTRIM(RTRIM(ISNULL(a.[STATE], ''))))                 AS state,
    LEFT(LTRIM(RTRIM(ISNULL(a.ZIP, ''))), 5)                   AS zip,
    LOWER(LTRIM(RTRIM(ISNULL(e.PERSON_EMAIL_ADDRESSES, ''))))  AS email,
    -- Strip common punctuation so phone comparison isn't defeated by
    -- formatting differences (identity_score() also normalizes to digits,
    -- but cleaning here avoids depending on that for other consumers).
    REPLACE(REPLACE(REPLACE(REPLACE(
        ISNULL(ph.PERSONAL_PHONE_NUMBER, ''), '-', ''), '(', ''), ')', ''), ' ', '')
                                                                AS phone,
    p.PERSON_ADD_OPERATOR                                      AS origin,
    p.PERSON_ADD_DATE                                          AS created_date,
    tro.TRO_STU_BIRTH_DATE                                     AS corroborating_dob,
    'transcript_order'                                         AS corroborating_source
FROM PERSON p
    LEFT JOIN [ADDRESS] a       ON a.ADDRESS_ID = p.PREFERRED_ADDRESS
    LEFT JOIN ADDRESS_LS al     ON a.ADDRESS_ID = al.ADDRESS_ID
    LEFT JOIN PEOPLE_EMAIL e    ON e.ID = p.ID AND e.PERSON_PREFERRED_EMAIL = 'y'
    LEFT JOIN PERPHONE ph       ON ph.ID = p.ID AND ph.POS = 1
    -- Only "matches" (non-NULL) when the two dates actually differ, so a
    -- clean/matching transcript order correctly looks the same as no
    -- transcript order at all (both come back NULL via the LEFT JOIN).
    LEFT JOIN TRANSCRIPT_ORDERS tro
        ON tro.TRO_STUDENT = p.ID
        AND p.BIRTH_DATE <> tro.TRO_STU_BIRTH_DATE
WHERE
    p.BIRTH_DATE IS NOT NULL
    -- IE predicate — confirm these codes with Q0 above before trusting them:
    AND p.PERSON_ADD_OPERATOR IN ('0420024', 'WEBCASHIER', 'GUEST')
    AND EXISTS (
        SELECT 1
        FROM STUDENTS s
        JOIN STUDENT_ACAD_CRED sac ON s.STUDENTS_ID = sac.STC_PERSON_ID
        JOIN TERMS t ON sac.STC_TERM = t.TERMS_ID
        JOIN STUDENT_COURSE_SEC scs ON sac.STC_STUDENT_COURSE_SEC = scs.STUDENT_COURSE_SEC_ID
        WHERE s.STUDENTS_ID = p.ID
          AND t.TERM_DESC LIKE '%Open%'
          AND scs.SCS_REG_TIME_PERIOD = 'R'
    )
ORDER BY p.LAST_NAME, p.FIRST_NAME, p.BIRTH_DATE;

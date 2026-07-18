from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class ColleagueMnemonic(db.Model):
    __tablename__ = "colleague_mnemonics"

    id = db.Column(db.Integer, primary_key=True)
    mnemonic = db.Column(db.String(100), nullable=False, unique=True)
    colleague_file = db.Column(db.String(200))
    eedm_resource = db.Column(db.String(200))
    eedm_version = db.Column(db.String(10))
    cn_supported = db.Column(db.Boolean, default=False)
    cn_notes = db.Column(db.Text)
    field_mappings = db.Column(db.JSON)
    gotchas = db.Column(db.Text)
    related_mnemonics = db.Column(db.JSON)
    last_updated = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "mnemonic": self.mnemonic,
            "colleague_file": self.colleague_file,
            "eedm_resource": self.eedm_resource,
            "eedm_version": self.eedm_version,
            "cn_supported": self.cn_supported,
            "cn_notes": self.cn_notes,
            "field_mappings": self.field_mappings or [],
            "gotchas": self.gotchas,
            "related_mnemonics": self.related_mnemonics or [],
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "updated_by": self.updated_by,
        }


class ReplayHistory(db.Model):
    __tablename__ = "replay_history"

    id = db.Column(db.Integer, primary_key=True)
    replayed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source_message_id = db.Column(db.String(100))
    resource_name = db.Column(db.String(200))
    operation = db.Column(db.String(50))
    workflow_name = db.Column(db.String(200))
    conductor_url = db.Column(db.String(500))
    conductor_workflow_id = db.Column(db.String(200))
    outcome = db.Column(db.String(50))
    error_message = db.Column(db.Text)

    def to_dict(self):
        return {
            "id": self.id,
            "replayed_at": self.replayed_at.isoformat() if self.replayed_at else None,
            "source_message_id": self.source_message_id,
            "resource_name": self.resource_name,
            "operation": self.operation,
            "workflow_name": self.workflow_name,
            "conductor_url": self.conductor_url,
            "conductor_workflow_id": self.conductor_workflow_id,
            "outcome": self.outcome,
            "error_message": self.error_message,
        }


class AuditEntry(db.Model):
    """Audit row for every state-changing or sensitive read operation.

    Replaces the C# CNM AuditEntry one-for-one in shape and intent, kept
    deliberately small so the same record covers Colleague reads, change-
    notification publishes, Conductor replays, mnemonic edits, and any
    future surface. `detail` is the catch-all JSON blob — put before/after
    state, source IP, failure reasons, anything situational.
    """
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    actor = db.Column(db.String(256), nullable=False, default="system", index=True)
    actor_display_name = db.Column(db.String(512))
    action = db.Column(db.String(64), nullable=False)
    resource_type = db.Column(db.String(128), nullable=False)
    resource_id = db.Column(db.String(512), index=True)
    outcome = db.Column(db.String(32), nullable=False, default="success")
    failure_reason = db.Column(db.Text)
    detail = db.Column(db.JSON)
    correlation_id = db.Column(db.String(64), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "actor": self.actor,
            "actor_display_name": self.actor_display_name,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "outcome": self.outcome,
            "failure_reason": self.failure_reason,
            "detail": self.detail or {},
            "correlation_id": self.correlation_id,
        }


class EthosErrorLog(db.Model):
    __tablename__ = "ethos_error_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = db.Column(db.String(100))
    endpoint = db.Column(db.String(200))
    http_status = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    resource_name = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source": self.source,
            "endpoint": self.endpoint,
            "http_status": self.http_status,
            "error_message": self.error_message,
            "resource_name": self.resource_name,
        }


class FilterPreset(db.Model):
    __tablename__ = "filter_presets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    resource_filter = db.Column(db.String(200), default="")
    operation_filter = db.Column(db.String(50), default="all")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "resource_filter": self.resource_filter or "",
            "operation_filter": self.operation_filter or "all",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


SEED_MNEMONICS = [
    {"mnemonic": "PERSON", "colleague_file": "PERSON", "eedm_resource": "persons", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Core person record — fires on most demographic changes",
     "gotchas": "PERSON.PREFERRED.NAME is a single-value override; prefer PERSON.FIRST.NAME + PERSON.LAST.NAME for display",
     "related_mnemonics": ["EACH", "STU.ACAD.LEVELS", "STUDENT"]},
    {"mnemonic": "EACH", "colleague_file": "ENTITY.ADDRESS.CHANGES", "eedm_resource": "person-addresses", "eedm_version": "11",
     "cn_supported": True, "cn_notes": "Fires on address create/update/delete",
     "gotchas": "EACH.PHONE.NUMBERS is @VM-delimited (ASCII 253). Split on chr(253) before mapping to ContactPointPhone arrays",
     "related_mnemonics": ["PERSON", "PHONE.TYPES", "ADDR.TYPES"]},
    {"mnemonic": "STUDENT", "colleague_file": "STUDENT", "eedm_resource": "students", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Enrollment data — fires on enrollment status changes",
     "related_mnemonics": ["PERSON", "STU.ACAD.LEVELS"]},
    {"mnemonic": "STU.ACAD.LEVELS", "colleague_file": "STU.ACAD.LEVELS", "eedm_resource": "student-academic-levels", "eedm_version": "15",
     "cn_supported": True, "cn_notes": "Academic level data per student",
     "related_mnemonics": ["STUDENT", "ACAD.CRED"]},
    {"mnemonic": "COURSES", "colleague_file": "COURSES", "eedm_resource": "courses", "eedm_version": "16",
     "cn_supported": False, "cn_notes": "Course catalog — CN not typically enabled",
     "related_mnemonics": ["COURSE.SECTIONS", "DEPARTMENTS"]},
    {"mnemonic": "COURSE.SECTIONS", "colleague_file": "COURSE.SECTIONS", "eedm_resource": "sections", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Section offerings — fires on meeting time changes, instructor changes, and enrollment changes",
     "gotchas": "Section meeting patterns are multi-value. Each @VM delimited row is one meeting time",
     "related_mnemonics": ["COURSES", "TERMS", "DEPARTMENTS"]},
    {"mnemonic": "APPLICANTS", "colleague_file": "APPLICANTS", "eedm_resource": "applications", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Admissions applications — fires on status changes",
     "related_mnemonics": ["PERSON", "APPLICATION.STATUSES"]},
    {"mnemonic": "ACAD.PROGRAMS", "colleague_file": "ACAD.PROGRAMS", "eedm_resource": "academic-programs", "eedm_version": "15",
     "cn_supported": True, "cn_notes": "⚠ Known TRIGGER_CONDITIONS gap — INTG.ACAD.PROGRAMS trigger may not fire in all versions",
     "gotchas": "TRIGGER_CONDITIONS bug: check CINC form for INTG.ACAD.PROGRAMS. If CN is silent on program changes, verify the trigger table is not empty",
     "related_mnemonics": ["INTG.ACAD.PROGRAMS", "ACAD.CRED"]},
    {"mnemonic": "INTG.ACAD.PROGRAMS", "colleague_file": "INTG.ACAD.PROGRAMS", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Internal trigger table used for CN triggers. Not a direct EEDM resource",
     "gotchas": "This is the table that TRIGGER_CONDITIONS checks. If ACAD.PROGRAMS CN is silent, check this table in Colleague CINC form",
     "related_mnemonics": ["ACAD.PROGRAMS"]},
    {"mnemonic": "ACAD.CRED", "colleague_file": "ACAD.CRED", "eedm_resource": "student-academic-credentials", "eedm_version": "3",
     "cn_supported": True, "cn_notes": "Student credentials/degrees",
     "related_mnemonics": ["ACAD.PROGRAMS", "ACAD.CREDENTIALS"]},
    {"mnemonic": "TERMS", "colleague_file": "TERMS", "eedm_resource": "academic-periods", "eedm_version": "6",
     "cn_supported": True, "cn_notes": "Term/session definitions",
     "related_mnemonics": ["COURSE.SECTIONS", "STU.ACAD.LEVELS"]},
    {"mnemonic": "DEPARTMENTS", "colleague_file": "DEPARTMENTS", "eedm_resource": "departments", "eedm_version": "15",
     "cn_supported": False, "cn_notes": "Department definitions — rarely changes, CN typically not needed",
     "related_mnemonics": ["COURSES", "COURSE.SECTIONS"]},
    {"mnemonic": "LOCATIONS", "colleague_file": "LOCATIONS", "eedm_resource": "sites", "eedm_version": "8",
     "cn_supported": False, "cn_notes": "Campus location/site definitions",
     "related_mnemonics": ["COURSE.SECTIONS"]},
    {"mnemonic": "PHONE.TYPES", "colleague_file": "PHONE.TYPES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Lookup table for phone type codes (e.g. HOME, CELL, BUS)",
     "related_mnemonics": ["EACH", "PERSON"]},
    {"mnemonic": "ADDR.TYPES", "colleague_file": "ADDR.TYPES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Lookup table for address type codes",
     "related_mnemonics": ["EACH"]},
    {"mnemonic": "PERSON.EMAIL.TYPES", "colleague_file": "PERSON.EMAIL.TYPES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Lookup table for email type codes",
     "related_mnemonics": ["PERSON"]},
    {"mnemonic": "APPLICATION.STATUSES", "colleague_file": "APPLICATION.STATUSES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Admissions application status code lookup",
     "related_mnemonics": ["APPLICANTS"]},
    {"mnemonic": "ACAD.CREDENTIALS", "colleague_file": "ACAD.CREDENTIALS", "eedm_resource": "academic-credentials", "eedm_version": "6",
     "cn_supported": False, "cn_notes": "Degree type definitions (B.A., M.S., etc.)",
     "related_mnemonics": ["ACAD.CRED"]},
    {"mnemonic": "CRED.TYPES", "colleague_file": "CRED.TYPES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Colleague credential type codes — maps to person-credentials credentialType",
     "related_mnemonics": ["PERSON"]},
    {"mnemonic": "PERSON.ORIGIN.CODES", "colleague_file": "PERSON.ORIGIN.CODES", "eedm_resource": None, "eedm_version": None,
     "cn_supported": False, "cn_notes": "Lookup for person origin (how the person was created in Colleague)",
     "related_mnemonics": ["PERSON"]},
    {"mnemonic": "INSTITUTIONS", "colleague_file": "INSTITUTIONS", "eedm_resource": "educational-institutions", "eedm_version": "7",
     "cn_supported": False, "cn_notes": "External institution lookup — used in person-external-education",
     "related_mnemonics": ["APPLICANTS"]},
    {"mnemonic": "GRADES", "colleague_file": "GRADES", "eedm_resource": "grade-definitions", "eedm_version": "6",
     "cn_supported": False, "cn_notes": "Grade scale definitions",
     "related_mnemonics": ["ACAD.CRED"]},
    {"mnemonic": "ROOM.ASSIGN", "colleague_file": "ROOM.ASSIGN", "eedm_resource": "room-assignments", "eedm_version": "10",
     "cn_supported": True, "cn_notes": "Housing room assignments",
     "related_mnemonics": ["PERSON"]},
    {"mnemonic": "MEAL.ASSIGN", "colleague_file": "MEAL.ASSIGN", "eedm_resource": "meal-plan-assignments", "eedm_version": "6",
     "cn_supported": True, "cn_notes": "Meal plan assignments",
     "related_mnemonics": ["ROOM.ASSIGN"]},
    {"mnemonic": "STUDENT.PROGRAMS", "colleague_file": "STUDENT.PROGRAMS", "eedm_resource": "student-academic-programs", "eedm_version": "15",
     "cn_supported": True, "cn_notes": "Student program declarations — fires on major/minor changes",
     "related_mnemonics": ["STUDENT", "ACAD.PROGRAMS"]},
    {"mnemonic": "STUDENT.ACAD.CRED", "colleague_file": "STUDENT.ACAD.CRED", "eedm_resource": "section-registrations", "eedm_version": "7",
     "cn_supported": True, "cn_notes": "Individual course registration — fires on add/drop",
     "gotchas": "Grade changes also fire a STUDENT.ACAD.CRED CN even though the operation may be 'updated'",
     "related_mnemonics": ["STUDENT", "COURSE.SECTIONS"]},
    {"mnemonic": "STAFF", "colleague_file": "STAFF", "eedm_resource": "persons", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Staff person records — shares EEDM resource with PERSON. Filter by type in Ethos",
     "related_mnemonics": ["PERSON"]},
    {"mnemonic": "FACULTY", "colleague_file": "FACULTY", "eedm_resource": "persons", "eedm_version": "16",
     "cn_supported": True, "cn_notes": "Faculty person records — shares EEDM resource with PERSON",
     "related_mnemonics": ["PERSON", "STAFF"]},
    {"mnemonic": "FINANCIAL.AID", "colleague_file": "CS.ACYR", "eedm_resource": "financial-aid-applications", "eedm_version": "3",
     "cn_supported": False, "cn_notes": "Financial aid application data — CN typically not enabled",
     "related_mnemonics": ["STUDENT"]},
    {"mnemonic": "AR.INVOICES", "colleague_file": "AR.INVOICES", "eedm_resource": "student-charges", "eedm_version": "2",
     "cn_supported": False, "cn_notes": "Student account charges",
     "related_mnemonics": ["STUDENT"]},
]


def seed_mnemonics(app):
    with app.app_context():
        for entry in SEED_MNEMONICS:
            if not ColleagueMnemonic.query.filter_by(mnemonic=entry["mnemonic"]).first():
                db.session.add(ColleagueMnemonic(**entry))
        db.session.commit()


class ResourceAnnotation(db.Model):
    __tablename__ = "resource_annotations"
    id = db.Column(db.Integer, primary_key=True)
    resource_name = db.Column(db.String(200), nullable=False, unique=True)
    trigger_conditions_gap = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    updated_by = db.Column(db.String(100))
    last_updated = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "resource_name": self.resource_name,
            "trigger_conditions_gap": self.trigger_conditions_gap,
            "notes": self.notes,
            "updated_by": self.updated_by,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class SavedQuery(db.Model):
    __tablename__ = "saved_queries"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    query_text = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON)
    is_preloaded = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(100))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "query_text": self.query_text,
            "variables": self.variables or {},
            "is_preloaded": self.is_preloaded,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_by": self.updated_by,
        }


SEED_SAVED_QUERIES = [
    {
        "name": "Person by ID — names + credentials",
        "query_text": "query GetPerson($id: String!) { persons16(filter: { id: { EQ: $id } }) { edges { node { id names { firstName lastName preferredName } credentials { type { credentialType } value } } } } }",
        "variables": {"id": ""},
        "is_preloaded": True,
    },
    {
        "name": "Student academic programs",
        "query_text": "query GetStudentPrograms($studentId: String!) { studentAcademicPrograms15(filter: { student: { id: { EQ: $studentId } } }) { edges { node { id student { id } program { id } enrollmentStatus { enrollmentStatus } startOn endOn } } } }",
        "variables": {"studentId": ""},
        "is_preloaded": True,
    },
    {
        "name": "Sections with meetings",
        "query_text": "query GetSections($termId: String!) { sections16(filter: { academicPeriod: { id: { EQ: $termId } } }) { edges { node { id course { id } number meeting { startOn endOn days startTime endTime } } } } }",
        "variables": {"termId": ""},
        "is_preloaded": True,
    },
    {
        "name": "Person addresses",
        "query_text": "query GetAddresses($personId: String!) { personAddresses11(filter: { person: { id: { EQ: $personId } } }) { edges { node { id type { addressType } address { addressLines city state { abbreviation } postalCode } } } } }",
        "variables": {"personId": ""},
        "is_preloaded": True,
    },
    {
        "name": "Applications (admissions)",
        "query_text": "query GetApplications { applications16 { edges { node { id applicant { id } academicPeriod { id } appliedOn admissionPopulation { admissionPopulation } } } } }",
        "variables": {},
        "is_preloaded": True,
    },
]


def seed_saved_queries(app):
    with app.app_context():
        for entry in SEED_SAVED_QUERIES:
            if not SavedQuery.query.filter_by(name=entry["name"]).first():
                db.session.add(SavedQuery(**entry))
        db.session.commit()


class DobDecision(db.Model):
    """Reviewer disposition for one DOB Repair candidate pair (PD0002124).

    The detector (app/dob_detector.py) proposes; this table is where a
    reviewer disposes. A decision only marks which record a human has
    approved for correction — this table itself is still never written to
    Colleague directly.

    When DOB_RECONCILE_AUTO_APPLY is enabled (see app/routes/dob_repair.py),
    an "accept" additionally triggers a Conductor workflow
    (DOB_RECONCILE_APPLY_WORKFLOW_NAME, default "ethos_update_person_dob")
    that performs the actual Ethos PUT + change-notification publish outside
    this app — conductor_workflow_id/apply_triggered_at/apply_error below
    are that trigger's outcome, not confirmation that Colleague itself was
    updated (this app has no visibility into the workflow's own execution
    once handed off). With DOB_RECONCILE_AUTO_APPLY off (the default), the
    CSV from GET /api/dob-repair/export/corrections remains the only
    write-adjacent output, same as before.

    candidate_id is the detector's stable, order-independent pair key
    (sorted person_id pair), so decisions survive re-analysis against a
    fresh PERSON export as long as the same two person_ids reappear.
    """
    __tablename__ = "dob_decisions"

    candidate_id = db.Column(db.String(200), primary_key=True)
    action = db.Column(db.String(20), nullable=False)
    corrected_person_id = db.Column(db.String(100))
    corrected_from = db.Column(db.String(20))
    corrected_to = db.Column(db.String(20))
    reviewer = db.Column(db.String(100), default="unknown")
    decided_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    note = db.Column(db.Text)
    # Set only when DOB_RECONCILE_AUTO_APPLY triggered (or attempted to
    # trigger) the Conductor apply workflow for this decision — see the
    # class docstring above.
    conductor_workflow_id = db.Column(db.String(200))
    apply_triggered_at = db.Column(db.DateTime(timezone=True))
    apply_error = db.Column(db.Text)

    def to_dict(self):
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "corrected_person_id": self.corrected_person_id,
            "corrected_from": self.corrected_from,
            "corrected_to": self.corrected_to,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "note": self.note or "",
            "conductor_workflow_id": self.conductor_workflow_id,
            "apply_triggered_at": self.apply_triggered_at.isoformat() if self.apply_triggered_at else None,
            "apply_error": self.apply_error,
        }

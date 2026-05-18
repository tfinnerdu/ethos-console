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
            "conductor_workflow_id": self.conductor_workflow_id,
            "outcome": self.outcome,
            "error_message": self.error_message,
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

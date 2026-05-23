"""Shared fixtures for CONSOLE_MOCK_MODE.

Realistic-shaped data for every upstream the console talks to. Shapes mirror
what the real services return; values are fabricated. Touched only when
CONSOLE_MOCK_MODE=true — never imported by real-mode code paths.

Pinned by tests in tests/test_mock_mode.py so changes here surface as a
characterization-test failure rather than a silent UI regression.
"""
from datetime import datetime, timezone


# Stable mock GUIDs (look like real Ethos UUIDs but are clearly fabricated).
_GUIDS = {
    "person_a":   "00000000-0000-4000-8000-0000000000a1",
    "person_b":   "00000000-0000-4000-8000-0000000000a2",
    "person_c":   "00000000-0000-4000-8000-0000000000a3",
    "section_a":  "00000000-0000-4000-8000-0000000000b1",
    "section_b":  "00000000-0000-4000-8000-0000000000b2",
    "course_a":   "00000000-0000-4000-8000-0000000000c1",
    "appl_a":     "00000000-0000-4000-8000-0000000000d1",
    "appl_b":     "00000000-0000-4000-8000-0000000000d2",
    "addr_a":     "00000000-0000-4000-8000-0000000000e1",
    "term_a":     "00000000-0000-4000-8000-0000000000f1",
}


def _repr(version: int) -> dict:
    return {
        "X-Media-Type": f"application/vnd.hedtech.integration.v{version}+json",
        "methods": ["get"],
        "version": str(version),
    }


# /api/available-resources shape (Ethos REST).
AVAILABLE_RESOURCES = [
    {"name": "persons",                        "representations": [_repr(16)]},
    {"name": "person-addresses",               "representations": [_repr(11)]},
    {"name": "students",                       "representations": [_repr(16)]},
    {"name": "student-academic-levels",        "representations": [_repr(15)]},
    {"name": "student-academic-programs",      "representations": [_repr(15)]},
    {"name": "student-academic-credentials",   "representations": [_repr(3)]},
    {"name": "courses",                        "representations": [_repr(16)]},
    {"name": "sections",                       "representations": [_repr(16)]},
    {"name": "section-registrations",          "representations": [_repr(7)]},
    {"name": "academic-periods",               "representations": [_repr(6)]},
    {"name": "academic-programs",              "representations": [_repr(15)]},
    {"name": "academic-credentials",           "representations": [_repr(6)]},
    {"name": "applications",                   "representations": [_repr(16)]},
    {"name": "departments",                    "representations": [_repr(15)]},
    {"name": "sites",                          "representations": [_repr(8)]},
    {"name": "room-assignments",               "representations": [_repr(10)]},
    {"name": "meal-plan-assignments",          "representations": [_repr(6)]},
    {"name": "educational-institutions",       "representations": [_repr(7)]},
    {"name": "grade-definitions",              "representations": [_repr(6)]},
    {"name": "financial-aid-applications",     "representations": [_repr(3)]},
    {"name": "student-charges",                "representations": [_repr(2)]},
    {"name": "advancement-appointments",       "representations": [_repr(1)]},
]

# /api/change-notifications/available-resources shape — subset.
CN_RESOURCES = [
    {"resourceName": "persons"},
    {"resourceName": "person-addresses"},
    {"resourceName": "students"},
    {"resourceName": "student-academic-levels"},
    {"resourceName": "student-academic-programs"},
    {"resourceName": "student-academic-credentials"},
    {"resourceName": "sections"},
    {"resourceName": "section-registrations"},
    {"resourceName": "academic-periods"},
    {"resourceName": "applications"},
    {"resourceName": "room-assignments"},
    {"resourceName": "meal-plan-assignments"},
]

# Pool the bus monitor cycles through. Each is a real-shaped change notification
# minus the server-assigned id (the mock client stamps id sequentially).
_CN_TEMPLATE_POOL = [
    {"resource": {"name": "persons",                "id": _GUIDS["person_a"], "operation": "updated"},  "contentType": "resource-representation-key", "content": {"id": _GUIDS["person_a"]}},
    {"resource": {"name": "person-addresses",       "id": _GUIDS["addr_a"],   "operation": "created"},  "contentType": "resource-representation",     "content": {"id": _GUIDS["addr_a"], "person": {"id": _GUIDS["person_a"]}}},
    {"resource": {"name": "students",               "id": _GUIDS["person_b"], "operation": "replaced"}, "contentType": "resource-representation-key", "content": {"id": _GUIDS["person_b"]}},
    {"resource": {"name": "sections",               "id": _GUIDS["section_a"],"operation": "updated"},  "contentType": "resource-representation",     "content": {"id": _GUIDS["section_a"], "number": "101"}},
    {"resource": {"name": "section-registrations",  "id": _GUIDS["section_b"],"operation": "created"},  "contentType": "resource-representation-key", "content": {"id": _GUIDS["section_b"]}},
    {"resource": {"name": "student-academic-programs", "id": _GUIDS["person_c"], "operation": "updated"}, "contentType": "resource-representation-key", "content": {"id": _GUIDS["person_c"]}},
    {"resource": {"name": "applications",           "id": _GUIDS["appl_a"],   "operation": "updated"},  "contentType": "resource-representation",     "content": {"id": _GUIDS["appl_a"]}},
    {"resource": {"name": "academic-periods",       "id": _GUIDS["term_a"],   "operation": "updated"},  "contentType": "resource-representation",     "content": {"id": _GUIDS["term_a"], "code": "FA26"}},
]


def cn_stream_template_pool() -> list:
    return list(_CN_TEMPLATE_POOL)


# Sample resource bodies for get_resource_by_id / get_resource. Sparse but
# representative of the actual EEDM shape so the JSON viewer shows something
# meaningful. Versions are arbitrary mock values, not pinned to real schemas.
RESOURCE_PAYLOADS: dict = {
    "persons": [{
        "id": _GUIDS["person_a"],
        "names": [{"firstName": "Avery", "lastName": "Mock", "preferredName": "Av"}],
        "credentials": [
            {"type": {"credentialType": "bannerId"}, "value": "B00001"},
            {"type": {"credentialType": "colleaguePersonId"}, "value": "STU001234"},
        ],
        "_mock": True,
    }],
    "person-addresses": [{
        "id": _GUIDS["addr_a"],
        "person": {"id": _GUIDS["person_a"]},
        "type": {"addressType": "home"},
        "address": {
            "addressLines": ["1014 Boswell Ave"],
            "city": "Crete",
            "state": {"abbreviation": "NE"},
            "postalCode": "68333",
        },
        "_mock": True,
    }],
    "students": [{
        "id": _GUIDS["person_b"],
        "person": {"id": _GUIDS["person_b"]},
        "type": {"studentType": "undergraduate"},
        "_mock": True,
    }],
    "sections": [{
        "id": _GUIDS["section_a"],
        "course": {"id": _GUIDS["course_a"]},
        "number": "101",
        "academicPeriod": {"id": _GUIDS["term_a"]},
        "_mock": True,
    }],
    "applications": [{
        "id": _GUIDS["appl_a"],
        "applicant": {"id": _GUIDS["person_a"]},
        "appliedOn": "2026-03-15",
        "_mock": True,
    }],
}


# GraphQL introspection — minimal but realistic enough that the Schema Browser
# and GraphQL tab render Query fields plus a couple of object types.
def _scalar(name: str = "String") -> dict:
    return {"kind": "SCALAR", "name": name, "ofType": None}


def _obj(name: str) -> dict:
    return {"kind": "OBJECT", "name": name, "ofType": None}


def _field(name: str, type_ref: dict) -> dict:
    return {"name": name, "type": type_ref}


INTROSPECTION_SCHEMA = {
    "queryType": {"name": "Query"},
    "types": [
        {
            "name": "Query",
            "kind": "OBJECT",
            "fields": [
                _field("persons16",                  _obj("persons16")),
                _field("personAddresses11",          _obj("personAddresses11")),
                _field("students16",                 _obj("students16")),
                _field("studentAcademicLevels15",    _obj("studentAcademicLevels15")),
                _field("studentAcademicPrograms15",  _obj("studentAcademicPrograms15")),
                _field("courses16",                  _obj("courses16")),
                _field("sections16",                 _obj("sections16")),
                _field("sectionRegistrations7",      _obj("sectionRegistrations7")),
                _field("academicPeriods6",           _obj("academicPeriods6")),
                _field("applications16",             _obj("applications16")),
                _field("advancementAppointments1",   _obj("advancementAppointments1")),
            ],
        },
        {
            "name": "persons16", "kind": "OBJECT",
            "fields": [
                _field("id",            _scalar("String")),
                _field("firstName",     _scalar("String")),
                _field("lastName",      _scalar("String")),
                _field("preferredName", _scalar("String")),
            ],
        },
        {
            "name": "sections16", "kind": "OBJECT",
            "fields": [
                _field("id",        _scalar("String")),
                _field("number",    _scalar("String")),
                _field("course",    _obj("courses16")),
            ],
        },
        {
            "name": "courses16", "kind": "OBJECT",
            "fields": [
                _field("id",        _scalar("String")),
                _field("title",     _scalar("String")),
                _field("number",    _scalar("String")),
            ],
        },
        {
            "name": "applications16", "kind": "OBJECT",
            "fields": [
                _field("id",         _scalar("String")),
                _field("applicant",  _obj("persons16")),
                _field("appliedOn",  _scalar("String")),
            ],
        },
        {
            "name": "advancementAppointments1", "kind": "OBJECT",
            "fields": [
                _field("id",         _scalar("String")),
                _field("appointedOn", _scalar("String")),
            ],
        },
    ],
}


# ── CNM ──────────────────────────────────────────────────────────────────────

CNM_HEALTH = {
    "status": "Healthy",
    "service": "EthosCn",
    "version": "0.5.0-mock",
    "uptime_seconds": 7320,
    "mock": True,
}

_CNM_NOTIFICATIONS = [
    {"id": "CN-persons-001",                "resourceName": "persons",                "status": "Enabled",  "lastModified": "2026-05-10T14:22:00Z", "hasParagraph": True,  "paragraphCode": "INTG.PERSONS"},
    {"id": "CN-person-addresses-001",       "resourceName": "person-addresses",       "status": "Enabled",  "lastModified": "2026-05-10T14:22:00Z", "hasParagraph": True,  "paragraphCode": "INTG.PERSON.ADDR"},
    {"id": "CN-students-001",               "resourceName": "students",               "status": "Enabled",  "lastModified": "2026-05-10T14:22:00Z", "hasParagraph": True,  "paragraphCode": "INTG.STUDENTS"},
    {"id": "CN-academic-programs-001",      "resourceName": "academic-programs",      "status": "Disabled", "lastModified": "2026-01-04T09:00:00Z", "hasParagraph": False, "paragraphCode": None},
    {"id": "CN-sections-001",               "resourceName": "sections",               "status": "Enabled",  "lastModified": "2026-05-10T14:22:00Z", "hasParagraph": True,  "paragraphCode": "INTG.SECTIONS"},
    {"id": "CN-section-registrations-001",  "resourceName": "section-registrations",  "status": "Enabled",  "lastModified": "2026-05-10T14:22:00Z", "hasParagraph": True,  "paragraphCode": "INTG.SEC.REG"},
    {"id": "CN-applications-001",           "resourceName": "applications",           "status": "Enabled",  "lastModified": "2026-04-22T11:10:00Z", "hasParagraph": True,  "paragraphCode": "INTG.APPL"},
    {"id": "CN-room-assignments-001",       "resourceName": "room-assignments",       "status": "Unknown",  "lastModified": "2026-02-19T18:33:00Z", "hasParagraph": False, "paragraphCode": None},
]


def cnm_notifications() -> list:
    return [dict(n) for n in _CNM_NOTIFICATIONS]


CNM_DIAGNOSTICS = {
    "aligned":               ["persons", "person-addresses", "students", "sections", "section-registrations", "applications"],
    "subscribedNotPublished": ["academic-programs"],
    "publishedNotSubscribed": ["room-assignments"],
}

CNM_AUDIT_LOG = {
    "items": [
        {"timestamp": "2026-05-22T11:14:00Z", "userId": "mock-user", "action": "ChangeNotificationViewed",  "targetIdentifier": "CN-persons-001",   "outcome": "Success"},
        {"timestamp": "2026-05-22T11:13:55Z", "userId": "mock-user", "action": "DiagnosticsRun",            "targetIdentifier": "—",                 "outcome": "Success"},
        {"timestamp": "2026-05-22T10:02:00Z", "userId": "mock-user", "action": "ChangeNotificationViewed",  "targetIdentifier": "CN-sections-001",   "outcome": "Success"},
    ],
    "page": 1,
    "pageSize": 50,
    "totalPages": 1,
    "totalCount": 3,
}


# ── Colleague Web API ────────────────────────────────────────────────────────

COLLEAGUE_ABOUT = {
    "productName": "Ellucian Colleague Web API (mock)",
    "productVersion": "1.34.0-mock",
    "buildNumber": "0000",
}

COLLEAGUE_EVENT_CONFIGS = [
    {"resourceName": "persons",                "isEnabled": True,  "lastModified": "2026-05-10T14:22:00Z"},
    {"resourceName": "person-addresses",       "isEnabled": True,  "lastModified": "2026-05-10T14:22:00Z"},
    {"resourceName": "students",               "isEnabled": True,  "lastModified": "2026-05-10T14:22:00Z"},
    {"resourceName": "sections",               "isEnabled": True,  "lastModified": "2026-05-10T14:22:00Z"},
    {"resourceName": "academic-programs",      "isEnabled": False, "lastModified": "2026-01-04T09:00:00Z"},
]

COLLEAGUE_METADATA_MANIFEST = {
    "ApiDomain": "STUDENT",
    "ApiType": "READ",
    "Version": "1.0.0",
    "Routes": ["/api/students/{id}", "/api/students/{id}/academic-programs"],
    "_mock": True,
}


def colleague_transaction_result(transaction_id: str, payload: dict) -> dict:
    """Echo-style mock response so the UI sees a usable structured result."""
    return {
        "OutVariable": f"MOCK_OK_{transaction_id}",
        "OutListString": ["mocked-row-1", "mocked-row-2"],
        "EchoInput": payload,
        "_mock": True,
        "_disclaimer": "CONSOLE_MOCK_MODE — no Colleague call was made.",
    }


# ── Conductor ────────────────────────────────────────────────────────────────

def conductor_trigger_id(workflow_name: str) -> str:
    return f"mock-{workflow_name}-{int(datetime.now(timezone.utc).timestamp())}"


# ── UniData ──────────────────────────────────────────────────────────────────

UNIDATA_FILE_LIST = [
    "PERSON", "STUDENT", "STU.ACAD.LEVELS", "COURSES", "COURSE.SECTIONS",
    "APPLICANTS", "ACAD.PROGRAMS", "INTG.ACAD.PROGRAMS", "ACAD.CRED",
    "TERMS", "DEPARTMENTS", "LOCATIONS", "ROOM.ASSIGN", "MEAL.ASSIGN",
    "STUDENT.PROGRAMS", "STUDENT.ACAD.CRED",
]


def unidata_command_response(statement: str) -> str:
    """Return a plausible-looking TCL response for a few common verbs."""
    verb = (statement.split() or [""])[0].upper()
    if verb in ("LIST", "SELECT", "COUNT", "SORT"):
        if "VOC" in statement.upper():
            body = "\n".join(UNIDATA_FILE_LIST)
            return (
                f"{statement}\n\n"
                f"LIST VOC WITH F1 = 'F' BY @ID 14:33:01\n"
                f"@ID........\n"
                f"{body}\n\n"
                f"{len(UNIDATA_FILE_LIST)} records listed.\n"
                f"[CONSOLE_MOCK_MODE — no Colleague call was made]"
            )
        return (
            f"{statement}\n\n"
            f"MOCK FIRST.NAME LAST.NAME    @ID\n"
            f"Avery   Mock          STU001234\n"
            f"Blair   Mock          STU001235\n"
            f"Casey   Mock          STU001236\n\n"
            f"3 records listed.\n"
            f"[CONSOLE_MOCK_MODE — no Colleague call was made]"
        )
    return (
        f"{statement}\n\n"
        f"[CONSOLE_MOCK_MODE — write verbs are not executed; nothing happened.]"
    )


def unidata_subroutine_result(name: str, args: list) -> dict:
    return {
        "subroutine": name,
        "args": [
            {
                "index": i,
                "label": a.get("label", f"ARG{i + 1}"),
                "direction": a.get("direction", "in"),
                "value": f"MOCK_OUT_{i}" if a.get("direction", "in").lower() in ("out", "inout") else str(a.get("value", "")),
            }
            for i, a in enumerate(args)
        ],
        "_mock": True,
    }

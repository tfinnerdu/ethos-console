"""Tests for config.py's DATABASE_URL normalization (_normalize_database_url).

Accepts either a full DB URI or a bare filesystem path (matching the SF
Mission Control sibling app's simpler DATABASE_PATH convention) — see the
module docstring in config.py for why: a bare path sidesteps the Linux-vs-
Windows "how many slashes mean absolute" footgun entirely, since the app
builds the sqlite:/// URI itself instead of asking the operator to.
"""
from config import _normalize_database_url


class TestNormalizeDatabaseUrl:
    def test_blank_stays_blank(self):
        assert _normalize_database_url("") == ""
        assert _normalize_database_url("   ") == ""

    def test_bare_relative_filename(self):
        assert _normalize_database_url("sf_mission_control.db") == "sqlite:///sf_mission_control.db"

    def test_bare_unix_absolute_path(self):
        assert _normalize_database_url("/data/ethos_console.db") == "sqlite:////data/ethos_console.db"

    def test_bare_windows_absolute_path_backslashes(self):
        assert (
            _normalize_database_url(r"C:\data\ethos_console.db")
            == "sqlite:///C:/data/ethos_console.db"
        )

    def test_bare_windows_absolute_path_forward_slashes(self):
        assert (
            _normalize_database_url("C:/data/ethos_console.db")
            == "sqlite:///C:/data/ethos_console.db"
        )

    def test_full_postgres_uri_passthrough(self):
        uri = "postgresql://user:pass@localhost:5432/ethos_console"
        assert _normalize_database_url(uri) == uri

    def test_legacy_postgres_scheme_rewritten(self):
        assert (
            _normalize_database_url("postgres://user:pass@localhost:5432/ethos_console")
            == "postgresql://user:pass@localhost:5432/ethos_console"
        )

    def test_full_sqlite_uri_passthrough_unchanged(self):
        # Someone who already knows the URI convention shouldn't have it
        # rewritten out from under them.
        assert _normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
        assert _normalize_database_url("sqlite:////data/foo.db") == "sqlite:////data/foo.db"

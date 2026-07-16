"""Tests for create_app()'s fail-closed production DB check (app/__init__.py).

A production run with a relative-path sqlite:// DATABASE_URL (the accidental
default, e.g. "sqlite:///ethos_console.db") must refuse to boot — that file
lives in the container's ephemeral filesystem and disappears on every
redeploy. An absolute-path sqlite:// DATABASE_URL (e.g.
"sqlite:////data/ethos_console.db" on Linux, or "sqlite:///C:/data/..." on
Windows) is a deliberate PVC-backed deployment (matching DLM's real k8s
pattern) and must be allowed through, with a warning logged instead of a
hard failure.
"""
import logging
import os
import shutil
from unittest.mock import patch

import pytest

from app import create_app, _is_absolute_sqlite_path


def _create_production_app(database_uri: str):
    with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
        return create_app("production", overrides={
            "SQLALCHEMY_DATABASE_URI": database_uri,
            "TESTING": True,
        })


class TestProductionDbFailClosed:
    def test_relative_path_sqlite_refuses_to_boot(self):
        with pytest.raises(RuntimeError, match="Refusing to start"):
            _create_production_app("sqlite:///ethos_console.db")

    def test_relative_path_sqlite_memory_refuses_to_boot(self):
        with pytest.raises(RuntimeError, match="Refusing to start"):
            _create_production_app("sqlite:///:memory:")

    def test_absolute_path_sqlite_boots_with_warning(self, caplog, tmp_path):
        # A real absolute path (like a PVC mount would provide), so db.create_all()
        # inside create_app() has somewhere real to write — exercises the actual
        # boot path rather than mocking it away.
        db_file = tmp_path / "ethos_console.db"
        db_uri = f"sqlite:///{db_file}"  # 3 slashes + db_file's own leading "/" = 4
        assert db_uri.startswith("sqlite:////")
        with caplog.at_level(logging.WARNING):
            app = _create_production_app(db_uri)
        assert db_file.exists()
        assert any(
            "PersistentVolumeClaim" in record.message
            for record in caplog.records
        )

    def test_postgres_boots_with_no_warning(self, caplog):
        with caplog.at_level(logging.WARNING), \
             patch("app.database.db.create_all"), \
             patch("app.seed_mnemonics"), \
             patch("app.seed_saved_queries"):
            app = _create_production_app("postgresql://user:pass@localhost:5432/ethos_console")
        assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://")
        assert not any(
            "PersistentVolumeClaim" in record.message
            for record in caplog.records
        )

    def test_relative_path_sqlite_in_development_still_boots(self):
        with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            app = create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "TESTING": True,
            })
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"

    def test_windows_style_absolute_path_boots_with_warning(self, caplog):
        # A bare Windows path (config.py's _normalize_database_url) produces
        # 3 slashes, not 4 — is_absolute_path_sqlite must still recognize it
        # as deliberate, not the accidental relative-path default.
        with caplog.at_level(logging.WARNING), \
             patch("app.database.db.create_all"), \
             patch("app.seed_mnemonics"), \
             patch("app.seed_saved_queries"):
            app = _create_production_app("sqlite:///C:/data/ethos_console.db")
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///C:/data/ethos_console.db"
        assert any(
            "PersistentVolumeClaim" in record.message
            for record in caplog.records
        )


class TestIsAbsoluteSqlitePath:
    def test_unix_absolute(self):
        assert _is_absolute_sqlite_path("/data/ethos_console.db") is True

    def test_windows_absolute_forward_slashes(self):
        assert _is_absolute_sqlite_path("C:/data/ethos_console.db") is True

    def test_windows_absolute_backslashes(self):
        assert _is_absolute_sqlite_path("C:\\data\\ethos_console.db") is True

    def test_relative_path(self):
        assert _is_absolute_sqlite_path("ethos_console.db") is False

    def test_relative_path_with_subdir(self):
        assert _is_absolute_sqlite_path("data/ethos_console.db") is False


class TestSqliteParentDirectoryAutoCreate:
    """SQLite creates the db *file* on first connect but never a missing
    parent directory — a DATABASE_URL pointing at an as-yet-uncreated
    subdirectory used to fail at db.create_all() with an opaque "unable to
    open database file" and no indication of which path it tried."""

    def test_creates_missing_nested_parent_directory(self, tmp_path):
        db_file = tmp_path / "nested" / "sub" / "ethos_console.db"
        assert not db_file.parent.exists()
        with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
                "TESTING": True,
            })
        assert db_file.exists()

    def test_in_memory_sqlite_is_unaffected(self):
        with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            app = create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "TESTING": True,
            })
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"

    def test_relative_default_path_is_unaffected(self):
        with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            app = create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///ethos_console_test_default.db",
                "TESTING": True,
            })
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///ethos_console_test_default.db"
        # Cleanup: this one lands in the CWD, unlike the tmp_path-scoped cases above.
        if os.path.exists("ethos_console_test_default.db"):
            os.remove("ethos_console_test_default.db")


class TestDatabaseBackendLogging:
    """The app boots identically on SQLite or Postgres — no visible
    difference on screen — so without a boot-time log line, "why isn't my
    sqlite file showing up" is only answerable by reading config.py."""

    def test_sqlite_path_is_logged(self, caplog, tmp_path):
        db_file = tmp_path / "ethos_console.db"
        with caplog.at_level(logging.INFO), \
             patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
                "TESTING": True,
            })
        assert any(
            "Database: SQLite" in record.message and str(db_file) in record.message
            for record in caplog.records
        )

    def test_sqlite_in_memory_is_logged_distinctly(self, caplog):
        with caplog.at_level(logging.INFO), \
             patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "TESTING": True,
            })
        assert any(
            "Database: SQLite" in record.message and "in-memory" in record.message
            for record in caplog.records
        )

    def test_postgres_is_logged_with_password_hidden(self, caplog):
        with caplog.at_level(logging.INFO), \
             patch("app.ethos_client.EthosClient.is_configured", return_value=False), \
             patch("app.database.db.create_all"), \
             patch("app.seed_mnemonics"), \
             patch("app.seed_saved_queries"):
            create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "postgresql://user:supersecret@localhost:5432/ethos_console",
                "TESTING": True,
            })
        messages = [record.message for record in caplog.records if "Database:" in record.message]
        assert messages, "expected a Database: log line"
        assert not any("supersecret" in m for m in messages)
        assert any("postgresql://user" in m for m in messages)


class TestInstancePathResolution:
    """Flask-SQLAlchemy >= 3.0 resolves a *relative* sqlite path against
    app.instance_path, not the process's CWD — a real, easy-to-miss
    surprise (DATABASE_URL=ethos_console.db does NOT land next to run.py).
    create_app()'s logging and mkdir logic must account for that rewrite
    instead of computing a directory relative to CWD that Flask-SQLAlchemy
    never actually uses."""

    def test_relative_path_is_logged_under_instance_path(self, caplog):
        with caplog.at_level(logging.INFO), \
             patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            app = create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///ethos_console_instance_test.db",
                "TESTING": True,
            })
        expected = os.path.join(app.instance_path, "ethos_console_instance_test.db")
        try:
            assert os.path.exists(expected)
            assert any(expected in record.message for record in caplog.records)
        finally:
            if os.path.exists(expected):
                os.remove(expected)

    def test_relative_path_with_subdir_creates_directory_under_instance_path(self):
        with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
            app = create_app("development", overrides={
                "SQLALCHEMY_DATABASE_URI": "sqlite:///nested_subdir_test/ethos_console.db",
                "TESTING": True,
            })
        expected_dir = os.path.join(app.instance_path, "nested_subdir_test")
        expected_file = os.path.join(expected_dir, "ethos_console.db")
        try:
            assert os.path.exists(expected_file)
        finally:
            if os.path.exists(expected_dir):
                shutil.rmtree(expected_dir)

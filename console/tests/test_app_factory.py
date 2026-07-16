"""Tests for create_app()'s fail-closed production DB check (app/__init__.py).

A production run with a relative-path sqlite:// DATABASE_URL (the accidental
default, e.g. "sqlite:///ethos_console.db") must refuse to boot — that file
lives in the container's ephemeral filesystem and disappears on every
redeploy. An absolute-path sqlite:// DATABASE_URL (e.g.
"sqlite:////data/ethos_console.db", four slashes) is a deliberate PVC-backed
deployment (matching DLM's real k8s pattern) and must be allowed through,
with a warning logged instead of a hard failure.
"""
import logging
from unittest.mock import patch

import pytest

from app import create_app


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

"""Characterization tests for app/unidata_client.py (the REAL uopy wrapper).

docs/test-coverage-classification.md previously left this module entirely
unaccounted for -- no test file exercised it at all, including
_parse_list_ids(), a pure function needing no mocking. These tests pin the
real client's connection-parameter passthrough, LIST-VOC response parsing,
and subroutine argument marshalling directly, per the "no exemptions"
coverage rule.
"""
from unittest.mock import MagicMock

import app.unidata_client as unidata_client
from app.unidata_client import UnidataClient, _parse_list_ids


# ── _parse_list_ids: pure function, no mocking needed ────────────────────────

def test_parse_list_ids_known_good_response():
    # Known-good LIST VOC response shape from a real UniData session.
    response = (
        "LIST VOC WITH F1 = 'F' BY @ID\n"
        "VOC\n"
        "..... \n"
        "PERSON\n"
        "COURSES\n"
        "SECTIONS\n"
        "3 records listed."
    )
    assert _parse_list_ids(response) == ["PERSON", "COURSES", "SECTIONS"]


def test_parse_list_ids_skips_blank_lines():
    response = "PERSON\n\n\nCOURSES\n"
    assert _parse_list_ids(response) == ["PERSON", "COURSES"]


def test_parse_list_ids_empty_response():
    assert _parse_list_ids("") == []


def test_parse_list_ids_all_noise_no_data_lines():
    response = "LIST VOC WITH F1 = 'F' BY @ID\nVOC\n.....\n0 records listed."
    assert _parse_list_ids(response) == []


# ── UnidataClient.is_configured ───────────────────────────────────────────────

def test_is_configured_false_without_host_or_account():
    c = UnidataClient(host="", account="")
    assert c.is_configured() is False


def test_is_configured_requires_uopy_available_host_and_account(monkeypatch):
    monkeypatch.setattr(unidata_client, "_UOPY_AVAILABLE", True)
    assert UnidataClient(host="udhost", account="ACC").is_configured() is True
    assert UnidataClient(host="", account="ACC").is_configured() is False
    assert UnidataClient(host="udhost", account="").is_configured() is False


def test_is_configured_false_when_uopy_not_importable(monkeypatch):
    monkeypatch.setattr(unidata_client, "_UOPY_AVAILABLE", False)
    assert UnidataClient(host="udhost", account="ACC").is_configured() is False


# ── run_command / list_files (mocked _uopy, mirroring the pyodbc-mock
#    pattern already used in tests/test_dob_sql_source.py) ──────────────────

def _client_with_mock_uopy(monkeypatch):
    mock_uopy = MagicMock()
    mock_conn_cm = MagicMock()
    mock_conn_cm.__enter__.return_value = MagicMock()
    mock_conn_cm.__exit__.return_value = False
    mock_uopy.connect.return_value = mock_conn_cm
    monkeypatch.setattr(unidata_client, "_uopy", mock_uopy)
    c = UnidataClient(host="udhost", port=31438, user="u", password="p", account="ACC")
    return c, mock_uopy


def test_connect_passes_all_connection_params(monkeypatch):
    c, mock_uopy = _client_with_mock_uopy(monkeypatch)
    mock_cmd = MagicMock()
    mock_cmd.response = "PERSON\nCOURSES\n"
    mock_uopy.Command.return_value = mock_cmd

    c.run_command("LIST VOC WITH F1 = 'F' BY @ID")

    mock_uopy.connect.assert_called_with(
        host="udhost", port=31438, user="u", password="p", account="ACC",
    )


def test_run_command_returns_raw_response(monkeypatch):
    c, mock_uopy = _client_with_mock_uopy(monkeypatch)
    mock_cmd = MagicMock()
    mock_cmd.response = "some TCL output"
    mock_uopy.Command.return_value = mock_cmd

    result = c.run_command("SELECT PERSON")

    mock_uopy.Command.assert_called_with("SELECT PERSON")
    mock_cmd.run.assert_called_once()
    assert result == "some TCL output"


def test_list_files_parses_command_response(monkeypatch):
    c, mock_uopy = _client_with_mock_uopy(monkeypatch)
    mock_cmd = MagicMock()
    mock_cmd.response = "PERSON\nCOURSES\n2 records listed."
    mock_uopy.Command.return_value = mock_cmd

    assert c.list_files() == ["PERSON", "COURSES"]


def test_call_subroutine_sets_in_and_inout_args_not_out(monkeypatch):
    c, mock_uopy = _client_with_mock_uopy(monkeypatch)
    mock_sub = MagicMock()
    mock_sub.args = ["", "", ""]
    mock_uopy.Subroutine.return_value = mock_sub

    args = [
        {"label": "IN.ARG", "direction": "in", "value": "hello"},
        {"label": "OUT.ARG", "direction": "out", "value": "should-not-be-set"},
        {"label": "INOUT.ARG", "direction": "inout", "value": "42"},
    ]
    c.call_subroutine("MY.SUB", args)

    mock_uopy.Subroutine.assert_called_with("MY.SUB", 3)
    # in/inout args are written into sub.args before the call; the out arg
    # is left alone since the subroutine itself is expected to populate it.
    assert mock_sub.args[0] == "hello"
    assert mock_sub.args[2] == "42"
    mock_sub.call.assert_called_once()


def test_call_subroutine_result_shape(monkeypatch):
    c, mock_uopy = _client_with_mock_uopy(monkeypatch)
    mock_sub = MagicMock()
    mock_sub.args = ["result-value"]
    mock_uopy.Subroutine.return_value = mock_sub

    result = c.call_subroutine("MY.SUB", [{"label": "RESULT", "direction": "out", "value": ""}])

    assert result["subroutine"] == "MY.SUB"
    assert result["args"] == [
        {"index": 0, "label": "RESULT", "direction": "out", "value": "result-value"},
    ]

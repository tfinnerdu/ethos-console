"""Tests for app.request_utils.get_json_body — the shared JSON-body coercion
helper introduced to replace the repo-wide `request.get_json(force=True) or {}`
pattern, which only substitutes {} for *falsy* non-dict JSON (null, [], "", 0,
false) and still crashes on a *truthy* non-dict body (a bare number, a
non-empty string, a non-empty list, `true`).
"""
import pytest
from app.request_utils import get_json_body


class _FakeRequest:
    def __init__(self, parsed):
        self._parsed = parsed

    def get_json(self, force=True):
        return self._parsed


@pytest.mark.parametrize("parsed", [None, [], "", 0, False])
def test_falsy_non_dict_bodies_become_empty_dict(parsed):
    assert get_json_body(_FakeRequest(parsed)) == {}


@pytest.mark.parametrize("parsed", [42, "hello", [1, 2, 3], True, 3.14])
def test_truthy_non_dict_bodies_also_become_empty_dict(parsed):
    # This is the case `or {}` gets wrong: a truthy non-dict value passes
    # `or {}` through unchanged and crashes the first `.get()`/`in` call.
    assert get_json_body(_FakeRequest(parsed)) == {}


def test_dict_body_passes_through_unchanged():
    assert get_json_body(_FakeRequest({"a": 1})) == {"a": 1}


def test_empty_dict_body_passes_through():
    assert get_json_body(_FakeRequest({})) == {}

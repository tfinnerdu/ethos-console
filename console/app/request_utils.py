"""Shared request-parsing helpers used across app/routes/*.py."""
from __future__ import annotations

from flask import Request


def get_json_body(req: Request) -> dict:
    """Parse the request body as JSON and coerce it to a dict.

    `request.get_json(force=True) or {}` -- the pattern this replaces --
    only substitutes {} when the parsed JSON is falsy (null, [], "", 0,
    false). A JSON body that parses successfully to a *truthy* non-dict
    value (a bare number, a non-empty string, a non-empty list, `true`)
    passes straight through `or {}` unchanged, and every subsequent
    `data.get(...)` / `"key" in data` call on it then raises an unhandled
    AttributeError/TypeError -> 500, leaking a stack trace to the caller.

    This coerces by type, not truthiness, so every non-dict body -- falsy
    or truthy -- becomes {}. A malformed (non-JSON) body still raises
    Flask's own 400 via get_json(force=True), unchanged from today.
    """
    data = req.get_json(force=True)
    return data if isinstance(data, dict) else {}

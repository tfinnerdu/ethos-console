"""Tests for app/help_guide.py (pure rendering pipeline) and the /help route.

Split three ways, same shape as the reference implementation this was ported
from: pure-function unit tests against small synthetic markdown (these are
what would catch a regression like the toc-escaping bug — a real doc rarely
has an '&' in a heading, so an integration-only test suite would miss it),
a few tests against the real doc file to catch structural drift, and
route/HTTP tests.
"""
from pathlib import Path
from unittest.mock import patch

import markdown
import pytest

from app.help_guide import DOC_PATH, _nav_tree, _strip_manual_toc, _unescape_names, render_guide

_MD_EXTENSIONS = ["toc", "tables", "fenced_code", "attr_list", "sane_lists"]
_MD_EXTENSION_CONFIGS = {"toc": {"permalink": False, "anchorlink": False}}


def _toc_tokens(text: str) -> list:
    md = markdown.Markdown(extensions=_MD_EXTENSIONS, extension_configs=_MD_EXTENSION_CONFIGS)
    md.convert(text)
    return md.toc_tokens


# ── _strip_manual_toc ────────────────────────────────────────────────────────

def test_strip_manual_toc_removes_the_toc_block():
    text = (
        "# Title\n\n"
        "## Table of Contents\n\n"
        "1. [Alpha](#alpha)\n"
        "2. [Beta](#beta)\n\n"
        "---\n\n"
        "## Alpha\n\ncontent a\n\n"
        "## Beta\n\ncontent b\n"
    )
    stripped = _strip_manual_toc(text)
    assert "Table of Contents" not in stripped
    assert "[Alpha](#alpha)" not in stripped
    assert "## Alpha" in stripped
    assert "content a" in stripped


def test_strip_manual_toc_no_op_when_absent():
    text = "# Title\n\n## Alpha\n\ncontent\n"
    assert _strip_manual_toc(text) == text


def test_strip_manual_toc_leaves_unrelated_mentions_of_the_phrase_alone():
    # The regex targets the '## Table of Contents' HEADING specifically, not
    # every occurrence of the phrase — a body-text mention elsewhere should
    # survive untouched.
    text = (
        "# Title\n\n## Table of Contents\n\nstuff\n\n## Real\n\n"
        "some body text that happens to mention Table of Contents later\n"
    )
    stripped = _strip_manual_toc(text)
    assert "## Table of Contents" not in stripped
    assert "some body text that happens to mention Table of Contents later" in stripped


# ── _unescape_names ──────────────────────────────────────────────────────────

def test_unescape_names_fixes_ampersand():
    tokens = _toc_tokens("## Navigation & Global UI\n\ntext\n")
    result = _unescape_names(tokens)
    assert result[0]["name"] == "Navigation & Global UI"


def test_unescape_names_recurses_into_children():
    tokens = _toc_tokens("## Parent\n\n### Child & Grandchild\n\ntext\n")
    result = _unescape_names(tokens)
    assert result[0]["children"][0]["name"] == "Child & Grandchild"


def test_unescape_names_leaves_plain_headings_alone():
    tokens = _toc_tokens("## Plain Heading\n\ntext\n")
    result = _unescape_names(tokens)
    assert result[0]["name"] == "Plain Heading"


# ── _nav_tree ─────────────────────────────────────────────────────────────────

def test_nav_tree_unwraps_single_h1():
    tokens = _toc_tokens("# Doc Title\n\n## Tab One\n\ntext\n\n## Tab Two\n\ntext\n")
    nav = _nav_tree(tokens)
    assert [t["name"] for t in nav] == ["Tab One", "Tab Two"]


def test_nav_tree_leaves_multiple_top_level_headings_alone():
    # No single H1 to unwrap — e.g. a doc that starts at H2.
    tokens = _toc_tokens("## Tab One\n\ntext\n\n## Tab Two\n\ntext\n")
    nav = _nav_tree(tokens)
    assert [t["name"] for t in nav] == ["Tab One", "Tab Two"]


def test_nav_tree_preserves_nested_features_under_each_tab():
    tokens = _toc_tokens(
        "# Doc Title\n\n## Migration\n\n### Readiness\n\ntext\n\n### Batches\n\ntext\n"
    )
    nav = _nav_tree(tokens)
    assert nav[0]["name"] == "Migration"
    assert [c["name"] for c in nav[0]["children"]] == ["Readiness", "Batches"]


# ── render_guide (full pipeline, synthetic file) ─────────────────────────────

def test_render_guide_missing_file_returns_none_none(tmp_path):
    content, nav = render_guide(doc_path=tmp_path / "does-not-exist.md")
    assert content is None
    assert nav is None


def test_render_guide_full_pipeline(tmp_path):
    doc = tmp_path / "guide.md"
    doc.write_text(
        "# My App — Guide\n\n"
        "## Table of Contents\n\n1. [Setup & Config](#setup--config)\n\n---\n\n"
        "## Setup & Config\n\nDo the thing.\n\n### Prereqs\n\nNeed a thing first.\n"
    )
    content, nav = render_guide(doc_path=doc)
    assert content is not None
    assert "Table of Contents" not in content
    assert "<h2" in content and 'id="setup-config"' in content
    assert "&amp;amp;" not in content
    assert nav[0]["name"] == "Setup & Config"
    assert nav[0]["children"][0]["name"] == "Prereqs"


# ── Integration: the real doc ────────────────────────────────────────────────

def test_real_doc_exists():
    assert DOC_PATH.exists(), f"expected the guide at {DOC_PATH}"


def test_real_doc_renders_without_error():
    content, nav = render_guide()
    assert content is not None
    assert nav is not None
    assert len(nav) > 0


def test_real_doc_covers_every_tab():
    _, nav = render_guide()
    names = {tok["name"] for tok in nav}
    for expected in ("Overview", "Bus Monitor", "Replay", "GraphQL", "Health",
                     "DOB Repair", "DoaneEdgeGate", "Configuration Reference"):
        assert any(expected in n for n in names), f"missing tab-level section: {expected}"


def test_real_doc_has_no_double_escaped_ampersands():
    content, _ = render_guide()
    assert "&amp;amp;" not in content


# ── Route ─────────────────────────────────────────────────────────────────────

def test_help_route_200(client):
    r = client.get("/help")
    assert r.status_code == 200


def test_help_route_renders_sidebar_and_content(client):
    html = client.get("/help").get_data(as_text=True)
    assert 'id="helpNav"' in html
    assert 'id="helpContent"' in html
    assert "DoaneEdgeGate" in html


def test_help_route_404_when_doc_missing(client):
    with patch("app.routes.main.render_guide", return_value=(None, None)):
        r = client.get("/help")
    assert r.status_code == 404


def test_help_icon_present_and_positioned_before_logout(client):
    html = client.get("/").get_data(as_text=True)
    help_idx = html.find('href="/help"')
    logout_idx = html.find('href="/logout"')
    assert help_idx != -1, "help icon link not found in navbar"
    assert logout_idx != -1, "logout link not found in navbar"
    assert help_idx < logout_idx, "help icon should sit before (to the left of) Logout"
    assert "bi-question-circle" in html

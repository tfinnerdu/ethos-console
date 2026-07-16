"""Renders console/docs/console-user-guide.md as the in-app Help & User Guide.

Single source of truth stays the markdown file — this only renders it, with a
per-tab/per-feature sidebar nav built from the file's real headers, so the
nav can never drift out of sync with the content the way a hand-maintained
table of contents can. Re-rendered on every request rather than cached —
this is low-traffic internal tooling, and it means a doc edit shows up
without a redeploy.

Ported from the same pattern already shipped in the DoaneEdgeGate/Salesforce
tooling console; the four functions below are generic and were copied
essentially unchanged.
"""
import html
import logging
import re
from pathlib import Path

import markdown

log = logging.getLogger(__name__)


# Lives INSIDE console/ (not the repo-root docs/ where DoaneEdgeGate's
# runbooks live) deliberately: every Doane service's Dockerfile build
# context is that service's own directory (confirmed against DLM/PII/OCR/
# Follett's real Dockerfiles — none of them reach outside their own folder),
# so anything read at runtime, like this one, has to physically live inside
# console/ or it silently isn't in the built image. Every other doc in this
# repo is pure human reference with no runtime reader, which is why they
# stay at the repo-root docs/ instead — this file is the one exception.
DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "console-user-guide.md"

_MD_EXTENSIONS = ["toc", "tables", "fenced_code", "attr_list", "sane_lists"]
_MD_EXTENSION_CONFIGS = {"toc": {"permalink": False, "anchorlink": False}}


def _strip_manual_toc(text: str) -> str:
    """Drop the hand-maintained '## Table of Contents' section before
    rendering — the page builds its own sidebar nav from the real headers, so
    keeping a second, separately-maintained TOC in the body would just be a
    second thing that can drift out of sync."""
    return re.sub(r"\n## Table of Contents\n.*?(?=\n## )", "\n", text,
                  count=1, flags=re.DOTALL)


def _unescape_names(tokens: list) -> list:
    """The toc extension's token 'name' is pre-escaped HTML (meant for its
    own toc_tokens-to-HTML renderer, which we don't use here) — e.g. a
    heading 'Velocity & ETA' comes through as 'Velocity &amp; ETA'. Decode it
    back to plain text so Jinja's autoescape (which assumes plain text)
    doesn't double-escape it on the page."""
    for tok in tokens:
        tok["name"] = html.unescape(tok["name"])
        _unescape_names(tok["children"])
    return tokens


def _nav_tree(toc_tokens: list) -> list:
    """Unwrap the single document-title H1 so the sidebar starts at the
    per-tab (H2) level; each tab's H3/H4 features are already nested
    correctly by the markdown toc extension."""
    toc_tokens = _unescape_names(toc_tokens)
    if len(toc_tokens) == 1 and toc_tokens[0]["level"] == 1:
        return toc_tokens[0]["children"]
    return toc_tokens


def render_guide(doc_path: Path = DOC_PATH):
    """Return (content_html, nav_tree) for the rendered user guide, or
    (None, None) if the source file is missing."""
    if not doc_path.exists():
        return None, None
    text = _strip_manual_toc(doc_path.read_text())
    md = markdown.Markdown(extensions=_MD_EXTENSIONS,
                           extension_configs=_MD_EXTENSION_CONFIGS)
    content = md.convert(text)
    return content, _nav_tree(md.toc_tokens)

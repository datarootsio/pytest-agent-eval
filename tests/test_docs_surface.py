"""The docs nav, llms.txt, and llms-full build must stay in sync with the pages on disk."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from build_llms_full import build_llms_full, nav_page_paths  # noqa: E402


def _all_nav_paths() -> list[str]:
    def walk(nav):
        for entry in nav:
            for value in entry.values():
                if isinstance(value, str):
                    yield value
                else:
                    yield from walk(value)

    config = tomllib.loads((REPO_ROOT / "zensical.toml").read_text())
    return list(walk(config["project"]["nav"]))


def test_every_nav_entry_points_at_an_existing_page():
    for path in _all_nav_paths():
        assert (DOCS_DIR / path).is_file(), f"nav references missing page {path}"


def test_every_docs_page_is_in_the_nav():
    nav = set(_all_nav_paths())
    pages = {str(p.relative_to(DOCS_DIR)) for p in DOCS_DIR.rglob("*.md") if "superpowers" not in p.parts}
    assert pages == nav


def test_llms_txt_links_resolve_to_nav_pages():
    text = (DOCS_DIR / "llms.txt").read_text()
    doc_links = re.findall(r"https://datarootsio\.github\.io/pytest-agent-eval/latest/([a-z-]+(?:/[a-z-]+)*)/\)", text)
    nav = set(_all_nav_paths())
    for slug in doc_links:
        candidates = {f"{slug}.md", f"{slug}/index.md"}
        assert candidates & nav, f"llms.txt links to {slug!r}, which is not a nav page"


def test_llms_full_contains_every_nav_page_h1():
    full = build_llms_full()
    pages = nav_page_paths()
    assert pages, "nav walk returned no pages"
    assert not any(p.startswith("api-reference/") for p in pages)
    for page in pages:
        first_heading = next(
            (line for line in (DOCS_DIR / page).read_text().splitlines() if line.startswith("# ")), None
        )
        assert first_heading is not None, f"{page} has no H1"
        assert first_heading in full
        assert f"<!-- source: {page} -->" in full

"""Concatenate the documentation into a single llms-full.txt, following nav order.

Generated at docs-build time (never committed), so it cannot drift from the
pages it is built from. The api-reference section is skipped: it is generated
from docstrings and mostly duplicates the source.

Usage::

    python scripts/build_llms_full.py [-o OUTPUT]
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"

_HEADER = (
    "# pytest-agent-eval — full documentation\n\n"
    "> Concatenated from the official documentation at "
    "https://datarootsio.github.io/pytest-agent-eval/latest/ — one page per "
    "'source:' comment below.\n"
)


def _walk_nav(nav: list[dict[str, Any]]) -> list[str]:
    pages: list[str] = []
    for entry in nav:
        for value in entry.values():
            if isinstance(value, str):
                pages.append(value)
            else:
                pages.extend(_walk_nav(value))
    return pages


def nav_page_paths() -> list[str]:
    """Return the docs pages in sidebar order, skipping the api-reference section."""
    config = tomllib.loads((REPO_ROOT / "zensical.toml").read_text())
    return [p for p in _walk_nav(config["project"]["nav"]) if not p.startswith("api-reference/")]


def build_llms_full() -> str:
    """Concatenate every nav page into one markdown document."""
    parts = [_HEADER]
    parts.extend(f"\n\n<!-- source: {page} -->\n\n{(DOCS_DIR / page).read_text()}" for page in nav_page_paths())
    return "".join(parts)


def main() -> None:
    """Write the concatenated documentation to the requested output path."""
    parser = argparse.ArgumentParser(description="Build llms-full.txt from the docs nav")
    parser.add_argument("-o", "--output", type=Path, default=DOCS_DIR / "llms-full.txt")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_llms_full())
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

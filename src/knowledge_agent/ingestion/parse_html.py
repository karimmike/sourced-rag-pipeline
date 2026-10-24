"""Turn an HTML Document into sections: heading path, text, slug and citation link."""

import re
from collections import Counter
from urllib.parse import quote

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from pydantic import BaseModel, ConfigDict

from knowledge_agent.connectors.base import Document

# Main content of an Erasmus+ guide page; header, menus and footer are outside it.
CONTENT_SELECTOR = "div.eac-body"
# ADR 001: split on h2/h3; h4 stays inside the section as a Markdown heading.
SPLIT_LEVELS = {"h2": 0, "h3": 1}
SUFFIX_WORDS = 4


class Section(BaseModel):
    """One h2/h3 section of a page; footnotes are kept apart so the chunker can place them."""

    model_config = ConfigDict(frozen=True)

    heading_path: tuple[str, ...]
    text: str
    # Stable id part built from the headings (the pages have no heading ids).
    slug: str
    # Text-fragment link ("#:~:text=...") that scrolls a browser to the heading.
    fragment: str
    # Footnotes referenced in text, number -> text. Treat as read-only.
    footnotes: dict[str, str]


def parse_html(document: Document) -> list[Section]:
    """Split a guide page into its h2/h3 sections, in page order."""
    body = BeautifulSoup(document.content, "lxml").select_one(CONTENT_SELECTOR)
    if body is None:
        raise ValueError(f"{document.id}: {CONTENT_SELECTOR} not found")
    for tag in body.find_all(["script", "style", "nav"]):
        tag.decompose()
    footnotes = _extract_footnotes(body)
    counts = Counter(_text(h) for h in body.find_all(list(SPLIT_LEVELS)))
    duplicated = {heading for heading, n in counts.items() if n > 1}

    # Group the body's children under the h2/h3 that precedes them.
    groups: list[tuple[Tag | None, list]] = [(None, [])]
    for child in body.children:
        if isinstance(child, Tag) and child.name in SPLIT_LEVELS:
            groups.append((child, []))
        else:
            groups[-1][1].append(child)

    sections: list[Section] = []
    path: list[str] = []
    slugs: Counter[str] = Counter()
    for heading, nodes in groups:
        if heading is not None:
            path = path[: SPLIT_LEVELS[heading.name]] + [_text(heading)]
        # Before rendering: rendering rewrites the footnote markers the suffix reads.
        fragment = _fragment(heading, duplicated)
        refs: list[str] = []
        blocks = [block for node in nodes if (block := _render(node, refs))]
        if not blocks:
            continue
        # dict.fromkeys drops repeated references but keeps their order.
        notes = dict(footnotes[ref] for ref in dict.fromkeys(refs) if ref in footnotes)
        slug = "/".join(_slugify(h) for h in path) or "intro"
        slugs[slug] += 1
        if slugs[slug] > 1:
            slug = f"{slug}-{slugs[slug]}"
        sections.append(
            Section(
                heading_path=(document.title, *path),
                text="\n\n".join(blocks),
                slug=slug,
                fragment=fragment,
                footnotes=notes,
            )
        )
    return sections


def _extract_footnotes(body: Tag) -> dict[str, tuple[str, str]]:
    footnotes = {}
    for item in body.select("ol.footnotes li.footnote"):
        for back_link in item.select('a[href^="#footnoteref"]'):
            back_link.decompose()
        footnotes[item["id"]] = (item["value"], _text(item))
    for tag in body.select("ol.footnotes, #eac-footnote-label"):
        tag.decompose()
    return footnotes


def _render(node, refs: list[str]) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return " ".join(node.split())
    for ref in node.select("a.eac-see-footnote"):
        refs.append(ref["href"].removeprefix("#"))
        ref.sup.replace_with(f"[{ref.sup.get_text(strip=True)}]")
        ref.unwrap()
    if node.name == "table":
        return _table_to_markdown(node)
    if node.name in ("ul", "ol"):
        return "\n".join("- " + _text(li) for li in node.find_all("li", recursive=False))
    if node.name == "h4":
        return "#### " + _text(node)
    return _text(node)


def _table_to_markdown(table: Tag) -> str:
    rows = [
        [_text(cell).replace("|", r"\|") for cell in tr.find_all(["th", "td"])]
        for tr in table.find_all("tr")
    ]
    rows = [row for row in rows if row]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    lines = [" | ".join(row + [""] * (width - len(row))) for row in rows]
    lines.insert(1, " | ".join(["---"] * width))
    return "\n".join(f"| {line} |" for line in lines)


def _fragment(heading: Tag | None, duplicated: set[str]) -> str:
    if heading is None:
        return ""
    text = _text(heading)
    fragment = "#:~:text=" + _encode(text)
    after = heading.find_next_sibling()
    if text in duplicated and after is not None:
        fragment += ",-" + _encode(" ".join(_text(after).split()[:SUFFIX_WORDS]))
    return fragment


def _text(tag: Tag) -> str:
    for block in tag.find_all(["p", "li", "div", "br"]):
        block.insert_after(" ")
    return " ".join(tag.get_text().split())


def _encode(text: str) -> str:
    # In text fragments "-", "," and "&" are syntax, so they must be percent-encoded.
    return quote(text, safe="").replace("-", "%2D")


def _slugify(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")

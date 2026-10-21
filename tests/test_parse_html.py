from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge_agent.connectors.base import Document
from knowledge_agent.ingestion.parse_html import parse_html

FIXTURE = Path(__file__).parent / "fixtures" / "erasmus_guide" / "section.html"
TITLE = "Mobility projects for higher education students and staff"
TRAVEL_PATH = (
    TITLE,
    "A) Funding rules applicable to all mobility activities in higher education",
    "Budget category - Travel support",
)


def make_document(html: str) -> Document:
    return Document(
        id="doc-1",
        title=TITLE,
        source="test",
        content=html,
        uri="https://example.org/page",
        content_type="text/html",
        fetched_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
    )


@pytest.fixture
def sections():
    return parse_html(make_document(FIXTURE.read_text(encoding="utf-8")))


def test_heading_paths_skip_empty_sections(sections):
    assert [s.heading_path for s in sections] == [(TITLE,), TRAVEL_PATH]


def test_boilerplate_is_removed(sections):
    text = "\n".join(s.text for s in sections)

    assert "Select your language" not in text
    assert "Share this page" not in text
    assert "↩" not in text


def test_h4_stays_inside_its_section(sections):
    assert "#### Amount" in sections[1].text


def test_table_becomes_markdown(sections):
    assert (
        "| Travel distance | Green travel | Non-Green travel |\n"
        "| --- | --- | --- |\n"
        "| 10 - 99 km | 56 EUR | 28 EUR |"
    ) in sections[1].text


def test_footnote_is_attached_to_the_section_that_references_it(sections):
    intro, travel = sections

    assert "the venue of the activity[17] by using" in travel.text
    assert travel.text.endswith(
        "[17] For example, if a person from Madrid (Spain) is taking part in an activity "
        "in Rome (Italy), the applicant will calculate the distance from Madrid to Rome "
        "(1365,28 KM) and then select the applicable travel distance band "
        "(i.e. between 500 and 1999 km)."
    )
    assert "Madrid" not in intro.text


def test_slug_and_fragment(sections):
    intro, travel = sections

    assert intro.slug == "intro"
    assert intro.fragment == ""
    assert travel.slug == (
        "a-funding-rules-applicable-to-all-mobility-activities-in-higher-education"
        "/budget-category-travel-support"
    )
    assert travel.fragment == "#:~:text=Budget%20category%20%2D%20Travel%20support"


def test_duplicate_headings_get_distinct_slugs_and_fragments():
    html = """<div class="eac-body">
    <h2>Part one</h2><h3>Who can apply?</h3><p>Any eligible participating organisation can apply.</p>
    <h2>Part two</h2><h3>Who can apply?</h3><p>Organisations with the following accreditation.</p>
    <h3>Who can apply?</h3><p>Only accredited consortia can apply.</p>
    </div>"""

    sections = parse_html(make_document(html))

    assert [s.slug for s in sections] == [
        "part-one/who-can-apply",
        "part-two/who-can-apply",
        "part-two/who-can-apply-2",
    ]
    assert sections[0].fragment == (
        "#:~:text=Who%20can%20apply%3F,-Any%20eligible%20participating%20organisation"
    )
    assert len({s.fragment for s in sections}) == 3

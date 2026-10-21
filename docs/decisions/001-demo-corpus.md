# 001: Demo corpus: Erasmus+ Programme Guide

- Date: 2026-10-12
- Status: Accepted (2026-10-14)

## Decision
The HTML version of the Erasmus+ Programme Guide 2026 (Version 1, 12.11.2025) is the MVP
source. The PDF is the official reference: if HTML and PDF disagree, the PDF prevails.
A PDF source will be added in a later step (this also covers page-number citations).
Record the PDF URL and edition as metadata on every chunk.
Commit the download script only, never the PDF or HTML snapshots.

## 1. Edition
**Verified**
- Latest edition: Erasmus+ Programme Guide 2026, Version 1, dated 12.11.2025.
  It is an integral part of the 2026 Erasmus+ Call for Proposals.
- Published on erasmus-plus.ec.europa.eu as HTML pages and as PDF in 24 languages.
  If language versions conflict, the English version prevails.

**Assumed**
- A 2027 edition will be published around November 2026, based on past yearly cycles.
  This is why every chunk must carry the edition.

## 2. Formats
**Verified**
- HTML: about one page per section under `/programme-guide/part-a…d/...`, with real
  `h1`-`h4` headings. Example: the higher-education mobility page has sections for
  Eligibility criteria, When to apply and Award criteria (with points).
- HTML tables are mixed: the higher-education page has 5 real `<table>` elements
  (e.g. travel bands, 10-99 km: 56 EUR green / 28 EUR non-green). Some amounts
  (e.g. "900 EUR per month") appear as plain text, not in a table.
- HTML pages have no version stamp. Only the landing page shows "Version 1 of 12.11.2025".
- The "download the full guide" link on HTML pages points to the 2024 PDF (outdated).
- PDF: `programme-guide-2026_en.pdf`, 3.3 MB, 456 pages, table of contents with page
  numbers, no bookmarks.
- In a pdftotext (layout mode) extraction, multi-column funding tables came out interleaved.

**Assumed**
- The PDF has no structure tags. This was checked by a byte search for `/StructTreeRoot`,
  which can miss compressed objects.
- PDF and HTML pages may be updated in place without a URL change. A checksum is needed.

## 3. Reuse terms
**Verified**
- European Commission content is licensed under CC BY 4.0 (Commission Decision 2011/833/EU).
  Reuse is allowed if appropriate credit is given and changes are indicated.
  Logos, trade marks and third-party content are excluded.
- robots.txt does not disallow `/programme-guide/` or `/sites/default/files/`.

**Assumed**
- The erasmus-plus site's "Legal notice" link applies the same Commission policy.
  The policy was read on commission.europa.eu, not on a separate erasmus-plus page.

**Attribution to use**
> Source: European Commission, *Erasmus+ Programme Guide 2026*, Version 1 (12.11.2025),
> © European Union, CC BY 4.0. Content extracted and chunked.

## 4. Guide structure and MVP sections
**Verified (from the PDF table of contents)**
- Part A: General information (p. 4): objectives, priorities, structure, budget,
  implementation, who can participate.
- Part B: Actions (p. 37): KA1 Learning mobility (higher education, VET, schools,
  adults, youth, sport); KA2 Cooperation (p. 224); KA3 Policy development (p. 364);
  Jean Monnet actions.
- Part C: Information for applicants (p. 413): registration, eligibility checks,
  financial conditions, submission.
- Part D: Glossary (p. 443), followed by a short annex.

**MVP sections**
1. Part A: "Who can participate", including eligible countries (general rules, country groups).
2. KA1: Mobility projects for higher education students and staff (monthly grants,
   travel bands, deadline 19 February 12:00 Brussels time).
3. KA2: Cooperation partnerships and small-scale partnerships (lump sums;
   deadline 5 March 12:00 Brussels time; optional 1 October round, set by each
   National Agency).
4. Optional: Part C financial conditions (cross-cutting rules).

**Verified**
- The 1 October KA2 round is optional: each National Agency decides whether to
  organise it and announces it on its website.

## 5. Format and parsing approach
**Approach:** HTML, parsed with BeautifulSoup4 (MIT) and lxml (BSD), split on
`h2`/`h3`, with `<table>` elements converted to Markdown. Alternative: trafilatura
(Apache-2.0). Chunk metadata: source URL + section anchor, heading path, edition, PDF URL.

**Pros:** real headings, one citable URL per section, no PDF layout problems, small downloads.

**Cons:** about 60 page fetches (must be polite: slow, cached, contact user agent);
no page numbers; mixed tables (plain-text amounts need a test); edition must be
recorded from the landing page.

**If page numbers are needed later:** map sections to PDF pages with pdfplumber (MIT)
or pypdf (BSD). Docling (MIT) handles tables better but has heavy dependencies.
Do not use PyMuPDF (AGPL). Poppler's pdftotext (GPL) was used only for inspection.

## 6. Known HTML vs PDF differences
**Verified (checked 2026-10-14 on the 3 MVP sections; the PDF prevails)**
- KA1 higher education, country groups: the HTML also lists "third countries not
  associated from Region 13" under Group 2; the PDF lists Region 13 only under Group 1.
- KA1 higher education: the HTML says the student grant covers "travel and subsistence";
  the PDF says "subsistence" (travel is a separate budget category).
- KA2 cooperation partnerships: the HTML uses the old agency name "European Education,
  Audiovisual and Cultural Executive Agency"; the PDF says "European Education and
  Culture Executive Agency (EACEA)".
- Part A, footnote on natural persons: the HTML says "not eligible to directly apply",
  the PDF "not eligible to apply".
- The "download the full guide" link on HTML pages points to the 2024 PDF.

**Content only in the PDF**
- Part A, footnote 51: list of 18 migration-priority Sub-Saharan countries.
- KA2 cooperation partnerships, footnote 239: informal groups of young people are not
  eligible (neither as applicants nor as partners). Only the small-scale page has it.
- KA2 footnote markers 244/245 (cooperation) and 253 (small-scale): the markers are in
  the PDF, but their text was not found in the extraction. Not verified.

**Chunking consequence**
- HTML footnotes sit at the bottom of each page and are numbered per page. They must be
  attached to the chunk that references them, not stored as a separate chunk.

## Sources
- [Erasmus+ Programme Guide landing page](https://erasmus-plus.ec.europa.eu/programme-guide/erasmusplus-programme-guide)
- [Programme Guide 2026 document page](https://erasmus-plus.ec.europa.eu/document/erasmus-programme-guide-2026)
- [2026 PDF (EN)](https://erasmus-plus.ec.europa.eu/sites/default/files/2025-11/programme-guide-2026_en.pdf)
- [HTML: Higher education mobility](https://erasmus-plus.ec.europa.eu/programme-guide/part-b/key-action-1/higher-education-mobility-projects)
- [European Commission legal notice (CC BY 4.0)](https://commission.europa.eu/legal-notice_en)

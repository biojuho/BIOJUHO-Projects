from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import server


def _entry(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_parse_arxiv_entry_dedupes_categories_and_extracts_pdf():
    entry = _entry(
        """
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
          <id>http://arxiv.org/abs/2401.12345</id>
          <title> A paper\n title </title>
          <summary> Abstract\n text </summary>
          <published>2026-05-01T00:00:00Z</published>
          <author><name>Alice</name></author>
          <arxiv:primary_category term="cs.AI" />
          <category term="cs.AI" />
          <category term="cs.CL" />
          <link title="pdf" href="https://arxiv.org/pdf/2401.12345" />
        </entry>
        """
    )

    parsed = server._parse_arxiv_entry(entry)

    assert parsed["arxiv_id"] == "2401.12345"
    assert parsed["authors"] == ["Alice"]
    assert parsed["categories"] == ["cs.AI", "cs.CL"]
    assert parsed["pdf_url"].endswith("2401.12345")


def test_grant_payload_and_result_normalization():
    payload = server._grant_search_payload("cancer", "NIH", 5)
    result = server._grant_result(
        {
            "oppTitle": "Grant",
            "agencyCode": "NIH",
            "closeDateStr": "2026-06-01",
            "estimatedFunding": "$100",
            "synopsis": "x" * 600,
            "oppNumber": "abc",
        }
    )

    assert payload["keyword"] == "cancer"
    assert payload["agencies"] == "NIH"
    assert result["title"] == "Grant"
    assert len(result["description"]) == 500
    assert result["url"].endswith("/abc")


def test_research_keywords_prefers_repeated_bigrams():
    papers = [
        {"title": "Graph neural discovery", "abstract": "Graph neural discovery improves science."},
        {"title": "Graph neural models", "abstract": "Graph neural methods support discovery."},
        {"title": "Graph neural systems", "abstract": "Graph neural evidence for discovery."},
    ]

    keywords = server._research_keywords(papers)

    assert keywords[0]["term"] == "graph neural"
    assert keywords[0]["count"] >= 3


def test_filter_recent_papers_includes_unparseable_dates():
    recent = _entry(
        """
        <entry xmlns="http://www.w3.org/2005/Atom">
          <id>id</id><title>T</title><summary>S</summary><published>not-a-date</published>
        </entry>
        """
    )

    papers = server._filter_recent_papers([recent], datetime(2026, 1, 1, tzinfo=UTC))

    assert len(papers) == 1
    assert papers[0]["title"] == "T"

"""Quick scraping diagnostic test."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

import asyncio

import httpx


pytestmark = pytest.mark.skip(reason="Diagnostic network/task-scheduler probe; run this file as a script when needed.")


async def test_scrape():
    results = {}

    # Test 1: getdaytrends.com connectivity
    print("=" * 50)
    print("Test 1: getdaytrends.com")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://getdaytrends.com/korea/",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15.0,
            )
            print(f"  Status: {resp.status_code}")
            print(f"  Content length: {len(resp.text)} chars")
            if "table" in resp.text.lower():
                print("  Table found: YES")
            else:
                print("  Table found: NO (possible block or site change)")
            results["getdaytrends"] = resp.status_code
    except Exception as e:
        print(f"  ERROR: {e}")
        results["getdaytrends"] = str(e)

    # Test 2: Google Trends RSS
    print("\nTest 2: Google Trends RSS")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://trends.google.com/trending/rss?geo=KR",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10.0,
            )
            print(f"  Status: {resp.status_code}")
            print(f"  Content length: {len(resp.text)} chars")
            if "<item>" in resp.text:
                import xml.etree.ElementTree as ET

                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                print(f"  Items found: {len(items)}")
                for item in items[:3]:
                    title = item.find("title")
                    if title is not None:
                        print(f"    - {title.text}")
            results["google_trends"] = resp.status_code
    except Exception as e:
        print(f"  ERROR: {e}")
        results["google_trends"] = str(e)

    # Test 3: Full scraper module test
    print("\nTest 3: Full scraper module")
    try:
        from scraper import fetch_getdaytrends, fetch_google_trends_rss

        trends = fetch_getdaytrends("korea", 5)
        print(f"  fetch_getdaytrends: {len(trends)} trends")
        for t in trends[:3]:
            print(f"    - {t.name} (vol: {t.volume})")
        results["scraper_gdt"] = len(trends)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["scraper_gdt"] = str(e)

    try:
        trends2 = fetch_google_trends_rss("korea", 5)
        print(f"  fetch_google_trends_rss: {len(trends2)} trends")
        for t in trends2[:3]:
            print(f"    - {t.name} (vol: {t.volume})")
        results["scraper_gtr"] = len(trends2)
    except Exception as e:
        print(f"  ERROR: {e}")
        results["scraper_gtr"] = str(e)

    # Test 4: Task Scheduler status
    print("\nTest 4: Windows Task Scheduler")
    import subprocess

    try:
        out = subprocess.run(
            ["schtasks", "/query", "/tn", "GetDayTrends", "/fo", "LIST"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print(f"  {out.stdout.strip()}")
        if out.returncode != 0:
            print(f"  Error: {out.stderr.strip()}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 50)
    print("SUMMARY:", results)


if __name__ == "__main__":
    asyncio.run(test_scrape())

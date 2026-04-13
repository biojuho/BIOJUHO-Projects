"""One-off cleanup for the 2026-04-13 false-success duplicate burst.

Six manual reruns and one schedule run published the morning brief multiple times.
Plus the next morning's brief (04-14 KST) was also created with date.today() == 04-13 UTC.

Action:
- Rename the most recent set (22:33-22:37 UTC = the 04-14 KST morning brief) to "2026-04-14"
- Keep the 03:00 UTC set (the last manual rerun) as the canonical 04-13 morning brief
- Archive everything else
"""
import os
from collections import defaultdict
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()
n = Client(auth=os.environ["NOTION_API_KEY"])
DS_ID = "27a87180-0f22-4b46-9569-50dacdc58794"

KEEP_AS_0414 = {
    "34190544-c198-81bb-bcde-f97798da4d4c",  # AI_Deep   22:37
    "34190544-c198-814b-b0a0-fc6037431234",  # Global_Affairs 22:36
    "34190544-c198-81f8-a463-de472847493b",  # Crypto    22:35
    "34190544-c198-81ed-8d66-c210080effa8",  # Economy_Global 22:34
    "34190544-c198-81dd-ac0b-d68b42ea507b",  # Economy_KR 22:34
    "34190544-c198-8148-8d94-f87c760110cb",  # Tech      22:33
}
KEEP_AS_0413 = {
    "34190544-c198-81af-9fdb-f2ec5a03e52e",  # AI_Deep   03:00
    "34190544-c198-81cd-a8c3-ee143b0eacd8",  # Global_Affairs 02:59
    "34190544-c198-810b-8e56-de86d8df3923",  # Crypto    02:59
    "34190544-c198-8109-bf76-dfbd76a52100",  # Economy_Global 02:58
    "34190544-c198-818d-bfc4-fc958864b570",  # Economy_KR 02:57
    "34190544-c198-81e5-9a3f-eee169494155",  # Tech      02:56
}
SKIP_PAGES = {
    "34090544-c198-819d-a499-e39fe51af84d",  # Tech Manual Brief — unrelated page
}


def normalize(pid: str) -> str:
    return pid.replace("-", "")


def main() -> None:
    res = n.data_sources.query(
        data_source_id=DS_ID,
        filter={"property": "Name", "title": {"contains": "2026-04-13"}},
        page_size=100,
    )
    pages = res["results"]

    keep_0414 = {normalize(p) for p in KEEP_AS_0414}
    keep_0413 = {normalize(p) for p in KEEP_AS_0413}
    skip = {normalize(p) for p in SKIP_PAGES}

    by_category: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        pid = normalize(p["id"])
        title = "".join(t.get("plain_text", "") for t in p["properties"]["Name"]["title"])
        if pid in skip:
            continue
        cat = title.split("]")[0].lstrip("[") if title.startswith("[") else "?"
        by_category[cat].append({"id": p["id"], "pid": pid, "title": title, "created": p["created_time"]})

    renamed = archived = kept = 0
    for cat, items in sorted(by_category.items()):
        print(f"\n=== {cat} ({len(items)} pages) ===")
        for item in sorted(items, key=lambda x: x["created"], reverse=True):
            pid = item["pid"]
            if pid in keep_0414:
                new_title = item["title"].replace("2026-04-13", "2026-04-14")
                n.pages.update(
                    page_id=item["id"],
                    properties={
                        "Name": {"title": [{"text": {"content": new_title}}]}
                    },
                )
                print(f"  RENAME -> 04-14  {item['created']}  {item['id']}")
                renamed += 1
            elif pid in keep_0413:
                print(f"  KEEP   04-13     {item['created']}  {item['id']}")
                kept += 1
            else:
                n.pages.update(page_id=item["id"], archived=True)
                print(f"  ARCHIVE          {item['created']}  {item['id']}")
                archived += 1

    print(f"\nTotal: renamed={renamed}  kept={kept}  archived={archived}")


if __name__ == "__main__":
    main()

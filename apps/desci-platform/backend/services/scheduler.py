"""
BioLinker - Notice scheduler.

The scheduler remains importable even when optional runtime integrations such
as APScheduler or crawler dependencies are not installed.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    APSCHEDULER_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in lean smoke environments
    APSCHEDULER_AVAILABLE = False

    class BackgroundScheduler:  # type: ignore[override]
        def __init__(self):
            self.running = False

        def add_job(self, *args, **kwargs):  # noqa: ANN002, ANN003
            return None

        def start(self):
            self.running = True

        def shutdown(self):
            self.running = False

    class CronTrigger:  # type: ignore[override]
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            pass


def _load_getter(module_name: str, getter_name: str):
    try:
        module = __import__(f".{module_name}", globals(), locals(), [getter_name], 1)
    except ImportError:
        module = __import__(module_name, globals(), locals(), [getter_name], 0)
    return getattr(module, getter_name)


def get_kddf_crawler():
    return _load_getter("kddf_crawler", "get_kddf_crawler")()


def get_ntis_crawler():
    return _load_getter("ntis_crawler", "get_ntis_crawler")()


def get_vector_store():
    return _load_getter("vector_store", "get_vector_store")()


class NoticeScheduler:
    """Collect and cache government RFP notices."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.notices_file = os.path.join(data_dir, "notices.json")
        self.last_run_file = os.path.join(data_dir, "last_run.txt")
        os.makedirs(data_dir, exist_ok=True)

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.run_collection_job,
            CronTrigger(hour=2, minute=0),
            id="daily_notice_collection",
            replace_existing=True,
        )

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            if APSCHEDULER_AVAILABLE:
                print("[Scheduler] Started background scheduler (daily 02:00)")
            else:
                print("[Scheduler] APScheduler not installed; using no-op scheduler")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("[Scheduler] Stopped background scheduler")

    def run_collection_job(self):
        print("[Scheduler] Triggering scheduled collection")
        try:
            asyncio.run(self.collect_all_notices())
        except Exception as exc:  # noqa: BLE001
            print(f"[Scheduler] Job failed: {exc}")

    async def collect_all_notices(self) -> list[dict]:
        all_notices: list[dict] = []

        print(f"[Scheduler] Starting collection at {datetime.now().isoformat()}")

        try:
            kddf = get_kddf_crawler()
            kddf_notices = await kddf.fetch_notice_list()
            all_notices.extend(kddf_notices)
            print(f"[KDDF] Collected {len(kddf_notices)} notices")
        except Exception as exc:  # noqa: BLE001
            print(f"[KDDF] Error: {exc}")

        ntis = None
        try:
            ntis = get_ntis_crawler()
            ntis_notices = await ntis.fetch_notice_list("바이오")
            all_notices.extend(ntis_notices)
            print(f"[NTIS] Collected {len(ntis_notices)} notices")
        except Exception as exc:  # noqa: BLE001
            print(f"[NTIS] Error: {exc}")

        if ntis is not None:
            for keyword in ["신약", "제약", "AI 신약"]:
                try:
                    extra = await ntis.fetch_notice_list(keyword)
                    existing_urls = {notice["url"] for notice in all_notices if notice.get("url")}
                    new_notices = [notice for notice in extra if notice.get("url") not in existing_urls]
                    all_notices.extend(new_notices)
                    print(f"[NTIS:{keyword}] Added {len(new_notices)} new notices")
                except Exception as exc:  # noqa: BLE001
                    print(f"[NTIS:{keyword}] Error: {exc}")

        new_notices = self._save_notices(all_notices)
        self._update_last_run()

        try:
            vector_store = get_vector_store()
        except Exception as exc:  # noqa: BLE001
            print(f"[Scheduler] Vector store unavailable: {exc}")
            vector_store = None

        if vector_store is not None and new_notices:
            print(f"[Scheduler] Indexing {len(new_notices)} new notices")
            for notice in new_notices:
                try:
                    rfp = None
                    source = notice.get("source")
                    url = notice.get("url")
                    if not url:
                        continue

                    if source == "KDDF":
                        rfp = await get_kddf_crawler().fetch_notice_detail(url)
                    elif source == "NTIS":
                        rfp = await get_ntis_crawler().fetch_notice_detail(url)

                    if rfp:
                        vector_store.add_notice(rfp)
                        print(f"[Scheduler] Indexed: {getattr(rfp, 'title', '')[:30]}")
                    await asyncio.sleep(1)
                except Exception as exc:  # noqa: BLE001
                    print(f"[Scheduler] Failed to index {notice.get('url')}: {exc}")

        print(f"[Scheduler] Total collected: {len(all_notices)}")
        return all_notices

    def _save_notices(self, notices: list[dict]) -> list[dict]:
        existing = self._load_notices()
        existing_urls = {notice["url"] for notice in existing if notice.get("url")}

        new_items: list[dict] = []
        for notice in notices:
            if notice.get("url") and notice["url"] not in existing_urls:
                notice["collected_at"] = datetime.now().isoformat()
                notice["is_new"] = True
                existing.append(notice)
                new_items.append(notice)

        if new_items:
            with open(self.notices_file, "w", encoding="utf-8") as handle:
                json.dump(existing, handle, ensure_ascii=False, indent=2)
            print(f"[Scheduler] Saved {len(new_items)} new notices")

        return new_items

    def _load_notices(self) -> list[dict]:
        if not os.path.exists(self.notices_file):
            return []

        try:
            with open(self.notices_file, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []

    def _update_last_run(self):
        with open(self.last_run_file, "w", encoding="utf-8") as handle:
            handle.write(datetime.now().isoformat())

    def get_last_run(self) -> str | None:
        if os.path.exists(self.last_run_file):
            with open(self.last_run_file, encoding="utf-8") as handle:
                return handle.read().strip()
        return None

    def get_notices(self, source: str | None = None, limit: int = 50) -> list[dict]:
        notices = self._load_notices()

        if source:
            notices = [notice for notice in notices if notice.get("source") == source]

        notices.sort(key=lambda item: item.get("collected_at", ""), reverse=True)
        return notices[:limit]

    def get_new_notices(self) -> list[dict]:
        return [notice for notice in self._load_notices() if notice.get("is_new", False)]

    def mark_as_read(self, url: str):
        notices = self._load_notices()
        for notice in notices:
            if notice.get("url") == url:
                notice["is_new"] = False

        with open(self.notices_file, "w", encoding="utf-8") as handle:
            json.dump(notices, handle, ensure_ascii=False, indent=2)


_scheduler: NoticeScheduler | None = None


def get_scheduler() -> NoticeScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = NoticeScheduler()
    return _scheduler


async def main():
    scheduler = get_scheduler()
    notices = await scheduler.collect_all_notices()

    print("\n=== Collected notices ===")
    for index, notice in enumerate(notices[:10], 1):
        title = str(notice.get("title", ""))[:50]
        print(f"{index}. [{notice.get('source', 'unknown')}] {title}")


if __name__ == "__main__":
    asyncio.run(main())

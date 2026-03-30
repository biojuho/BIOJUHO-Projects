"""
BioLinker - Notice Scheduler
자동 공고 수집 스케줄러
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .kddf_crawler import get_kddf_crawler
    from .ntis_crawler import get_ntis_crawler
    from .vector_store import get_vector_store
except ImportError:
    from kddf_crawler import get_kddf_crawler
    from ntis_crawler import get_ntis_crawler
    from vector_store import get_vector_store


class NoticeScheduler:
    """공고 수집 스케줄러 (APScheduler)"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.notices_file = os.path.join(data_dir, "notices.json")
        self.last_run_file = os.path.join(data_dir, "last_run.txt")
        os.makedirs(data_dir, exist_ok=True)

        # Initialize Scheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.run_collection_job,
            CronTrigger(hour=2, minute=0),  # Run daily at 02:00 AM
            id="daily_notice_collection",
            replace_existing=True,
        )

    def start(self):
        """스케줄러 시작"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("[Scheduler] Started Background Scheduler (Daily 02:00 AM)")

    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("[Scheduler] Stopped Background Scheduler")

    def run_collection_job(self):
        """스케줄러 잡 실행 래퍼 (Async function 호출)"""
        print("[Scheduler] Triggering scheduled collection...")
        try:
            # Create a new event loop for the async task if necessary
            # Or run in the main loop if possible.
            # safely run async in a thread:
            asyncio.run(self.collect_all_notices())
        except Exception as e:
            print(f"[Scheduler] Job failed: {e}")

    async def collect_all_notices(self) -> list[dict]:
        """모든 소스에서 공고 수집"""
        all_notices = []

        print(f"[Scheduler] Starting collection at {datetime.now()}")

        # KDDF 수집
        try:
            kddf = get_kddf_crawler()
            kddf_notices = await kddf.fetch_notice_list()
            all_notices.extend(kddf_notices)
            print(f"[KDDF] Collected {len(kddf_notices)} notices")
        except Exception as e:
            print(f"[KDDF] Error: {e}")

        # NTIS 수집
        ntis = get_ntis_crawler()
        try:
            ntis_notices = await ntis.fetch_notice_list("바이오")
            all_notices.extend(ntis_notices)
            print(f"[NTIS] Collected {len(ntis_notices)} notices")
        except Exception as e:
            print(f"[NTIS] Error: {e}")

        # 추가 검색어로 NTIS 수집
        for keyword in ["신약", "의약품", "AI 헬스케어"]:
            try:
                extra = await ntis.fetch_notice_list(keyword)
                # 중복 제거
                existing_urls = {n["url"] for n in all_notices}
                new_notices = [n for n in extra if n["url"] not in existing_urls]
                all_notices.extend(new_notices)
                print(f"[NTIS:{keyword}] Added {len(new_notices)} new notices")
            except Exception as e:
                print(f"[NTIS:{keyword}] Error: {e}")

        # 저장 & 신규 공고 추출
        new_notices = self._save_notices(all_notices)
        self._update_last_run()

        # Vector Store Indexing
        try:
            vector_store = get_vector_store()

            if new_notices:
                print(f"[Scheduler] Indexing {len(new_notices)} new notices to VectorDB...")

                # Crawlers should be accessed via their getters
                # Crawlers should be accessed via their getters
                kddf = get_kddf_crawler()
                ntis = get_ntis_crawler()

                for notice in new_notices:
                    try:
                        rfp = None
                        source = notice.get("source")
                        url = notice.get("url")

                        if source == "KDDF":
                            rfp = await kddf.fetch_notice_detail(url)
                        elif source == "NTIS":
                            rfp = await ntis.fetch_notice_detail(url)

                        if rfp:
                            vector_store.add_notice(rfp)
                            print(f"[Scheduler] Indexed: {rfp.title[:30]}...")
                        else:
                            print(f"[Scheduler] Failed to fetch details for {url}")

                        # Random delay to be polite
                        await asyncio.sleep(1)

                    except Exception as e:
                        print(f"[Scheduler] Failed to index {notice.get('url')}: {e}")

        except Exception as e:
            print(f"[Scheduler] Vector indexing error: {e}")

        print(f"[Scheduler] Total: {len(all_notices)} notices collected")
        return all_notices

    def _save_notices(self, notices: list[dict]) -> list[dict]:
        """공고 저장 (신규 공고 반환)"""
        # 기존 공고 로드
        existing = self._load_notices()
        existing_urls = {n["url"] for n in existing}

        # 신규 공고 추가
        new_items = []
        for notice in notices:
            if notice["url"] not in existing_urls:
                notice["collected_at"] = datetime.now().isoformat()
                notice["is_new"] = True
                existing.append(notice)
                new_items.append(notice)

        # 저장
        if new_items:
            with open(self.notices_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"[Scheduler] {len(new_items)} new notices saved!")

        return new_items

    def _load_notices(self) -> list[dict]:
        """저장된 공고 로드"""
        if os.path.exists(self.notices_file):
            with open(self.notices_file, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _update_last_run(self):
        """마지막 실행 시간 기록"""
        with open(self.last_run_file, "w") as f:
            f.write(datetime.now().isoformat())

    def get_last_run(self) -> str | None:
        """마지막 실행 시간 조회"""
        if os.path.exists(self.last_run_file):
            with open(self.last_run_file) as f:
                return f.read().strip()
        return None

    def get_notices(self, source: str | None = None, limit: int = 50) -> list[dict]:
        """저장된 공고 조회"""
        notices = self._load_notices()

        if source:
            notices = [n for n in notices if n.get("source") == source]

        # 최신순 정렬
        notices.sort(key=lambda x: x.get("collected_at", ""), reverse=True)

        return notices[:limit]

    def get_new_notices(self) -> list[dict]:
        """신규 공고만 조회"""
        notices = self._load_notices()
        return [n for n in notices if n.get("is_new", False)]

    def mark_as_read(self, url: str):
        """공고를 읽음으로 표시"""
        notices = self._load_notices()
        for notice in notices:
            if notice["url"] == url:
                notice["is_new"] = False

        with open(self.notices_file, "w", encoding="utf-8") as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)


# Singleton
_scheduler: NoticeScheduler | None = None


def get_scheduler() -> NoticeScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = NoticeScheduler()
    return _scheduler


async def main():
    """CLI 실행"""
    scheduler = get_scheduler()
    notices = await scheduler.collect_all_notices()

    print("\n=== 수집된 공고 ===")
    for i, notice in enumerate(notices[:10], 1):
        print(f"{i}. [{notice['source']}] {notice['title'][:50]}...")


if __name__ == "__main__":
    asyncio.run(main())

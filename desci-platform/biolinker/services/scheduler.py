"""
BioLinker - Notice Scheduler
자동 공고 수집 스케줄러
"""
import os
import asyncio
from datetime import datetime
from typing import Optional
import json

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import RFPDocument

try:
    from .kddf_crawler import get_kddf_crawler
    from .ntis_crawler import get_ntis_crawler
except ImportError:
    from kddf_crawler import get_kddf_crawler
    from ntis_crawler import get_ntis_crawler


class NoticeScheduler:
    """공고 수집 스케줄러"""
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.notices_file = os.path.join(data_dir, "notices.json")
        self.last_run_file = os.path.join(data_dir, "last_run.txt")
        os.makedirs(data_dir, exist_ok=True)
    
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
        try:
            ntis = get_ntis_crawler()
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
                existing_urls = {n['url'] for n in all_notices}
                new_notices = [n for n in extra if n['url'] not in existing_urls]
                all_notices.extend(new_notices)
                print(f"[NTIS:{keyword}] Added {len(new_notices)} new notices")
            except Exception as e:
                print(f"[NTIS:{keyword}] Error: {e}")
        
        # 저장
        self._save_notices(all_notices)
        self._update_last_run()
        
        print(f"[Scheduler] Total: {len(all_notices)} notices collected")
        return all_notices
    
    def _save_notices(self, notices: list[dict]):
        """공고 저장"""
        # 기존 공고 로드
        existing = self._load_notices()
        existing_urls = {n['url'] for n in existing}
        
        # 신규 공고 추가
        new_count = 0
        for notice in notices:
            if notice['url'] not in existing_urls:
                notice['collected_at'] = datetime.now().isoformat()
                notice['is_new'] = True
                existing.append(notice)
                new_count += 1
        
        # 저장
        with open(self.notices_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        
        if new_count > 0:
            print(f"[Scheduler] {new_count} new notices saved!")
    
    def _load_notices(self) -> list[dict]:
        """저장된 공고 로드"""
        if os.path.exists(self.notices_file):
            with open(self.notices_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _update_last_run(self):
        """마지막 실행 시간 기록"""
        with open(self.last_run_file, 'w') as f:
            f.write(datetime.now().isoformat())
    
    def get_last_run(self) -> Optional[str]:
        """마지막 실행 시간 조회"""
        if os.path.exists(self.last_run_file):
            with open(self.last_run_file, 'r') as f:
                return f.read().strip()
        return None
    
    def get_notices(self, source: Optional[str] = None, limit: int = 50) -> list[dict]:
        """저장된 공고 조회"""
        notices = self._load_notices()
        
        if source:
            notices = [n for n in notices if n.get('source') == source]
        
        # 최신순 정렬
        notices.sort(key=lambda x: x.get('collected_at', ''), reverse=True)
        
        return notices[:limit]
    
    def get_new_notices(self) -> list[dict]:
        """신규 공고만 조회"""
        notices = self._load_notices()
        return [n for n in notices if n.get('is_new', False)]
    
    def mark_as_read(self, url: str):
        """공고를 읽음으로 표시"""
        notices = self._load_notices()
        for notice in notices:
            if notice['url'] == url:
                notice['is_new'] = False
        
        with open(self.notices_file, 'w', encoding='utf-8') as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)


# Singleton
_scheduler: Optional[NoticeScheduler] = None

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

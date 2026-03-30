from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from notion_client import AsyncClient
from runtime import (
    AlreadyRunningError,
    JobLock,
    PipelineStateStore,
    configure_stdout_utf8,
    create_notion_page_with_retry,
    generate_run_id,
    get_logger,
)
from settings import NOTION_API_KEY, NOTION_REPORTS_DATABASE_ID
from telegram_notifier import send_telegram_message


def chunk_text(text: str, limit: int = 1900) -> list[str]:
    return [text[index : index + limit] for index in range(0, len(text), limit)]


async def publish_to_notion(*, title: str, file_path: Path, run_id: str | None = None) -> int:
    configure_stdout_utf8()
    run_id = run_id or generate_run_id("content_publisher")
    logger = get_logger("content_publisher", run_id)
    state = PipelineStateStore()
    state.record_job_start(run_id, "content_publisher")

    if not NOTION_API_KEY:
        logger.error("bootstrap", "failed", "NOTION_API_KEY missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_API_KEY missing")
        send_telegram_message("❌ <b>Content Publisher Failed</b>\nNOTION_API_KEY is missing in `.env`.")
        return 1
    if not NOTION_REPORTS_DATABASE_ID:
        logger.error("bootstrap", "failed", "NOTION_REPORTS_DATABASE_ID missing")
        state.record_job_finish(run_id, status="failed", error_text="NOTION_REPORTS_DATABASE_ID missing")
        send_telegram_message("❌ <b>Content Publisher Failed</b>\nNOTION_REPORTS_DATABASE_ID is missing in `.env`.")
        return 1
    if not file_path.exists():
        logger.error("input", "failed", "report file missing", path=file_path)
        state.record_job_finish(run_id, status="failed", error_text=f"report file missing: {file_path}")
        send_telegram_message(
            f"❌ <b>Content Publisher Failed</b>\nInput file not found: <code>{file_path.name}</code>"
        )
        return 1

    notion = AsyncClient(auth=NOTION_API_KEY)

    try:
        with JobLock("content_publisher", run_id):
            content = file_path.read_text(encoding="utf-8")
            children = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                }
                for chunk in chunk_text(content)
            ]

            page = await create_notion_page_with_retry(
                notion_client=notion,
                parent={"database_id": NOTION_REPORTS_DATABASE_ID},
                properties={
                    "Name": {"title": [{"text": {"content": title}}]},
                    "Date": {"date": {"start": datetime.now().date().isoformat()}},
                },
                children=children[:100],
                logger=logger,
                step="upload",
            )
            state.record_job_finish(
                run_id, status="success", summary={"blocks": len(children), "page_id": page.get("id")}
            )
            logger.info("complete", "success", "content published", page_id=page.get("id"), blocks=len(children))

            page_url = page.get("url", "No URL available")
            success_msg = (
                f"✅ <b>Content Published Successfully</b>\n\n"
                f"<b>Title:</b> {title}\n"
                f"<b>Blocks:</b> {len(children)}\n"
                f"<a href='{page_url}'>View on Notion</a>"
            )
            send_telegram_message(success_msg)
            return 0
    except AlreadyRunningError:
        logger.warning("lock", "skipped", "job already running")
        state.record_job_finish(run_id, status="skipped", error_text="already running")
        return 2
    except Exception as exc:
        logger.error("complete", "failed", "content publishing failed", error=str(exc))
        state.record_job_finish(run_id, status="failed", error_text=str(exc))
        send_telegram_message(f"❌ <b>Content Publisher Failed</b>\nAn exception occurred:\n<code>{str(exc)}</code>")
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload a markdown report to Notion.")
    parser.add_argument("--title", required=True, help="Title of the report")
    parser.add_argument("--file", required=True, help="Path to the markdown report file")
    parser.add_argument("--run-id", help="Optional run identifier for logs and state tracking")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(publish_to_notion(title=args.title, file_path=Path(args.file), run_id=args.run_id))


if __name__ == "__main__":
    raise SystemExit(main())

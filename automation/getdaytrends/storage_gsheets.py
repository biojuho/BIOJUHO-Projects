"""
getdaytrends — Google Sheets Storage
gspread 기반 Google Sheets 동기화.
storage.py에서 분리됨.
"""

from datetime import datetime

from loguru import logger as log

try:
    from .config import AppConfig
    from .models import ScoredTrend, TweetBatch
except ImportError:
    from config import AppConfig
    from models import ScoredTrend, TweetBatch

# Google Sheets (optional dependency)
try:
    import gspread
    from google.auth.exceptions import GoogleAuthError
    from google.oauth2.service_account import Credentials

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None  # type: ignore
    Credentials = None  # type: ignore
    GoogleAuthError = None  # type: ignore


def _is_gspread_provider_error(exc: Exception) -> bool:
    candidates: list[type[BaseException]] = []
    if GSPREAD_AVAILABLE and gspread is not None:
        gspread_exceptions = getattr(gspread, "exceptions", None)
        if gspread_exceptions is not None:
            for name in ("APIError", "GSpreadException", "SpreadsheetNotFound", "WorksheetNotFound"):
                candidate = getattr(gspread_exceptions, name, None)
                if isinstance(candidate, type):
                    candidates.append(candidate)
    if isinstance(GoogleAuthError, type):
        candidates.append(GoogleAuthError)
    return any(isinstance(exc, candidate) for candidate in candidates)


def save_to_google_sheets(
    batch: TweetBatch,
    trend: ScoredTrend,
    config: AppConfig,
) -> bool:
    """Append one batch to Google Sheets using a stable V2-compatible schema."""
    if not GSPREAD_AVAILABLE:
        log.error("gspread package is not installed. Run: pip install gspread google-auth")
        return False

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(config.google_service_json, scopes=scopes)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(config.google_sheet_id).sheet1

        if sheet.row_count == 0 or not sheet.cell(1, 1).value:
            headers = [
                "Created",
                "Rank",
                "Topic",
                "Empathy",
                "Curiosity",
                "Question",
                "Quote",
                "Reaction",
                "Status",
                "Viral Score",
                "Thread",
            ]
            sheet.append_row(headers, value_input_option="USER_ENTERED")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        tweet_map = {t.tweet_type: t.content for t in batch.tweets}
        thread_text = "\n---\n".join(batch.thread.tweets) if batch.thread else ""

        # B-010 fix: tweet_type 키를 영어로 통일 (Mojibake 컬럼 매핑 오류 방지)
        row = [
            now,
            trend.rank,
            batch.topic,
            tweet_map.get("empathy", tweet_map.get("공감형", "")),
            tweet_map.get("curiosity", tweet_map.get("호기심형", "")),
            tweet_map.get("question", tweet_map.get("질문형", "")),
            tweet_map.get("quote", tweet_map.get("인용형", "")),
            tweet_map.get("reaction", tweet_map.get("반응/토론형", "")),
            "Ready",
            trend.viral_potential,
            thread_text[:2000],
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")

        log.info(f"Google Sheets sync complete: '{batch.topic}'")
        return True

    except FileNotFoundError:
        log.error(f"Service account JSON not found: {config.google_service_json}")
        return False
    except (ConnectionError, TimeoutError) as e:
        log.error(f"Google Sheets network error: {type(e).__name__}: {e}")
        return False
    except Exception as e:
        if _is_gspread_provider_error(e):
            log.error(f"Google Sheets API error (gspread): {type(e).__name__}: {e}")
        else:
            log.error(f"Google Sheets sync failed: {type(e).__name__}: {e}")
        return False

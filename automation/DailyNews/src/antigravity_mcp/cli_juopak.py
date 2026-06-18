"""CLI subcommand for the 쥬팍식 정량 다이제스트.

Usage:
  # 기사 JSON 파일을 던지면 노션 붙여넣기용 마크다운이 나온다
  antigravity-mcp juopak digest --articles-file articles.json
  cat articles.json | antigravity-mcp juopak digest          # stdin도 가능
  antigravity-mcp juopak digest --articles-file a.json --focus "AI 에이전트"
  antigravity-mcp juopak digest --articles-file a.json --dry-run   # 프롬프트만 미리보기

기사 JSON 형식 (리스트):
  [{"title": "...", "source": "...", "link": "https://...",
    "body": "본문 또는 description"}]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

logger = logging.getLogger(__name__)


def register_juopak_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the 'juopak' subcommand group."""
    juopak = subparsers.add_parser("juopak", help="쥬팍식 정량 다이제스트 생성")
    juopak_sub = juopak.add_subparsers(dest="juopak_command", required=True)

    digest = juopak_sub.add_parser("digest", help="기사 묶음 -> 노션 붙여넣기용 쥬팍 다이제스트")
    digest.add_argument(
        "--articles-file",
        default="-",
        help="기사 JSON 파일 경로. '-' 또는 생략 시 stdin (default: stdin)",
    )
    digest.add_argument("--focus", default="", help="오늘 강조할 주제 (선택)")
    digest.add_argument("--date", default="", help="다이제스트 날짜 (기본: 오늘)")
    digest.add_argument("--output", default="-", help="출력 파일 경로 ('-' = stdout)")
    digest.add_argument(
        "--dry-run",
        action="store_true",
        help="LLM 호출 없이 시스템/사용자 프롬프트 + 권위 출처 블록만 미리보기",
    )
    digest.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="무결성 하드 실패 시 교정 재시도 횟수 (default: 1)",
    )
    digest.add_argument("--json", action="store_true", dest="json_output", help="JSON 봉투로 출력")


def dispatch_juopak_command(args: argparse.Namespace) -> int:
    """Dispatch juopak subcommands."""
    if args.juopak_command == "digest":
        return _run_digest(args)
    return 1


def _read_articles(path: str) -> list[dict]:
    if path in ("-", ""):
        raw = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    data = json.loads(raw)
    if isinstance(data, dict) and "articles" in data:
        data = data["articles"]
    if not isinstance(data, list):
        raise ValueError("기사 JSON 은 객체 리스트여야 한다.")
    return [a for a in data if isinstance(a, dict)]


def _today(args: argparse.Namespace) -> str:
    if args.date:
        return str(args.date)
    from datetime import datetime

    return datetime.now().date().isoformat()


def _emit(text: str, *, output: str) -> None:
    if output in ("-", ""):
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    else:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote digest to {output}", file=sys.stderr)


def _error(message: str, *, code: str, json_output: bool) -> int:
    if json_output:
        payload = {"status": "error", "error": {"code": code, "message": message}}
        sys.stdout.buffer.write((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    else:
        print(message, file=sys.stderr)
    return 1


def _run_digest(args: argparse.Namespace) -> int:
    from antigravity_mcp.integrations import juopak_digest as jd

    try:
        articles = _read_articles(args.articles_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _error(
            f"기사 JSON 을 읽지 못했다: {type(exc).__name__}: {exc}",
            code="invalid_articles_input",
            json_output=args.json_output,
        )

    if not articles:
        # v2 스펙: 기사 없으면 한 줄만.
        if args.json_output:
            sys.stdout.buffer.write(
                (json.dumps({"status": "empty", "message": "기사 붙여넣어."}, ensure_ascii=False) + "\n").encode("utf-8")
            )
            sys.stdout.buffer.flush()
        else:
            print("기사 붙여넣어.")
        return 0

    today = _today(args)

    if args.dry_run:
        system_prompt = jd.build_juopak_system_prompt()
        user_prompt = jd.build_juopak_user_prompt(articles, focus=args.focus, today=today)
        sources = jd.render_sources_block(articles)
        preview = (
            "===== SYSTEM PROMPT =====\n"
            f"{system_prompt}\n\n"
            "===== USER PROMPT =====\n"
            f"{user_prompt}\n\n"
            "===== 권위 출처 블록 (코드 생성) =====\n"
            f"{sources}"
        )
        _emit(preview, output=args.output)
        return 0

    if not jd.is_available():
        return _error(
            "LLM 클라이언트를 불러올 수 없다 (shared.llm import 실패). API 키/환경을 확인하라.",
            code="llm_unavailable",
            json_output=args.json_output,
        )

    try:
        result = asyncio.run(
            jd.generate_juopak_digest(
                articles,
                focus=args.focus,
                today=today,
                max_retries=max(0, args.max_retries),
            )
        )
    except jd.JuopakDigestError as exc:
        return _error(
            f"다이제스트 생성 실패: {exc}",
            code="digest_generation_failed",
            json_output=args.json_output,
        )

    if args.json_output:
        sys.stdout.buffer.write(
            (json.dumps({"status": "ok", **result}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )
        sys.stdout.buffer.flush()
        return 0

    if result.get("warnings"):
        print(f"[무결성 경고] {', '.join(result['warnings'])}", file=sys.stderr)
    _emit(result["markdown"], output=args.output)
    return 0

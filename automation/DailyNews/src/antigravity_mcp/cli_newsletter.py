"""CLI commands for newsletter management.

Usage:
  antigravity-mcp newsletter stats
  antigravity-mcp newsletter add --email user@example.com [--categories Tech Economy_KR]
  antigravity-mcp newsletter remove --email user@example.com
  antigravity-mcp newsletter list [--status active]
  antigravity-mcp newsletter send-test --email user@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import json


def register_newsletter_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register newsletter subcommands onto the main CLI parser."""
    newsletter = subparsers.add_parser("newsletter", help="Newsletter subscriber management")
    nl_sub = newsletter.add_subparsers(dest="newsletter_command", required=True)

    # stats
    nl_sub.add_parser("stats", help="Show subscriber statistics")

    # add
    add_cmd = nl_sub.add_parser("add", help="Add a subscriber")
    add_cmd.add_argument("--email", required=True)
    add_cmd.add_argument("--name", default="")
    add_cmd.add_argument("--categories", nargs="*", default=[])

    # remove
    remove_cmd = nl_sub.add_parser("remove", help="Unsubscribe an email")
    remove_cmd.add_argument("--email", required=True)

    # list
    list_cmd = nl_sub.add_parser("list", help="List subscribers")
    list_cmd.add_argument("--status", default="active", choices=["active", "all", "paused", "unsubscribed"])
    list_cmd.add_argument("--limit", type=int, default=50)

    # send-test
    test_cmd = nl_sub.add_parser("send-test", help="Send a test newsletter to a specific email")
    test_cmd.add_argument("--email", required=True)
    test_cmd.add_argument("--dry-run", action="store_true", default=True)


def dispatch_newsletter_command(args: argparse.Namespace) -> int:
    """Dispatch newsletter subcommands."""
    from antigravity_mcp.integrations.subscriber_store import SubscriberStore

    store = SubscriberStore()
    cmd = args.newsletter_command

    if cmd == "stats":
        stats = store.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    if cmd == "add":
        sub = store.add_subscriber(args.email, name=args.name, categories=args.categories)
        if sub:
            print(f"✅ 구독자 추가: {sub.email} (ID: {sub.id})")
            if sub.categories:
                print(f"   카테고리: {', '.join(sub.categories)}")

            # Try to send welcome email
            from antigravity_mcp.integrations.newsletter_adapter import NewsletterAdapter

            adapter = NewsletterAdapter(subscriber_store=store)
            if adapter.is_configured:
                result = asyncio.run(adapter.send_welcome(sub))
                print(f"   환영 이메일: {result.get('status', 'unknown')}")
            else:
                print("   ⚠️ RESEND_API_KEY 미설정 — 환영 이메일 건너뜀")
        else:
            print(f"⚠️ 이미 등록된 이메일: {args.email}")
        return 0

    if cmd == "remove":
        if store.unsubscribe(args.email):
            print(f"✅ 구독 해지: {args.email}")
        else:
            print(f"❌ 해당 이메일을 찾을 수 없습니다: {args.email}")
        return 0

    if cmd == "list":
        if args.status == "active":
            subscribers = store.get_active_subscribers()
        else:
            # For non-active statuses, we need to query directly
            subscribers = store.get_active_subscribers()  # fallback — show active
            print(f"(showing active subscribers, filter '{args.status}' uses active list)")

        if not subscribers:
            print("구독자가 없습니다.")
            return 0

        print(f"{'Email':<35} {'Name':<15} {'Status':<12} {'Score':<8} {'Categories'}")
        print("─" * 90)
        for sub in subscribers[: args.limit]:
            cats = ", ".join(sub.categories) if sub.categories else "—"
            print(f"{sub.email:<35} {(sub.name or '—'):<15} {sub.status:<12} {sub.engagement_score:<8.2f} {cats}")
        total = store.get_subscriber_count()
        print(f"\n총 활성 구독자 수: {total}")
        return 0

    if cmd == "send-test":
        from antigravity_mcp.integrations.newsletter_adapter import NewsletterAdapter

        adapter = NewsletterAdapter(subscriber_store=store)
        print(f"📧 테스트 이메일 발송 → {args.email}")
        print(f"   dry_run={args.dry_run}")

        # Create a mock report for testing
        from unittest.mock import MagicMock

        mock_report = MagicMock()
        mock_report.report_id = "test-rpt-001"
        mock_report.category = "Economy_KR"
        mock_report.window_name = "morning"
        mock_report.summary_lines = [
            "📈 원/달러 환율 1,352원 — 3개월 만의 최고치",
            "🏦 한국은행 기준금리 3.25% 동결 전망",
            "🤖 OpenAI GPT-5, 6월 출시 확정",
        ]
        mock_report.insights = ["기준금리 동결 지속 시 가계대출 금리 추가 하락 가능성"]
        mock_report.channel_drafts = []

        from antigravity_mcp.integrations.subscriber_store import Subscriber

        test_sub = Subscriber(id="test", email=args.email, status="active")
        result = asyncio.run(
            adapter.send_daily_brief(
                reports=[mock_report],
                subscribers=[test_sub],
                edition="morning",
                dry_run=args.dry_run,
            )
        )
        print(f"   결과: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return 0

    return 1

"""
Unified Growth Pipeline v2.0
subprocess 기반 파이프라인을 대체하는 직접 호출 방식의 통합 엔진.
모든 단계에서 Analytics DB에 기록하고, Viral Score로 품질을 검증합니다.
"""
import json
import os
import sys
import logging
from datetime import datetime

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE_DIR, ".agent"))

from engine.analytics import (
    save_trend, save_post, save_reply, update_post_status,
    get_dashboard_stats, is_trend_stale
)
from engine.viral_scorer import calculate_viral_score
from engine.scheduler import get_next_posting_slot
from engine.x_client import XClient
from utils.llm import LLMWrapper

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("Pipeline")

CONFIG_PATH = os.path.join(BASE_DIR, "config", "x_growth_config.json")


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _parse_llm_json(response):
    """LLM 응답에서 JSON 추출 (강건한 파싱)"""
    import re
    # ```json ... ``` 블록 우선 시도 (코드 펜스 내 전체 내용 캡처)
    code_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
    if code_match:
        try:
            return json.loads(code_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 일반 JSON 객체 (greedy - 가장 바깥쪽 중괄호 매칭)
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    # JSON 배열
    arr_match = re.search(r'\[.*\]', response, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ═══════════════════════════════════════════════
# Step 1: Trend Radar
# ═══════════════════════════════════════════════

def step_radar(keywords=None):
    """트렌드 수집 및 분석"""
    config = _load_config()
    if not keywords:
        keywords = config.get("targeting", config.get("operator_variables", {})).get("niche_keywords", ["AI", "DeSci", "Biotech"])

    logger.info(f"[Radar] Scanning keywords: {keywords}")
    llm = LLMWrapper()

    # 데이터 소스별 수집
    from skills.x_radar.scraper import fetch_twitter_trends, fetch_reddit_trends, fetch_google_news_trends

    results = []
    for kw in keywords:
        if is_trend_stale(kw, hours=4):
            logger.info(f"  [Radar] '{kw}' - 최근 4시간 내 분석 완료, 스킵")
            continue

        twitter_data = fetch_twitter_trends(kw)
        reddit_data = fetch_reddit_trends(kw)
        news_data = fetch_google_news_trends(kw)

        combined = f"[X 실시간]\n{twitter_data}\n\n[Reddit]\n{reddit_data}\n\n[뉴스]\n{news_data}"

        prompt = f"""키워드 '{kw}'에 대한 실시간 데이터를 분석하세요.

데이터:
{combined}

다음 JSON으로 응답하세요:
{{
    "keyword": "{kw}",
    "volume_estimate": 숫자(추정 24시간 볼륨),
    "trend_acceleration": "+N%" 또는 "-N%",
    "viral_potential": 0-100 사이 점수,
    "top_insight": "가장 뜨거운 이슈 1문장 요약",
    "suggested_angles": [
        "반직관적 앵글 1",
        "데이터 기반 앵글 2",
        "미래 예측 앵글 3"
    ]
}}"""

        response = llm.generate(prompt, tier="fast")
        parsed = _parse_llm_json(response)

        if parsed:
            save_trend(
                keyword=kw,
                volume=parsed.get("volume_estimate", 0),
                acceleration=parsed.get("trend_acceleration", "0%"),
                insight=parsed.get("top_insight", ""),
                angle=json.dumps(parsed.get("suggested_angles", []), ensure_ascii=False),
                viral_potential=parsed.get("viral_potential", 0)
            )
            results.append(parsed)
        else:
            results.append({"keyword": kw, "error": "분석 실패", "raw_news": news_data})

    logger.info(f"[Radar] {len(results)} keywords analyzed")
    return results


# ═══════════════════════════════════════════════
# Step 2: Opinion & Hook Generation
# ═══════════════════════════════════════════════

def step_generate_content(trend_data):
    """트렌드 데이터를 기반으로 다양한 포맷의 콘텐츠를 생성"""
    config = _load_config()
    persona = config.get("operator", config.get("operator_variables", {})).get("persona_tone", "데이터 기반 테크 분석가")

    # Load RLHF Best Hooks
    best_hooks_str = ""
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "output")
        best_hooks_path = os.path.join(output_dir, "best_hooks.json")
        if os.path.exists(best_hooks_path):
            with open(best_hooks_path, "r", encoding="utf-8") as f:
                best_hooks = json.load(f)
            if best_hooks:
                best_hooks_str = "\n[참고: 과거 인게이지먼트가 높았던 우수 훅(Hook) 데이터]\n"
                for i, hook in enumerate(best_hooks):
                    best_hooks_str += f"{i+1}. (Likes: {hook.get('likes')}, RTs: {hook.get('retweets')}) {hook.get('text')}\n"
                best_hooks_str += "위의 성공적인 훅 구조를 참고하여 이번 콘텐츠에도 비슷한 텐션과 질문 던지기 기법을 활용하세요.\n"
    except Exception:
        pass

    llm = LLMWrapper()
    all_content = []

    for trend in trend_data[:3]:  # 상위 3개 트렌드
        keyword = trend.get("keyword", "")
        insight = trend.get("top_insight", "")
        angles = trend.get("suggested_angles", [])
        angle_text = "\n".join(f"- {a}" for a in angles) if angles else "- 반직관적 해석"

        prompt = f"""당신은 X(Twitter) 콘텐츠 전략가입니다. 페르소나: {persona}

트렌드: {keyword}
핵심 인사이트: {insight}
제안된 앵글:
{angle_text}
{best_hooks_str}
아래 5가지 포맷의 콘텐츠를 생성하세요. 
(조건: 해시태그 절대 사용 금지, 이모지(이모티콘)는 꼭 필요할 때만 최소한으로 사용)

JSON 응답:
{{
    "keyword": "{keyword}",
    "contents": [
        {{
            "type": "single",
            "hook": "강력한 첫 문장 (150자 이내)",
            "body": "짧은 의견을 담은 단일 트윗 (140자 이내, 줄바꿈은 \\n)"
        }},
        {{
            "type": "thread",
            "hook": "정보성 스레드 첫 트윗 훅",
            "body": "1/ 첫 트윗\\n\\n2/ 두번째\\n\\n3/ 세번째\\n\\n4/ CTA 마무리"
        }},
        {{
            "type": "poll_tweet",
            "hook": "투표를 유도하는 질문형 트윗",
            "body": "논란이 될 만한 질문 + 선택지 안내",
            "poll_options": ["옵션A", "옵션B", "옵션C"]
        }},
        {{
            "type": "joke_meme",
            "hook": "공감 유발 밈/유머 캡션",
            "body": "관련 밈(유머) 이미지에 들어갈 매우 짧은 캡션 텍스트 (줄바꿈 가능)"
        }},
        {{
            "type": "quote_reply",
            "hook": "인용 리트윗용 멘트",
            "body": "유명 인사의 격언이나 관련 트윗을 인용하며 덧붙이는 짧은 해석 (줄바꿈 가능)"
        }}
    ]
}}"""

        response = llm.generate(prompt)
        parsed = _parse_llm_json(response)

        if parsed and "contents" in parsed:
            for content in parsed["contents"]:
                content["keyword"] = keyword
                # 바이럴 스코어 계산
                score = calculate_viral_score(
                    content=content.get("body", ""),
                    hook=content.get("hook", ""),
                    keyword=keyword,
                    post_type=content.get("type", "single")
                )
                content["viral_score"] = score

                # DB에 저장
                post_id = save_post(
                    content=content.get("body", ""),
                    hook=content.get("hook", ""),
                    post_type=content.get("type", "single"),
                    keyword=keyword,
                    viral_score=score["total_score"],
                    status="draft"
                )
                content["post_id"] = post_id
                all_content.append(content)

    # 바이럴 스코어 기준 정렬
    all_content.sort(key=lambda x: x.get("viral_score", {}).get("total_score", 0), reverse=True)
    logger.info(f"[Content] {len(all_content)} pieces generated, top score: {all_content[0]['viral_score']['total_score'] if all_content else 0}")
    return all_content


# ═══════════════════════════════════════════════
# Step 3: Reply Sniper
# ═══════════════════════════════════════════════

def step_sniper(targets=None):
    """인플루언서 트윗 감시 및 답글 생성"""
    config = _load_config()
    targeting = config.get("targeting", config.get("operator_variables", {}))

    if not targets:
        targets = targeting.get("tier1_influencers", targeting.get("target_influencers", ["@elonmusk"]))

    persona = config.get("operator", config.get("operator_variables", {})).get("persona_tone", "데이터 기반 분석가")
    llm = LLMWrapper()
    x = XClient()
    results = []

    for handle in targets:
        tweets = x.get_user_tweets(handle, max_results=3)
        if not tweets:
            logger.warning(f"  [Sniper] {handle} - 트윗 가져오기 실패")
            continue

        for tweet in tweets[:1]:  # 최신 1개만
            tweet_text = tweet.get("text", "")
            tweet_id = tweet.get("id")
            metrics = tweet.get("metrics", {})

            prompt = f"""당신은 X Reply Sniper입니다. 페르소나: {persona}

타겟: {handle}
원문: "{tweet_text}"
원문 메트릭: 좋아요 {metrics.get('like_count', '?')}, RT {metrics.get('retweet_count', '?')}

규칙:
1. 280자 이내
2. 무의미한 칭찬 금지 - 반드시 새로운 데이터/관점/질문을 추가
3. 대화를 이끌어내는 질문이나 반론 포함
4. 해당 분야 전문가처럼 보이는 톤

JSON 응답:
{{
    "target": "{handle}",
    "reply": "답글 본문",
    "opportunity_score": 1-10,
    "strategy": "이 답글이 왜 효과적인지 1문장"
}}"""

            response = llm.generate(prompt, tier="smart")
            parsed = _parse_llm_json(response)

            if parsed:
                reply_id = save_reply(
                    target_handle=handle,
                    original_tweet=tweet_text,
                    reply_text=parsed.get("reply", ""),
                    opportunity_score=parsed.get("opportunity_score", 0),
                    original_tweet_id=str(tweet_id) if tweet_id else None
                )
                results.append({**parsed, "reply_id": reply_id, "original_tweet_id": tweet_id})

    logger.info(f"[Sniper] {len(results)} replies generated")
    return results


# ═══════════════════════════════════════════════
# Step 4: Publish to Notion
# ═══════════════════════════════════════════════

def step_publish_notion(contents, replies=None):
    """최종 콘텐츠를 Notion에 게시"""
    from skills.dashboard_updater.publisher import push_to_notion

    if not contents:
        return {"status": "skip", "reason": "게시할 콘텐츠 없음"}

    # 최고 바이럴 스코어 콘텐츠로 노션 페이지 구성
    top = contents[0]
    body_parts = []

    body_parts.append(f"## 바이럴 스코어: {top.get('viral_score', {}).get('total_score', '?')}/100 ({top.get('viral_score', {}).get('grade', '?')})")
    body_parts.append(f"\n### 메인 콘텐츠 ({top.get('type', 'single')})")
    body_parts.append(top.get("body", ""))

    if len(contents) > 1:
        body_parts.append("\n---\n### 대안 콘텐츠")
        for alt in contents[1:5]:
            score = alt.get("viral_score", {}).get("total_score", 0)
            body_parts.append(f"\n**[{alt.get('type')}] Score: {score}** - {alt.get('hook', '')}")

    if replies:
        body_parts.append("\n---\n### Reply Sniper 초안")
        for r in replies:
            body_parts.append(f"\n> **{r.get('target', '')}** (Score: {r.get('opportunity_score', 0)})")
            body_parts.append(f"> {r.get('reply', '')}")

    full_content = "\n".join(body_parts)
    hook = top.get("hook", "Daily Growth Report")
    keyword = top.get("keyword", "Daily")

    result_str = push_to_notion(keyword, hook, full_content)
    try:
        result = json.loads(result_str)
        if result.get("status") == "success" and top.get("post_id"):
            update_post_status(top["post_id"], "notion_ready", notion_url=result.get("notion_url"))
        return result
    except json.JSONDecodeError:
        return {"status": "error", "raw": result_str}


# ═══════════════════════════════════════════════
# Step 5: Alert
# ═══════════════════════════════════════════════

def step_alert(summary, is_error=False):
    """텔레그램 알림 전송"""
    from skills.trend_monitor.webhook import send_telegram_alert
    
    if is_error:
        summary = f"🚨 [X Growth Engine ERROR]\n\n{summary}"
        
    return send_telegram_alert(summary)


# ═══════════════════════════════════════════════
# Master Pipeline
# ═══════════════════════════════════════════════

def run_full_pipeline():
    """전체 파이프라인 실행"""
    start = datetime.now()
    report = {"timestamp": start.isoformat(), "steps": {}}

    print("\n" + "=" * 60)
    print("  X Growth Engine v2.0 - Daily Pipeline")
    print(f"  {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # Step 1: Radar
        print("\n[1/5] Trend Radar...")
        trends = step_radar()
        report["steps"]["radar"] = {"count": len(trends), "keywords": [t.get("keyword") for t in trends]}
        if not trends:
            print("  -> 트렌드 데이터 없음. 파이프라인 중단.")
            return report

        # Step 2: Content Generation
        print("\n[2/5] Content Generation...")
        contents = step_generate_content(trends)
        report["steps"]["content"] = {
            "count": len(contents),
            "top_score": contents[0]["viral_score"]["total_score"] if contents else 0
        }

        # Step 3: Reply Sniper
        print("\n[3/5] Reply Sniper...")
        replies = step_sniper()
        report["steps"]["sniper"] = {"count": len(replies)}

        # Step 4: Notion Publish
        print("\n[4/5] Notion Dashboard...")
        notion_result = step_publish_notion(contents, replies)
        report["steps"]["notion"] = notion_result

        # Step 5: Alert
        print("\n[5/5] Sending Alert...")
        stats = get_dashboard_stats(30)
        next_slot = get_next_posting_slot()

        alert = f"""X Growth Engine 파이프라인 완료

    트렌드: {len(trends)}개 분석
    콘텐츠: {len(contents)}개 생성
    최고 바이럴 스코어: {contents[0]['viral_score']['total_score'] if contents else 0}/100
    답글 초안: {len(replies)}개
    다음 최적 게시: {next_slot.get('hour', '?')}시 ({next_slot.get('reason', '')})

    30일 통계: {stats.get('published', 0)}건 게시, 평균 인게이지먼트 {stats.get('avg_engagement_rate', 0)}%"""

        alert_result = step_alert(alert)
        report["steps"]["alert"] = alert_result

        elapsed = (datetime.now() - start).total_seconds()
        report["elapsed_seconds"] = round(elapsed, 1)
        report["status"] = "success"

        try:
            print(f"\n{'=' * 60}")
            print(f"  Pipeline completed in {elapsed:.1f}s")
            print(f"  Contents: {len(contents)} | Top Score: {contents[0]['viral_score']['total_score'] if contents else 0}/100")
            print(f"  Next optimal post: {next_slot.get('hour', '?')}:00 ({next_slot.get('reason', '')})")
            print(f"{'=' * 60}\n")
        except OSError:
            pass
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Pipeline failed: {e}")
        step_alert(f"파이프라인 실행 중 치명적 오류 발생:\n{str(e)}\n\n```\n{error_trace[:500]}\n```", is_error=True)
        report["status"] = "failed"
        report["error"] = str(e)

    return report


def run_quick_content(topic, post_type="single"):
    """빠른 단일 콘텐츠 생성 (파이프라인 없이)"""
    config = _load_config()
    persona = config.get("operator", config.get("operator_variables", {})).get("persona_tone", "데이터 기반 분석가")
    llm = LLMWrapper()

    prompt = f"""페르소나: {persona}
토픽: {topic}
포맷: {post_type}

이 토픽으로 X(Twitter)에 올릴 {post_type} 콘텐츠를 작성하세요.

JSON:
{{
    "hook": "강력한 첫 문장",
    "body": "완성된 본문 (줄바꿈은 \\n)",
    "hashtags": ["관련태그"]
}}"""

    response = llm.generate(prompt)
    parsed = _parse_llm_json(response)

    if parsed:
        score = calculate_viral_score(
            content=parsed.get("body", ""),
            hook=parsed.get("hook", ""),
            keyword=topic,
            post_type=post_type
        )
        post_id = save_post(
            content=parsed.get("body", ""),
            hook=parsed.get("hook", ""),
            post_type=post_type,
            keyword=topic,
            viral_score=score["total_score"]
        )
        return {**parsed, "viral_score": score, "post_id": post_id}

    return {"error": "생성 실패", "raw": response}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="X Growth Engine v2.0 Pipeline")
    parser.add_argument("--mode", choices=["full", "quick", "stats", "calendar"], default="full")
    parser.add_argument("--topic", type=str, help="Quick mode: 토픽")
    parser.add_argument("--type", type=str, default="single", help="Quick mode: 콘텐츠 유형")
    args = parser.parse_args()

    if args.mode == "full":
        result = run_full_pipeline()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode == "quick":
        if not args.topic:
            print("--topic 필요")
        else:
            result = run_quick_content(args.topic, args.type)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode == "stats":
        stats = get_dashboard_stats(30)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.mode == "calendar":
        from engine.scheduler import get_content_calendar
        cal = get_content_calendar(7)
        print(json.dumps(cal, ensure_ascii=False, indent=2))

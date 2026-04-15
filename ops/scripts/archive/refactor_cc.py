import sys
from pathlib import Path

def refactor_generator():
    gen_file = Path("automation/getdaytrends/generator.py")
    content = gen_file.read_text(encoding="utf-8")

    new_helpers = """
async def _run_serial_generation(
    trend: ScoredTrend, config: AppConfig, client: LLMClient,
    recent_tweets: list[str] | None, golden_refs: list | None, pattern_weights: dict | None,
    edape_block: str, threads_enabled: bool, blog_enabled: bool, gen_tier: TaskTier
) -> dict[str, Any]:
    result_map: dict[str, Any] = {}
    primary_key = "combined" if threads_enabled else "tweets"
    primary_coro = (
        generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                         edape_block=edape_block)
        if threads_enabled
        else generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                   edape_block=edape_block)
    )
    try:
        result_map[primary_key] = await primary_coro
    except Exception as exc:
        result_map[primary_key] = exc

    for key, coro in [
        ("long", generate_long_form_async(trend, config, client, tier=gen_tier)
         if config.enable_long_form and trend.viral_potential >= config.long_form_min_score else None),
        ("thread", generate_thread_async(trend, config, client, tier=gen_tier)
         if trend.viral_potential >= config.thread_min_score else None),
        ("blog", generate_blog_async(trend, config, client) if blog_enabled else None),
    ]:
        if coro is not None:
            try:
                result_map[key] = await coro
            except Exception as exc:
                result_map[key] = exc
    return result_map


async def _run_parallel_generation(
    trend: ScoredTrend, config: AppConfig, client: LLMClient,
    recent_tweets: list[str] | None, golden_refs: list | None, pattern_weights: dict | None,
    edape_block: str, threads_enabled: bool, blog_enabled: bool, gen_tier: TaskTier
) -> dict[str, Any]:
    tasks: dict[str, asyncio.Task] = {}
    if threads_enabled:
        tasks["combined"] = asyncio.ensure_future(
            generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                             edape_block=edape_block)
        )
    else:
        tasks["tweets"] = asyncio.ensure_future(
            generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                  edape_block=edape_block)
        )
    if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
        tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))
    if trend.viral_potential >= config.thread_min_score:
        tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))
    if blog_enabled:
        tasks["blog"] = asyncio.ensure_future(generate_blog_async(trend, config, client))
    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return dict(zip(keys, results, strict=False))

"""

    old_body = """    # 직렬 실행 경로 (Python 3.14+ 호환용)
    if _PY314_SERIAL_GENERATION:
        result_map: dict[str, Any] = {}
        primary_key = "combined" if threads_enabled else "tweets"
        primary_coro = (
            generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                             edape_block=edape_block)
            if threads_enabled
            else generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                       edape_block=edape_block)
        )
        try:
            result_map[primary_key] = await primary_coro
        except Exception as exc:
            result_map[primary_key] = exc

        for key, coro in [
            ("long", generate_long_form_async(trend, config, client, tier=gen_tier)
             if config.enable_long_form and trend.viral_potential >= config.long_form_min_score else None),
            ("thread", generate_thread_async(trend, config, client, tier=gen_tier)
             if trend.viral_potential >= config.thread_min_score else None),
            ("blog", generate_blog_async(trend, config, client) if blog_enabled else None),
        ]:
            if coro is not None:
                try:
                    result_map[key] = await coro
                except Exception as exc:
                    result_map[key] = exc
    else:
        # 병렬 실행 경로 (기본)
        tasks: dict[str, asyncio.Task] = {}
        if threads_enabled:
            tasks["combined"] = asyncio.ensure_future(
                generate_tweets_and_threads_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                                 edape_block=edape_block)
            )
        else:
            tasks["tweets"] = asyncio.ensure_future(
                generate_tweets_async(trend, config, client, recent_tweets, golden_refs, pattern_weights,
                                      edape_block=edape_block)
            )
        if config.enable_long_form and trend.viral_potential >= config.long_form_min_score:
            tasks["long"] = asyncio.ensure_future(generate_long_form_async(trend, config, client, tier=gen_tier))
        if trend.viral_potential >= config.thread_min_score:
            tasks["thread"] = asyncio.ensure_future(generate_thread_async(trend, config, client, tier=gen_tier))
        if blog_enabled:
            tasks["blog"] = asyncio.ensure_future(generate_blog_async(trend, config, client))
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        result_map = dict(zip(keys, results, strict=False))"""

    new_body = """    if _PY314_SERIAL_GENERATION:
        result_map = await _run_serial_generation(
            trend, config, client, recent_tweets, golden_refs, pattern_weights,
            edape_block, threads_enabled, blog_enabled, gen_tier
        )
    else:
        result_map = await _run_parallel_generation(
            trend, config, client, recent_tweets, golden_refs, pattern_weights,
            edape_block, threads_enabled, blog_enabled, gen_tier
        )"""

    content = content.replace("async def generate_for_trend_async", new_helpers + "\nasync def generate_for_trend_async")
    content = content.replace(old_body, new_body)

    gen_file.write_text(content, encoding="utf-8")
    print("generator.py updated")

def refactor_main():
    main_file = Path("automation/getdaytrends/main.py")
    content2 = main_file.read_text(encoding="utf-8")

    old_args = """    if args.countries:
        countries = _normalize_countries(args.countries.split(","))
        config.country = countries[0]
        config.countries = countries
    elif args.country:
        config.country = args.country
        config.countries = [args.country]
    if args.limit:
        config.limit = args.limit
    if args.one_shot:
        config.one_shot = True
    if args.dry_run:
        config.dry_run = True
    if args.verbose:
        config.verbose = True
    if args.no_alerts:
        config.no_alerts = True
    if args.schedule_min:
        config.schedule_minutes = args.schedule_min"""

    new_overrides_func = """def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> None:
    if args.countries:
        countries = _normalize_countries(args.countries.split(","))
        config.country = countries[0]
        config.countries = countries
    elif args.country:
        config.country = args.country
        config.countries = [args.country]
    if args.limit:
        config.limit = args.limit
    if args.one_shot:
        config.one_shot = True
    if args.dry_run:
        config.dry_run = True
    if args.verbose:
        config.verbose = True
    if args.no_alerts:
        config.no_alerts = True
    if args.schedule_min:
        config.schedule_minutes = args.schedule_min

"""
    content2 = content2.replace("def _main_body():\n", new_overrides_func + "def _main_body():\n")
    content2 = content2.replace(old_args, "    _apply_cli_overrides(config, args)")

    old_loop = """        while not _SHUTDOWN_FLAG.is_set():
            # 야간 슬립: 02:00~07:00 사이 실행 건너뜀
            if config.night_mode:
                now_hour = datetime.now().hour
                if 2 <= now_hour < 7:
                    wake_at = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
                    sleep_seconds = max(0, (wake_at - datetime.now()).total_seconds())  # BUG-013 fix: guard against negative
                    if sleep_seconds > 0:
                        log.info(f"야간 슬립: 07:00까지 {sleep_seconds/60:.0f}분 대기")
                        print(f"  야간 슬립 중... (07:00 기상, {sleep_seconds/60:.0f}분 후)")
                        for _ in range(int(sleep_seconds)):
                            if _SHUTDOWN_FLAG.is_set():
                                break
                            time.sleep(1)
                        continue

            schedule.run_pending()
            time.sleep(1)"""

    new_sleep_func = """def _sleep_with_interrupt(sleep_seconds: float):
    for _ in range(int(sleep_seconds)):
        if _SHUTDOWN_FLAG.is_set():
            break
        time.sleep(1)

def _get_night_sleep_seconds() -> float:
    now = datetime.now()
    if 2 <= now.hour < 7:
        wake_at = now.replace(hour=7, minute=0, second=0, microsecond=0)
        return max(0.0, (wake_at - now).total_seconds())
    return 0.0

"""

    new_loop = """        while not _SHUTDOWN_FLAG.is_set():
            if config.night_mode:
                sleep_seconds = _get_night_sleep_seconds()
                if sleep_seconds > 0:
                    log.info(f"야간 슬립: 07:00까지 {sleep_seconds/60:.0f}분 대기")
                    print(f"  야간 슬립 중... (07:00 기상, {sleep_seconds/60:.0f}분 후)")
                    _sleep_with_interrupt(sleep_seconds)
                    continue

            schedule.run_pending()
            time.sleep(1)"""

    # We need to insert new_sleep_func somewhere. Maybe before _main_body? It's fine to insert it at where the previous insert happened.
    content2 = content2.replace("def _apply_cli_overrides", new_sleep_func + "def _apply_cli_overrides")
    content2 = content2.replace(old_loop, new_loop)

    main_file.write_text(content2, encoding="utf-8")
    print("main.py updated")

if __name__ == "__main__":
    refactor_generator()
    refactor_main()

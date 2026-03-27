-- =========================================================================
-- DailyNews Database Optimization Script
-- =========================================================================
--
-- 이 스크립트는 SQLite 데이터베이스에 인덱스를 추가하여 쿼리 성능을 향상시킵니다.
--
-- 실행 방법:
--   sqlite3 "d:\AI 프로젝트\DailyNews\data\pipeline_state.db" < scripts/optimize_database.sql
--
-- 작성일: 2026-03-21
-- =========================================================================

-- 1. job_runs 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_job_runs_started_at
ON job_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_status
ON job_runs(status);

CREATE INDEX IF NOT EXISTS idx_job_runs_job_name
ON job_runs(job_name);

-- 2. article_cache 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_article_cache_link
ON article_cache(link);

CREATE INDEX IF NOT EXISTS idx_article_cache_collected_at
ON article_cache(collected_at DESC);

-- 3. llm_cache 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_llm_cache_prompt_hash
ON llm_cache(prompt_hash);

CREATE INDEX IF NOT EXISTS idx_llm_cache_created_at
ON llm_cache(created_at DESC);

-- 4. content_reports 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_content_reports_category
ON content_reports(category);

CREATE INDEX IF NOT EXISTS idx_content_reports_created_at
ON content_reports(created_at DESC);

-- 5. 분석 쿼리 확인
SELECT 'Indexes created successfully!' as status;

SELECT name, sql
FROM sqlite_master
WHERE type = 'index'
AND name LIKE 'idx_%'
ORDER BY name;

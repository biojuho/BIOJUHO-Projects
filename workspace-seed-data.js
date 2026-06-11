/* ================================================================
 * JooPark Workspace — initial dashboard seed data.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkWorkspaceSeedData(global) {
  "use strict";

  const VERSION = "joopark-workspace-seed-data/v1";

  function createWorkspaceSeedData(deps = {}) {
    const addDays = typeof deps.addDays === "function" ? deps.addDays : ((value) => value);
    return {
  currentView: "home",
  currentProjectId: "proj-radar",
  currentInstanceId: "db-prod-1",
  deletedItems: [],

  projects: [
    { id: "proj-radar", name: "OSS Radar v2", owner: "운영팀", progress: 72, status: "on-track", health: "green",
      deadline: "2026-07-10", burn: [10, 20, 30, 42, 55, 65, 72], risks: 1, openIssues: 14, members: ["jp", "sk", "mh"] },
    { id: "proj-data", name: "데이터 허브", owner: "데이터팀", progress: 48, status: "at-risk", health: "amber",
      deadline: "2026-06-20", burn: [5, 12, 22, 30, 38, 44, 48], risks: 3, openIssues: 22, members: ["sk", "yj"] },
    { id: "proj-docs", name: "Docs 파이프라인", owner: "문서팀", progress: 91, status: "on-track", health: "green",
      deadline: "2026-06-05", burn: [22, 40, 58, 70, 80, 87, 91], risks: 0, openIssues: 4, members: ["mh", "yj"] },
    { id: "proj-policy", name: "정책 허브", owner: "법무팀", progress: 34, status: "delayed", health: "red",
      deadline: "2026-06-12", burn: [4, 9, 15, 22, 27, 31, 34], risks: 4, openIssues: 9, members: ["jp", "yj"] },
    { id: "proj-mobile", name: "모바일 알림", owner: "프론트팀", progress: 58, status: "on-track", health: "green",
      deadline: "2026-07-25", burn: [8, 18, 28, 38, 46, 52, 58], risks: 1, openIssues: 11, members: ["sk", "mh", "hr"] },
    { id: "proj-billing", name: "결제 정산", owner: "결제팀", progress: 25, status: "at-risk", health: "amber",
      deadline: "2026-08-01", burn: [3, 6, 11, 15, 18, 22, 25], risks: 2, openIssues: 17, members: ["hr", "yj"] },
  ],

  issues: [
    { id: "PM-101", project: "proj-radar", title: "라이선스 보고서 자동화", status: "todo", priority: "high", assignee: "jp", labels: ["backend", "docs"], due: "2026-06-05", estimate: 5 },
    { id: "PM-102", project: "proj-radar", title: "PR 리뷰 자동 라우팅", status: "in-progress", priority: "med", assignee: "sk", labels: ["bot"], due: "2026-06-08", estimate: 8 },
    { id: "PM-103", project: "proj-radar", title: "라이선스 충돌 알림 채널", status: "review", priority: "high", assignee: "mh", labels: ["ops"], due: "2026-06-02", estimate: 3 },
    { id: "PM-104", project: "proj-radar", title: "주간 리포트 PDF 출력", status: "done", priority: "low", assignee: "jp", labels: ["docs"], due: "2026-05-25", estimate: 2 },
    { id: "PM-105", project: "proj-radar", title: "OSS 카탈로그 검색 캐시", status: "todo", priority: "med", assignee: "sk", labels: ["backend", "perf"], due: "2026-06-18", estimate: 5 },
    { id: "PM-106", project: "proj-radar", title: "운영자 권한 분리", status: "in-progress", priority: "crit", assignee: "jp", labels: ["security"], due: "2026-06-01", estimate: 4 },

    { id: "PM-201", project: "proj-data", title: "민감값 마스킹 룰", status: "review", priority: "crit", assignee: "yj", labels: ["security"], due: "2026-06-03", estimate: 3 },
    { id: "PM-202", project: "proj-data", title: "데이터 카탈로그 정합성", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: "2026-06-10", estimate: 6 },
    { id: "PM-203", project: "proj-data", title: "스키마 변경 감지", status: "todo", priority: "med", assignee: "sk", labels: ["backend"], due: "2026-06-15", estimate: 5 },
    { id: "PM-204", project: "proj-data", title: "샘플 데이터 자동 생성", status: "todo", priority: "low", assignee: "sk", labels: ["dev"], due: "2026-06-22", estimate: 2 },
    { id: "PM-205", project: "proj-data", title: "Airflow DAG 점검", status: "done", priority: "med", assignee: "yj", labels: ["data"], due: "2026-05-20", estimate: 4 },

    { id: "PM-301", project: "proj-docs", title: "한/영 번역 동기화", status: "in-progress", priority: "med", assignee: "mh", labels: ["docs", "i18n"], due: "2026-06-04", estimate: 5 },
    { id: "PM-302", project: "proj-docs", title: "API 레퍼런스 자동화", status: "done", priority: "high", assignee: "yj", labels: ["docs"], due: "2026-05-22", estimate: 4 },
    { id: "PM-303", project: "proj-docs", title: "튜토리얼 영상 캡션", status: "review", priority: "low", assignee: "mh", labels: ["docs", "media"], due: "2026-06-01", estimate: 2 },

    { id: "PM-401", project: "proj-policy", title: "GDPR 갭 분석 v2", status: "todo", priority: "crit", assignee: "jp", labels: ["compliance"], due: "2026-06-09", estimate: 7 },
    { id: "PM-402", project: "proj-policy", title: "동의서 템플릿 표준화", status: "in-progress", priority: "high", assignee: "yj", labels: ["legal"], due: "2026-06-12", estimate: 5 },
    { id: "PM-403", project: "proj-policy", title: "정책 변경 로그", status: "todo", priority: "med", assignee: "jp", labels: ["compliance"], due: "2026-06-20", estimate: 3 },

    { id: "PM-501", project: "proj-mobile", title: "푸시 채널 분리", status: "in-progress", priority: "high", assignee: "sk", labels: ["mobile"], due: "2026-06-15", estimate: 5 },
    { id: "PM-502", project: "proj-mobile", title: "다크 모드 토큰", status: "review", priority: "low", assignee: "mh", labels: ["ui"], due: "2026-06-08", estimate: 2 },
    { id: "PM-503", project: "proj-mobile", title: "에러 추적 SDK 통합", status: "todo", priority: "med", assignee: "hr", labels: ["mobile", "ops"], due: "2026-06-25", estimate: 4 },
    { id: "PM-504", project: "proj-mobile", title: "알림 클릭 트래킹", status: "todo", priority: "med", assignee: "sk", labels: ["mobile"], due: "2026-07-01", estimate: 3 },
    { id: "PM-505", project: "proj-mobile", title: "iOS 16 호환성", status: "done", priority: "high", assignee: "hr", labels: ["mobile"], due: "2026-05-28", estimate: 4 },

    { id: "PM-601", project: "proj-billing", title: "환불 트랜잭션 격리", status: "review", priority: "crit", assignee: "hr", labels: ["billing"], due: "2026-06-06", estimate: 5 },
    { id: "PM-602", project: "proj-billing", title: "월간 정산 리포트", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: "2026-06-30", estimate: 8 },
    { id: "PM-603", project: "proj-billing", title: "세금 코드 매핑", status: "todo", priority: "high", assignee: "hr", labels: ["billing", "compliance"], due: "2026-07-05", estimate: 6 },
    { id: "PM-604", project: "proj-billing", title: "결제 실패 재시도", status: "todo", priority: "med", assignee: "hr", labels: ["billing"], due: "2026-07-10", estimate: 3 },
    { id: "PM-605", project: "proj-billing", title: "PG 사 라우팅 룰", status: "todo", priority: "low", assignee: "yj", labels: ["billing"], due: "2026-07-15", estimate: 2 },
  ],

  gantt: {
    rangeStart: "2026-05-01",
    rangeEnd: "2026-08-01",
    tasks: [
      { id: "T1",  project: "proj-radar",   name: "요구 정리",         start: "2026-05-01", end: "2026-05-14", owner: "jp", deps: [],          milestone: false, color: "blue" },
      { id: "T2",  project: "proj-radar",   name: "스키마 설계",       start: "2026-05-10", end: "2026-05-28", owner: "sk", deps: ["T1"],      milestone: false, color: "blue" },
      { id: "T3",  project: "proj-radar",   name: "API 구현",          start: "2026-05-28", end: "2026-06-20", owner: "sk", deps: ["T2"],      milestone: false, color: "blue" },
      { id: "M1",  project: "proj-radar",   name: "베타 마일스톤",     start: "2026-06-20", end: "2026-06-20", owner: "jp", deps: ["T3"],      milestone: true,  color: "blue" },
      { id: "T4",  project: "proj-radar",   name: "QA & 문서",         start: "2026-06-20", end: "2026-07-10", owner: "mh", deps: ["M1"],      milestone: false, color: "blue" },

      { id: "T5",  project: "proj-data",    name: "파이프라인 설계",   start: "2026-05-05", end: "2026-05-22", owner: "yj", deps: [],          milestone: false, color: "cyan" },
      { id: "T6",  project: "proj-data",    name: "마스킹 룰 구현",    start: "2026-05-22", end: "2026-06-10", owner: "yj", deps: ["T5"],      milestone: false, color: "cyan" },
      { id: "M2",  project: "proj-data",    name: "데이터 GA",         start: "2026-06-20", end: "2026-06-20", owner: "yj", deps: ["T6"],      milestone: true,  color: "cyan" },

      { id: "T7",  project: "proj-docs",    name: "번역 동기화",       start: "2026-05-12", end: "2026-06-04", owner: "mh", deps: [],          milestone: false, color: "violet" },
      { id: "T8",  project: "proj-docs",    name: "API 레퍼런스",      start: "2026-05-01", end: "2026-05-22", owner: "yj", deps: [],          milestone: false, color: "violet" },

      { id: "T9",  project: "proj-policy",  name: "GDPR 갭 분석",      start: "2026-05-20", end: "2026-06-09", owner: "jp", deps: [],          milestone: false, color: "amber" },
      { id: "T10", project: "proj-policy",  name: "동의서 표준화",     start: "2026-05-25", end: "2026-06-12", owner: "yj", deps: [],          milestone: false, color: "amber" },
      { id: "M3",  project: "proj-policy",  name: "정책 v3 공개",      start: "2026-06-25", end: "2026-06-25", owner: "jp", deps: ["T10"],     milestone: true,  color: "amber" },

      { id: "T11", project: "proj-mobile",  name: "푸시 채널 분리",    start: "2026-05-15", end: "2026-06-15", owner: "sk", deps: [],          milestone: false, color: "green" },
      { id: "T12", project: "proj-mobile",  name: "다크 모드 토큰",    start: "2026-05-28", end: "2026-06-08", owner: "mh", deps: [],          milestone: false, color: "green" },
      { id: "T13", project: "proj-mobile",  name: "SDK 통합",          start: "2026-06-15", end: "2026-07-01", owner: "hr", deps: ["T11"],     milestone: false, color: "green" },

      { id: "T14", project: "proj-billing", name: "환불 격리",         start: "2026-05-18", end: "2026-06-06", owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T15", project: "proj-billing", name: "정산 리포트",       start: "2026-06-06", end: "2026-06-30", owner: "yj", deps: ["T14"],     milestone: false, color: "red" },
      { id: "T16", project: "proj-billing", name: "세금 매핑",         start: "2026-06-15", end: "2026-07-05", owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T17", project: "proj-billing", name: "재시도 로직",       start: "2026-07-05", end: "2026-07-20", owner: "hr", deps: ["T16"],     milestone: false, color: "red" },
    ],
  },

  team: [
    { id: "jp", name: "박주호", role: "PM",       load: 78, projects: ["proj-radar", "proj-policy"], onLeave: false },
    { id: "sk", name: "서기태", role: "Backend",  load: 92, projects: ["proj-radar", "proj-data", "proj-mobile"], onLeave: false },
    { id: "mh", name: "문하늘", role: "Design",   load: 35, projects: ["proj-radar", "proj-docs", "proj-mobile"], onLeave: false },
    { id: "yj", name: "윤재민", role: "Data",     load: 84, projects: ["proj-data", "proj-docs", "proj-policy", "proj-billing"], onLeave: false },
    { id: "hr", name: "한혜린", role: "Mobile",   load: 71, projects: ["proj-mobile", "proj-billing"], onLeave: false },
    { id: "do", name: "도민재", role: "Frontend", load: 0,  projects: [],                              onLeave: true  },
    { id: "ks", name: "강서윤", role: "QA",       load: 48, projects: ["proj-radar", "proj-mobile"], onLeave: false },
    { id: "nm", name: "남명진", role: "DevOps",   load: 62, projects: ["proj-radar", "proj-data", "proj-billing"], onLeave: false },
  ],

  dbInstances: [
    { id: "db-prod-1",  name: "prod-postgres-01",  engine: "PostgreSQL 15.3", region: "ap-northeast-2", cpu: 42, mem: 68, conn: 184, connMax: 300,  health: "green", latencyMs: 12, series: [20, 22, 28, 34, 30, 38, 42] },
    { id: "db-prod-2",  name: "prod-redis-01",     engine: "Redis 7.2.4",     region: "ap-northeast-2", cpu: 18, mem: 35, conn: 512, connMax: 2000, health: "green", latencyMs: 1,  series: [12, 14, 15, 15, 17, 18, 18] },
    { id: "db-stage-1", name: "stage-postgres-01", engine: "PostgreSQL 15.3", region: "ap-northeast-2", cpu: 88, mem: 74, conn: 240, connMax: 300,  health: "amber", latencyMs: 38, series: [60, 72, 80, 84, 85, 86, 88] },
    { id: "db-dev-1",   name: "dev-postgres-01",   engine: "PostgreSQL 14.9", region: "ap-northeast-2", cpu: 9,  mem: 21, conn: 8,   connMax: 100,  health: "green", latencyMs: 4,  series: [6, 7, 7, 8, 8, 9, 9] },
  ],

  schemas: [
    { id: "db-prod-1", databases: [
      { name: "radar", tables: [
        { id: "t-radar-users",    name: "users",          rows: 18342, sizeMb: 62,
          columns: [
            { name: "id",         type: "bigint",       pk: true,  nullable: false },
            { name: "email",      type: "text",         nullable: false, idx: ["uniq_email"] },
            { name: "name",       type: "text",         nullable: true },
            { name: "role",       type: "text",         nullable: false },
            { name: "created_at", type: "timestamptz",  nullable: false },
          ],
          indexes: [{ name: "uniq_email", cols: ["email"], unique: true }],
          fks: [] },
        { id: "t-radar-repos",    name: "repositories",   rows: 4012, sizeMb: 18,
          columns: [
            { name: "id",         type: "bigint", pk: true },
            { name: "owner_id",   type: "bigint", fk: "users.id", nullable: false },
            { name: "name",       type: "text",   nullable: false },
            { name: "license",    type: "text",   nullable: true },
            { name: "created_at", type: "timestamptz", nullable: false },
          ],
          indexes: [{ name: "idx_owner", cols: ["owner_id"] }],
          fks: [{ col: "owner_id", refs: "users.id" }] },
        { id: "t-radar-issues",   name: "issues",         rows: 22018, sizeMb: 41,
          columns: [
            { name: "id",       type: "bigint", pk: true },
            { name: "repo_id",  type: "bigint", fk: "repositories.id", nullable: false },
            { name: "title",    type: "text",   nullable: false },
            { name: "status",   type: "text",   nullable: false },
            { name: "priority", type: "text",   nullable: false },
            { name: "due_at",   type: "timestamptz", nullable: true },
          ],
          indexes: [{ name: "idx_repo_status", cols: ["repo_id", "status"] }],
          fks: [{ col: "repo_id", refs: "repositories.id" }] },
        { id: "t-radar-licenses", name: "licenses",       rows: 312, sizeMb: 1,
          columns: [
            { name: "spdx_id", type: "text", pk: true },
            { name: "name",   type: "text", nullable: false },
            { name: "kind",   type: "text", nullable: false },
          ],
          indexes: [],
          fks: [] },
        { id: "t-radar-audit", name: "audit_log",         rows: 184012, sizeMb: 412,
          columns: [
            { name: "id",        type: "bigserial", pk: true },
            { name: "actor_id",  type: "bigint",    fk: "users.id" },
            { name: "action",    type: "text" },
            { name: "object",    type: "text" },
            { name: "at",        type: "timestamptz", nullable: false },
          ],
          indexes: [{ name: "idx_audit_at", cols: ["at"] }],
          fks: [{ col: "actor_id", refs: "users.id" }] },
      ] },
      { name: "billing", tables: [
        { id: "t-bill-orders",   name: "orders",          rows: 92341, sizeMb: 184,
          columns: [
            { name: "id",        type: "bigint", pk: true },
            { name: "user_id",   type: "bigint", fk: "radar.users.id" },
            { name: "amount",    type: "numeric(12,2)" },
            { name: "currency",  type: "char(3)" },
            { name: "status",    type: "text" },
            { name: "created_at",type: "timestamptz" },
          ],
          indexes: [{ name: "idx_user", cols: ["user_id"] }, { name: "idx_status", cols: ["status"] }],
          fks: [{ col: "user_id", refs: "radar.users.id" }] },
        { id: "t-bill-refunds",  name: "refunds",         rows: 1240, sizeMb: 8,
          columns: [
            { name: "id",        type: "bigint", pk: true },
            { name: "order_id",  type: "bigint", fk: "orders.id" },
            { name: "reason",    type: "text" },
            { name: "amount",    type: "numeric(12,2)" },
            { name: "created_at",type: "timestamptz" },
          ],
          indexes: [{ name: "idx_order", cols: ["order_id"] }],
          fks: [{ col: "order_id", refs: "orders.id" }] },
        { id: "t-bill-tax",      name: "tax_rates",       rows: 412, sizeMb: 1,
          columns: [
            { name: "code", type: "text", pk: true },
            { name: "rate", type: "numeric(6,4)" },
            { name: "region", type: "text" },
          ],
          indexes: [],
          fks: [] },
      ] },
    ] },
    { id: "db-prod-2", databases: [
      { name: "cache", tables: [
        { id: "t-cache-sess",   name: "sessions:*",        rows: 12842, sizeMb: 22, columns: [{ name: "key", type: "string" }, { name: "ttl", type: "seconds" }, { name: "value", type: "json" }], indexes: [], fks: [] },
        { id: "t-cache-queue",  name: "queue:notifications", rows: 1240, sizeMb: 3, columns: [{ name: "id", type: "stream" }, { name: "payload", type: "json" }], indexes: [], fks: [] },
        { id: "t-cache-rate",   name: "rate:user:*",       rows: 4920, sizeMb: 5, columns: [{ name: "key", type: "string" }, { name: "count", type: "int" }], indexes: [], fks: [] },
      ] },
    ] },
    { id: "db-stage-1", databases: [
      { name: "radar_stage", tables: [
        { id: "t-stage-users",  name: "users",         rows: 184, sizeMb: 1,  columns: [{ name: "id", type: "bigint", pk: true }, { name: "email", type: "text" }, { name: "name", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-repos",  name: "repositories",  rows: 42, sizeMb: 1,   columns: [{ name: "id", type: "bigint", pk: true }, { name: "owner_id", type: "bigint" }, { name: "name", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-issues", name: "issues",        rows: 220, sizeMb: 1,  columns: [{ name: "id", type: "bigint", pk: true }, { name: "repo_id", type: "bigint" }, { name: "status", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-flags",  name: "feature_flags", rows: 28, sizeMb: 1,   columns: [{ name: "key", type: "text", pk: true }, { name: "enabled", type: "bool" }], indexes: [], fks: [] },
      ] },
    ] },
    { id: "db-dev-1", databases: [
      { name: "scratch", tables: [
        { id: "t-dev-test", name: "test_runs", rows: 18, sizeMb: 1, columns: [{ name: "id", type: "bigint", pk: true }, { name: "ran_at", type: "timestamptz" }], indexes: [], fks: [] },
      ] },
    ] },
  ],

  queries: [
    { id: "Q1",  instance: "db-prod-1",  db: "radar",   text: "SELECT r.*, u.email FROM repositories r JOIN users u ON u.id = r.owner_id WHERE r.license IS NULL", avgMs: 1280, p95Ms: 2100, count: 42,  lastRun: "2026-05-29 09:14", planHint: "seq scan on repositories" },
    { id: "Q2",  instance: "db-stage-1", db: "radar",   text: "UPDATE issues SET status = $1 WHERE repo_id = $2 AND due_at < NOW()",                              avgMs: 980,  p95Ms: 1450, count: 118, lastRun: "2026-05-29 09:11", planHint: "missing idx on (repo_id, due_at)" },
    { id: "Q3",  instance: "db-prod-1",  db: "billing", text: "SELECT o.id, SUM(o.amount) FROM orders o WHERE o.created_at > now() - interval '30 days' GROUP BY o.id", avgMs: 740, p95Ms: 1200, count: 32, lastRun: "2026-05-29 09:09", planHint: "consider materialized view" },
    { id: "Q4",  instance: "db-prod-1",  db: "radar",   text: "SELECT * FROM audit_log WHERE at > NOW() - interval '1 hour' ORDER BY at DESC LIMIT 200",            avgMs: 612,  p95Ms: 980,  count: 84,  lastRun: "2026-05-29 09:08", planHint: "OK (idx_audit_at)" },
    { id: "Q5",  instance: "db-prod-1",  db: "radar",   text: "SELECT count(*) FROM issues WHERE status = 'todo' AND priority IN ('high','crit')",                  avgMs: 540,  p95Ms: 820,  count: 240, lastRun: "2026-05-29 09:07", planHint: "consider partial idx" },
    { id: "Q6",  instance: "db-stage-1", db: "radar",   text: "INSERT INTO issues(...) SELECT ... FROM staging_issues",                                              avgMs: 488,  p95Ms: 720,  count: 6,   lastRun: "2026-05-29 02:00", planHint: "batch insert" },
    { id: "Q7",  instance: "db-prod-1",  db: "billing", text: "SELECT * FROM orders WHERE status = 'failed' AND created_at > now() - interval '24h'",               avgMs: 420,  p95Ms: 640,  count: 64,  lastRun: "2026-05-29 09:05", planHint: "OK (idx_status)" },
    { id: "Q8",  instance: "db-prod-1",  db: "radar",   text: "DELETE FROM audit_log WHERE at < now() - interval '90 days'",                                        avgMs: 380,  p95Ms: 580,  count: 1,   lastRun: "2026-05-29 03:00", planHint: "scheduled cleanup" },
    { id: "Q9",  instance: "db-dev-1",   db: "scratch", text: "SELECT * FROM test_runs ORDER BY ran_at DESC LIMIT 100",                                             avgMs: 320,  p95Ms: 480,  count: 22,  lastRun: "2026-05-29 08:42", planHint: "OK" },
    { id: "Q10", instance: "db-prod-1",  db: "billing", text: "SELECT r.id FROM refunds r WHERE r.created_at > $1 ORDER BY r.amount DESC",                          avgMs: 270,  p95Ms: 400,  count: 18,  lastRun: "2026-05-29 09:01", planHint: "OK (idx_order)" },
    { id: "Q11", instance: "db-stage-1", db: "radar",   text: "VACUUM ANALYZE issues",                                                                              avgMs: 240,  p95Ms: 320,  count: 1,   lastRun: "2026-05-29 04:00", planHint: "scheduled maintenance" },
    { id: "Q12", instance: "db-prod-1",  db: "radar",   text: "SELECT spdx_id FROM licenses WHERE kind = $1",                                                       avgMs: 210,  p95Ms: 300,  count: 920, lastRun: "2026-05-29 09:14", planHint: "lookup" },
  ],

  queryHistogram: [
    { bucket: "<10",     count: 1820 },
    { bucket: "10-50",   count: 940 },
    { bucket: "50-100",  count: 612 },
    { bucket: "100-200", count: 412 },
    { bucket: "200-400", count: 280 },
    { bucket: "400-600", count: 184 },
    { bucket: "600-800", count: 120 },
    { bucket: "0.8-1s",  count: 82  },
    { bucket: "1-2s",    count: 42  },
    { bucket: "2-5s",    count: 14  },
    { bucket: "5-10s",   count: 4   },
    { bucket: ">10s",    count: 1   },
  ],

  backups: (function () {
    const out = [];
    const instances = ["db-prod-1", "db-prod-2", "db-stage-1", "db-dev-1"];
    const start = "2026-05-01";
    for (let d = 0; d < 30; d++) {
      const date = addDays(start, d);
      instances.forEach((inst) => {
        // Deterministic pattern: most ok, some warn, rare fail
        const key = (d * 7 + inst.length) % 23;
        let status = "ok";
        let note = "";
        if (key === 0) { status = "fail"; note = "디스크 부족"; }
        else if (key === 3 || key === 14) { status = "warn"; note = "느린 I/O"; }
        const sizeMb = status === "fail" ? 0 : (inst === "db-prod-1" ? 1800 + (d * 6) : inst === "db-prod-2" ? 420 + d : inst === "db-stage-1" ? 380 + d * 2 : 80 + d);
        const durationS = status === "fail" ? 0 : (inst === "db-prod-1" ? 42 + (key % 5) * 8 : 8 + (key % 4) * 3);
        out.push({ date, instance: inst, status, sizeMb, durationS, note });
      });
    }
    return out;
  })(),

  migrations: [
    { id: "M-2026-05-12-01", instance: "db-prod-1",  title: "add issues.priority", status: "applied",  appliedAt: "2026-05-12 02:05", rolledBack: false },
    { id: "M-2026-05-15-01", instance: "db-prod-1",  title: "create index idx_audit_at", status: "applied", appliedAt: "2026-05-15 02:02", rolledBack: false },
    { id: "M-2026-05-20-01", instance: "db-prod-1",  title: "add billing.refunds.reason", status: "applied", appliedAt: "2026-05-20 02:04", rolledBack: false },
    { id: "M-2026-05-25-03", instance: "db-stage-1", title: "drop users.legacy_token",  status: "pending",  scheduledAt: "2026-05-30 02:00" },
    { id: "M-2026-05-28-01", instance: "db-prod-1",  title: "alter audit_log.actor_id nullable",  status: "review",   author: "jp" },
    { id: "M-2026-05-28-02", instance: "db-stage-1", title: "feature flag table bootstrap", status: "applied", appliedAt: "2026-05-28 02:10", rolledBack: false },
    { id: "M-2026-05-29-01", instance: "db-prod-1",  title: "create materialized view monthly_orders", status: "pending", scheduledAt: "2026-05-31 02:00" },
    { id: "M-2026-05-29-02", instance: "db-prod-1",  title: "drop audit_log.legacy",   status: "rolled-back", appliedAt: "2026-05-26 02:00", rolledBack: true, rollbackReason: "타이밍 충돌로 롤백" },
  ],

  projects_list_for_picker: null, // computed below in setup if needed
};
  }

  global.JooParkWorkspaceSeedData = Object.freeze({
    version: VERSION,
    create: createWorkspaceSeedData,
  });
})(typeof window !== "undefined" ? window : globalThis);

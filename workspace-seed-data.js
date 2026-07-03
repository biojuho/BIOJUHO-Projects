/* ================================================================
 * JooPark Workspace — initial dashboard seed data.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkWorkspaceSeedData(global) {
  "use strict";

  const VERSION = "joopark-workspace-seed-data/v1";

  function createWorkspaceSeedData(deps = {}) {
    const addDays = typeof deps.addDays === "function" ? deps.addDays : ((value) => value);
    // Seed dates are offsets from today so a first run always looks like a
    // live workspace instead of a demo frozen at its authoring date.
    // deps.today lets tests pin the anchor; the runtime derives it locally.
    const today = typeof deps.today === "string" && deps.today
      ? deps.today
      : (function () {
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      })();
    const day = (offset) => addDays(today, offset);
    const dayAt = (offset, time) => `${addDays(today, offset)} ${time}`;
    return {
  currentView: "home",
  currentProjectId: "proj-radar",
  currentInstanceId: "db-prod-1",
  deletedItems: [],

  projects: [
    { id: "proj-radar", name: "OSS Radar v2", owner: "운영팀", progress: 72, status: "on-track", health: "green",
      deadline: day(42), burn: [10, 20, 30, 42, 55, 65, 72], risks: 1, openIssues: 14, members: ["jp", "sk", "mh"] },
    { id: "proj-data", name: "데이터 허브", owner: "데이터팀", progress: 48, status: "at-risk", health: "amber",
      deadline: day(22), burn: [5, 12, 22, 30, 38, 44, 48], risks: 3, openIssues: 22, members: ["sk", "yj"] },
    { id: "proj-docs", name: "Docs 파이프라인", owner: "문서팀", progress: 91, status: "on-track", health: "green",
      deadline: day(7), burn: [22, 40, 58, 70, 80, 87, 91], risks: 0, openIssues: 4, members: ["mh", "yj"] },
    { id: "proj-policy", name: "정책 허브", owner: "법무팀", progress: 34, status: "delayed", health: "red",
      deadline: day(14), burn: [4, 9, 15, 22, 27, 31, 34], risks: 4, openIssues: 9, members: ["jp", "yj"] },
    { id: "proj-mobile", name: "모바일 알림", owner: "프론트팀", progress: 58, status: "on-track", health: "green",
      deadline: day(57), burn: [8, 18, 28, 38, 46, 52, 58], risks: 1, openIssues: 11, members: ["sk", "mh", "hr"] },
    { id: "proj-billing", name: "결제 정산", owner: "결제팀", progress: 25, status: "at-risk", health: "amber",
      deadline: day(64), burn: [3, 6, 11, 15, 18, 22, 25], risks: 2, openIssues: 17, members: ["hr", "yj"] },
  ],

  issues: [
    { id: "PM-101", project: "proj-radar", title: "라이선스 보고서 자동화", status: "todo", priority: "high", assignee: "jp", labels: ["backend", "docs"], due: day(7), estimate: 5 },
    { id: "PM-102", project: "proj-radar", title: "PR 리뷰 자동 라우팅", status: "in-progress", priority: "med", assignee: "sk", labels: ["bot"], due: day(10), estimate: 8 },
    { id: "PM-103", project: "proj-radar", title: "라이선스 충돌 알림 채널", status: "review", priority: "high", assignee: "mh", labels: ["ops"], due: day(4), estimate: 3 },
    { id: "PM-104", project: "proj-radar", title: "주간 리포트 PDF 출력", status: "done", priority: "low", assignee: "jp", labels: ["docs"], due: day(-4), estimate: 2 },
    { id: "PM-105", project: "proj-radar", title: "OSS 카탈로그 검색 캐시", status: "todo", priority: "med", assignee: "sk", labels: ["backend", "perf"], due: day(20), estimate: 5 },
    // 의도된 연체 데모: crit 이슈가 기한을 넘긴 채 진행 중인 상태를 보여준다.
    { id: "PM-106", project: "proj-radar", title: "운영자 권한 분리", status: "in-progress", priority: "crit", assignee: "jp", labels: ["security"], due: day(-3), estimate: 4 },

    { id: "PM-201", project: "proj-data", title: "민감값 마스킹 룰", status: "review", priority: "crit", assignee: "yj", labels: ["security"], due: day(5), estimate: 3 },
    { id: "PM-202", project: "proj-data", title: "데이터 카탈로그 정합성", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: day(12), estimate: 6 },
    { id: "PM-203", project: "proj-data", title: "스키마 변경 감지", status: "todo", priority: "med", assignee: "sk", labels: ["backend"], due: day(17), estimate: 5 },
    { id: "PM-204", project: "proj-data", title: "샘플 데이터 자동 생성", status: "todo", priority: "low", assignee: "sk", labels: ["dev"], due: day(24), estimate: 2 },
    { id: "PM-205", project: "proj-data", title: "Airflow DAG 점검", status: "done", priority: "med", assignee: "yj", labels: ["data"], due: day(-9), estimate: 4 },

    { id: "PM-301", project: "proj-docs", title: "한/영 번역 동기화", status: "in-progress", priority: "med", assignee: "mh", labels: ["docs", "i18n"], due: day(6), estimate: 5 },
    { id: "PM-302", project: "proj-docs", title: "API 레퍼런스 자동화", status: "done", priority: "high", assignee: "yj", labels: ["docs"], due: day(-7), estimate: 4 },
    { id: "PM-303", project: "proj-docs", title: "튜토리얼 영상 캡션", status: "review", priority: "low", assignee: "mh", labels: ["docs", "media"], due: day(3), estimate: 2 },

    { id: "PM-401", project: "proj-policy", title: "GDPR 갭 분석 v2", status: "todo", priority: "crit", assignee: "jp", labels: ["compliance"], due: day(11), estimate: 7 },
    { id: "PM-402", project: "proj-policy", title: "동의서 템플릿 표준화", status: "in-progress", priority: "high", assignee: "yj", labels: ["legal"], due: day(14), estimate: 5 },
    { id: "PM-403", project: "proj-policy", title: "정책 변경 로그", status: "todo", priority: "med", assignee: "jp", labels: ["compliance"], due: day(22), estimate: 3 },

    { id: "PM-501", project: "proj-mobile", title: "푸시 채널 분리", status: "in-progress", priority: "high", assignee: "sk", labels: ["mobile"], due: day(17), estimate: 5 },
    { id: "PM-502", project: "proj-mobile", title: "다크 모드 토큰", status: "review", priority: "low", assignee: "mh", labels: ["ui"], due: day(10), estimate: 2 },
    { id: "PM-503", project: "proj-mobile", title: "에러 추적 SDK 통합", status: "todo", priority: "med", assignee: "hr", labels: ["mobile", "ops"], due: day(27), estimate: 4 },
    { id: "PM-504", project: "proj-mobile", title: "알림 클릭 트래킹", status: "todo", priority: "med", assignee: "sk", labels: ["mobile"], due: day(33), estimate: 3 },
    { id: "PM-505", project: "proj-mobile", title: "iOS 16 호환성", status: "done", priority: "high", assignee: "hr", labels: ["mobile"], due: day(-1), estimate: 4 },

    { id: "PM-601", project: "proj-billing", title: "환불 트랜잭션 격리", status: "review", priority: "crit", assignee: "hr", labels: ["billing"], due: day(8), estimate: 5 },
    { id: "PM-602", project: "proj-billing", title: "월간 정산 리포트", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: day(32), estimate: 8 },
    { id: "PM-603", project: "proj-billing", title: "세금 코드 매핑", status: "todo", priority: "high", assignee: "hr", labels: ["billing", "compliance"], due: day(37), estimate: 6 },
    { id: "PM-604", project: "proj-billing", title: "결제 실패 재시도", status: "todo", priority: "med", assignee: "hr", labels: ["billing"], due: day(42), estimate: 3 },
    { id: "PM-605", project: "proj-billing", title: "PG 사 라우팅 룰", status: "todo", priority: "low", assignee: "yj", labels: ["billing"], due: day(47), estimate: 2 },
  ],

  gantt: {
    rangeStart: day(-28),
    rangeEnd: day(64),
    tasks: [
      { id: "T1",  project: "proj-radar",   name: "요구 정리",         start: day(-28), end: day(-15), owner: "jp", deps: [],          milestone: false, color: "blue" },
      { id: "T2",  project: "proj-radar",   name: "스키마 설계",       start: day(-19), end: day(-1),  owner: "sk", deps: ["T1"],      milestone: false, color: "blue" },
      { id: "T3",  project: "proj-radar",   name: "API 구현",          start: day(-1),  end: day(22),  owner: "sk", deps: ["T2"],      milestone: false, color: "blue" },
      { id: "M1",  project: "proj-radar",   name: "베타 마일스톤",     start: day(22),  end: day(22),  owner: "jp", deps: ["T3"],      milestone: true,  color: "blue" },
      { id: "T4",  project: "proj-radar",   name: "QA & 문서",         start: day(22),  end: day(42),  owner: "mh", deps: ["M1"],      milestone: false, color: "blue" },

      { id: "T5",  project: "proj-data",    name: "파이프라인 설계",   start: day(-24), end: day(-7),  owner: "yj", deps: [],          milestone: false, color: "cyan" },
      { id: "T6",  project: "proj-data",    name: "마스킹 룰 구현",    start: day(-7),  end: day(12),  owner: "yj", deps: ["T5"],      milestone: false, color: "cyan" },
      { id: "M2",  project: "proj-data",    name: "데이터 GA",         start: day(22),  end: day(22),  owner: "yj", deps: ["T6"],      milestone: true,  color: "cyan" },

      { id: "T7",  project: "proj-docs",    name: "번역 동기화",       start: day(-17), end: day(6),   owner: "mh", deps: [],          milestone: false, color: "violet" },
      { id: "T8",  project: "proj-docs",    name: "API 레퍼런스",      start: day(-28), end: day(-7),  owner: "yj", deps: [],          milestone: false, color: "violet" },

      { id: "T9",  project: "proj-policy",  name: "GDPR 갭 분석",      start: day(-9),  end: day(11),  owner: "jp", deps: [],          milestone: false, color: "amber" },
      { id: "T10", project: "proj-policy",  name: "동의서 표준화",     start: day(-4),  end: day(14),  owner: "yj", deps: [],          milestone: false, color: "amber" },
      { id: "M3",  project: "proj-policy",  name: "정책 v3 공개",      start: day(27),  end: day(27),  owner: "jp", deps: ["T10"],     milestone: true,  color: "amber" },

      { id: "T11", project: "proj-mobile",  name: "푸시 채널 분리",    start: day(-14), end: day(17),  owner: "sk", deps: [],          milestone: false, color: "green" },
      { id: "T12", project: "proj-mobile",  name: "다크 모드 토큰",    start: day(-1),  end: day(10),  owner: "mh", deps: [],          milestone: false, color: "green" },
      { id: "T13", project: "proj-mobile",  name: "SDK 통합",          start: day(17),  end: day(33),  owner: "hr", deps: ["T11"],     milestone: false, color: "green" },

      { id: "T14", project: "proj-billing", name: "환불 격리",         start: day(-11), end: day(8),   owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T15", project: "proj-billing", name: "정산 리포트",       start: day(8),   end: day(32),  owner: "yj", deps: ["T14"],     milestone: false, color: "red" },
      { id: "T16", project: "proj-billing", name: "세금 매핑",         start: day(17),  end: day(37),  owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T17", project: "proj-billing", name: "재시도 로직",       start: day(37),  end: day(52),  owner: "hr", deps: ["T16"],     milestone: false, color: "red" },
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

  // 제약 파이프라인 보드(pm-pipeline): 자산 × 워크스트림 2차원 매트릭스.
  // 공개 데모에는 비식별 샘플 데이터만 싣는다.
  pipeline: {
    assets: [
      { id: "RX101", name: "RX101", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
      { id: "RX201", name: "RX201", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
      { id: "RX202", name: "RX202", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
      { id: "PX301", name: "PX301 (샘플 프로그램)", modality: "비식별 바이오 의약품", indication: "샘플 적응증", targetConc: "비공개", stage: "preclinical" },
      { id: "RX302", name: "RX302", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
      { id: "RX401", name: "RX401", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
      { id: "RX601", name: "RX601", modality: "미정", indication: "미정", targetConc: "", stage: "planned" },
    ],
    cells: {
      "PX301:efficacy": {
        status: "preclinical",
        phaseLabel: "비임상 효능 샘플",
        owner: "효능팀",
        nextAction: "후속 연구 범위와 증거 패키지 검토",
        riskFlags: ["efficacy-signal"],
        lastUpdated: "2026-06-15",
        docLink: { category: "sample-pipeline", article: "sample-efficacy-study" },
        milestones: [
          { id: "m-protocol", label: "프로토콜 샘플 승인", date: null, done: true },
          { id: "m-run", label: "실행 단계 샘플 완료", date: null, done: true },
          { id: "m-review", label: "결과 리뷰 샘플", date: null, done: false },
        ],
        wbs: [
          { id: "EFF-1", name: "프로토콜·분석계획 정리", status: "done", owner: "효능팀", deps: [], children: [] },
          { id: "EFF-2", name: "샘플 실행 상태 점검", status: "done", owner: "효능팀", deps: ["EFF-1"], children: [] },
          { id: "EFF-3", name: "정성 결과 리뷰", status: "doing", owner: "효능팀", deps: ["EFF-2"], children: [
            { id: "EFF-3a", name: "효능 신호 요약", status: "done", owner: "효능팀", deps: [], children: [] },
            { id: "EFF-3b", name: "한계·리스크 기록", status: "doing", owner: "효능팀", deps: [], children: [] },
          ] },
          { id: "EFF-4", name: "후속 연구 범위 결정", status: "todo", owner: "PM", deps: ["EFF-3"], children: [] },
        ],
      },
      "PX301:CMC": {
        status: "preclinical",
        phaseLabel: "제제 개발 샘플",
        owner: "제제팀",
        nextAction: "QTPP/CQA 샘플 증거 보강",
        riskFlags: ["aggregation", "thermolability", "adsorption", "deamidation"],
        lastUpdated: "2026-06-15",
        docLink: { category: "sample-pipeline", article: "sample-formulation-plan" },
        milestones: [
          { id: "m-qtpp", label: "QTPP 샘플 확정", date: null, done: true },
          { id: "m-cqa", label: "CQA 샘플 정의", date: null, done: true },
          { id: "m-screen", label: "스크리닝 샘플 설계", date: null, done: false },
        ],
        wbs: [
          { id: "CMC-1", name: "QTPP 템플릿 정의", status: "done", owner: "제제팀", deps: [], children: [] },
          { id: "CMC-2", name: "주요 리스크 샘플 평가", status: "done", owner: "제제팀", deps: ["CMC-1"], children: [
            { id: "CMC-2a", name: "품질 리스크 기록", status: "done", owner: "제제팀", deps: [], children: [] },
            { id: "CMC-2b", name: "공정 리스크 기록", status: "done", owner: "제제팀", deps: [], children: [] },
          ] },
          { id: "CMC-3", name: "CQA 샘플 확정", status: "done", owner: "QA", deps: ["CMC-1"], children: [] },
          { id: "CMC-4", name: "스크리닝 계획 수립", status: "doing", owner: "제제팀", deps: ["CMC-2", "CMC-3"], children: [] },
        ],
      },
    },
  },

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
    { id: "Q1",  instance: "db-prod-1",  db: "radar",   text: "SELECT r.*, u.email FROM repositories r JOIN users u ON u.id = r.owner_id WHERE r.license IS NULL", avgMs: 1280, p95Ms: 2100, count: 42,  lastRun: dayAt(0, "09:14"), planHint: "seq scan on repositories" },
    { id: "Q2",  instance: "db-stage-1", db: "radar",   text: "UPDATE issues SET status = $1 WHERE repo_id = $2 AND due_at < NOW()",                              avgMs: 980,  p95Ms: 1450, count: 118, lastRun: dayAt(0, "09:11"), planHint: "missing idx on (repo_id, due_at)" },
    { id: "Q3",  instance: "db-prod-1",  db: "billing", text: "SELECT o.id, SUM(o.amount) FROM orders o WHERE o.created_at > now() - interval '30 days' GROUP BY o.id", avgMs: 740, p95Ms: 1200, count: 32, lastRun: dayAt(0, "09:09"), planHint: "consider materialized view" },
    { id: "Q4",  instance: "db-prod-1",  db: "radar",   text: "SELECT * FROM audit_log WHERE at > NOW() - interval '1 hour' ORDER BY at DESC LIMIT 200",            avgMs: 612,  p95Ms: 980,  count: 84,  lastRun: dayAt(0, "09:08"), planHint: "OK (idx_audit_at)" },
    { id: "Q5",  instance: "db-prod-1",  db: "radar",   text: "SELECT count(*) FROM issues WHERE status = 'todo' AND priority IN ('high','crit')",                  avgMs: 540,  p95Ms: 820,  count: 240, lastRun: dayAt(0, "09:07"), planHint: "consider partial idx" },
    { id: "Q6",  instance: "db-stage-1", db: "radar",   text: "INSERT INTO issues(...) SELECT ... FROM staging_issues",                                              avgMs: 488,  p95Ms: 720,  count: 6,   lastRun: dayAt(0, "02:00"), planHint: "batch insert" },
    { id: "Q7",  instance: "db-prod-1",  db: "billing", text: "SELECT * FROM orders WHERE status = 'failed' AND created_at > now() - interval '24h'",               avgMs: 420,  p95Ms: 640,  count: 64,  lastRun: dayAt(0, "09:05"), planHint: "OK (idx_status)" },
    { id: "Q8",  instance: "db-prod-1",  db: "radar",   text: "DELETE FROM audit_log WHERE at < now() - interval '90 days'",                                        avgMs: 380,  p95Ms: 580,  count: 1,   lastRun: dayAt(0, "03:00"), planHint: "scheduled cleanup" },
    { id: "Q9",  instance: "db-dev-1",   db: "scratch", text: "SELECT * FROM test_runs ORDER BY ran_at DESC LIMIT 100",                                             avgMs: 320,  p95Ms: 480,  count: 22,  lastRun: dayAt(0, "08:42"), planHint: "OK" },
    { id: "Q10", instance: "db-prod-1",  db: "billing", text: "SELECT r.id FROM refunds r WHERE r.created_at > $1 ORDER BY r.amount DESC",                          avgMs: 270,  p95Ms: 400,  count: 18,  lastRun: dayAt(0, "09:01"), planHint: "OK (idx_order)" },
    { id: "Q11", instance: "db-stage-1", db: "radar",   text: "VACUUM ANALYZE issues",                                                                              avgMs: 240,  p95Ms: 320,  count: 1,   lastRun: dayAt(0, "04:00"), planHint: "scheduled maintenance" },
    { id: "Q12", instance: "db-prod-1",  db: "radar",   text: "SELECT spdx_id FROM licenses WHERE kind = $1",                                                       avgMs: 210,  p95Ms: 300,  count: 920, lastRun: dayAt(0, "09:14"), planHint: "lookup" },
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
    const start = day(-29); // 30-day window ending today, so the latest backup is always fresh
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

  // 마이그레이션 ID는 불투명 식별자로 고정하고 appliedAt/scheduledAt만 오늘 기준 오프셋을 쓴다.
  migrations: [
    { id: "M-2026-05-12-01", instance: "db-prod-1",  title: "add issues.priority", status: "applied",  appliedAt: dayAt(-17, "02:05"), rolledBack: false },
    { id: "M-2026-05-15-01", instance: "db-prod-1",  title: "create index idx_audit_at", status: "applied", appliedAt: dayAt(-14, "02:02"), rolledBack: false },
    { id: "M-2026-05-20-01", instance: "db-prod-1",  title: "add billing.refunds.reason", status: "applied", appliedAt: dayAt(-9, "02:04"), rolledBack: false },
    { id: "M-2026-05-25-03", instance: "db-stage-1", title: "drop users.legacy_token",  status: "pending",  scheduledAt: dayAt(1, "02:00") },
    { id: "M-2026-05-28-01", instance: "db-prod-1",  title: "alter audit_log.actor_id nullable",  status: "review",   author: "jp" },
    { id: "M-2026-05-28-02", instance: "db-stage-1", title: "feature flag table bootstrap", status: "applied", appliedAt: dayAt(-1, "02:10"), rolledBack: false },
    { id: "M-2026-05-29-01", instance: "db-prod-1",  title: "create materialized view monthly_orders", status: "pending", scheduledAt: dayAt(2, "02:00") },
    { id: "M-2026-05-29-02", instance: "db-prod-1",  title: "drop audit_log.legacy",   status: "rolled-back", appliedAt: dayAt(-3, "02:00"), rolledBack: true, rollbackReason: "타이밍 충돌로 롤백" },
  ],

  projects_list_for_picker: null, // computed below in setup if needed
};
  }

  global.JooParkWorkspaceSeedData = Object.freeze({
    version: VERSION,
    create: createWorkspaceSeedData,
  });
})(typeof window !== "undefined" ? window : globalThis);

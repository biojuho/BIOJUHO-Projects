# AgriGuard Database Performance Benchmark

- Generated at: 2026-03-25T10:26:26.129157+00:00
- Rounds: 5
- SQLite DB: `D:\AI 프로젝트\AgriGuard\backend\agriguard.db`
- PostgreSQL: `postgresql://agriguard:***@localhost:5432/agriguard`

## Results

| Query | Category | SQLite (ms) | PostgreSQL (ms) | Speedup |
|-------|----------|-------------|-----------------|---------|
| COUNT all products | COUNT | 0.28 | 2.03 | [-] 0.1x |
| SELECT products with index | SELECT+INDEX | 0.52 | 2.31 | [-] 0.2x |
| JOIN products → tracking_events | JOIN+GROUP | 8.63 | 10.05 | [-] 0.9x |
| Recent tracking events | JOIN+ORDER | 13.78 | 13.82 | [-] 1.0x |
| User statistics | GROUP | 0.47 | 2.37 | [-] 0.2x |

## Notes

- Speedup > 1x means PostgreSQL is faster
- Results depend on data volume, indexing, and connection latency
- Current data volume: 16729 rows

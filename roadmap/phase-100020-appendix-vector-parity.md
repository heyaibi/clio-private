# Phase 100020 appendix: Vector backend parity ceilings

**Consumers:** Phase 100020 (persistence hooks), slice 100110 (dense/lexical index pipelines).

**Parent:** `requirement.md` §0 (Postgres+pgvector and SQLite both required; backend MUST NOT fork product rules); `roadmap/index.md` slice 100020.

## Spike conclusion (doc-recorded, 2026-09-16)

| Backend | Vector mechanism | Phase 100020 bar | Scale ceiling (first-release guidance) | ANN status |
|---------|------------------|---------------|----------------------------------------|------------|
| PostgreSQL + pgvector | Native extension indexes | Insert/delete/query hooks; behavioral parity with SQLite API | Production ANN indexes available; tune later in slice 100110 | Supported by pgvector |
| SQLite + loadable extension (default example: **sqlite-vec**) | `vec0` (or equivalent) KNN | Extension **must load**; insert/delete; **exact/brute-force KNN** acceptable | Comfortable target: tens–low hundreds of thousands of vectors for exact KNN | Stable sqlite-vec historically exact KNN; ANN (e.g. DiskANN/IVF) was alpha/pre-v1 as of review—**do not block Phase 100020 on ANN** |

## Non-negotiables

- No pretend-native-pgvector on SQLite (float blob claiming vector parity without a real extension).
- Backend choice MUST NOT change admission, taxonomy, or encryption rules.
- Phase 100020 exit does **not** require equal p95 recall latency at multi-million scale across backends.

## Upgrade path

- Slice 100110: wire embedding generation + rebuild hooks; revisit ANN only if a production-stable SQLite ANN build is chosen and documented.
- If sqlite-vec ANN becomes stable, record version + recall/latency spike results here before making ANN an AC.

## What Phase 100020 completion evidence MUST include

- Extension name + version (SQLite) and pgvector availability check (Postgres).
- Confirmation that ACs used exact KNN (or documented equivalent), not alpha ANN.
- Explicit statement of the scale ceiling assumed for the deployment profile under test.

# DeSci Platform API Spec

Last updated: 2026-05-13

This document is the source-of-truth contract for the FastAPI backend in
`apps/desci-platform/backend`. It was created from the current implemented
routes because the requested `API_SPEC.md` was not present in the workspace.

## Conventions

- Base URL in local development: `http://127.0.0.1:8000`
- Request and response bodies are JSON unless an endpoint explicitly uses
  `multipart/form-data` or `text/event-stream`.
- Authenticated endpoints use `Authorization: Bearer <firebase_id_token>`.
- Local tests may use `Authorization: Bearer test-token-bypass` when
  `ALLOW_TEST_BYPASS=true`.
- Validation failures use FastAPI's standard `422` response shape.
- Expected domain failures use `HTTPException` with a `detail` field.
- Rate limits are enforced by `slowapi` where decorators are present.

## Core Health

### `GET /`

Returns service metadata.

Response `200`:

```json
{
  "service": "BioLinker",
  "description": "AI bio grant matching agent",
  "version": "0.2.0",
  "features": ["RFP Analysis", "KDDF/NTIS Crawling", "ChromaDB Search", "IPFS Upload", "Token Rewards"]
}
```

### `GET /health`

Returns subsystem health.

Required response fields:

- `status`: `healthy` or `degraded`
- `vector_store_backend`
- `llm_available`
- `chromadb_ok`
- `chromadb_count`
- `web3_connected`
- `ipfs_configured`
- `grobid_configured`
- `grobid_available`
- `redis_ok`
- `rabbitmq_ok`

### `GET /ready`

Returns launch-readiness checks.

Required response fields:

- `status`: `ready`, `degraded`, or `blocked`
- `checked_at`
- `summary`
- `checks`
- `launch_blockers`

### `GET /me`

Auth required. Returns current user bootstrap data.

Response `200`:

```json
{
  "authenticated": true,
  "uid": "test-user-id",
  "email": "test@example.com",
  "name": "Test User"
}
```

Auth errors:

- `401` when the auth header is missing or malformed.
- `503` when Firebase auth is unavailable and local fallback is disabled.

## Job API

Long-running workflows create jobs and return a `JobSnapshot`. Clients can poll
`GET /jobs/{job_id}` or consume `GET /jobs/{job_id}/events` as SSE.

### JobSnapshot

```json
{
  "id": "uuid",
  "type": "notice_collection",
  "status": "queued",
  "progress": 0,
  "message": "Queued notice collection",
  "storage": "memory",
  "result": null,
  "error": null,
  "created_at": "2026-05-13T00:00:00Z",
  "started_at": null,
  "completed_at": null,
  "updated_at": "2026-05-13T00:00:00Z",
  "events": [
    {
      "timestamp": "2026-05-13T00:00:00Z",
      "status": "queued",
      "progress": 0,
      "message": "Queued notice collection"
    }
  ]
}
```

Allowed `type` values:

- `notice_collection`
- `paper_index`
- `paper_match`
- `proposal_generation`

Allowed `status` values:

- `queued`
- `running`
- `succeeded`
- `failed`

Allowed `storage` values:

- `memory`
- `redis`

### `POST /jobs/notices/collect`

Creates a public notice-collection job.

Auth: not required.

Rate limit: `10/minute`.

Request body: none.

Response `200`:

```json
{
  "job": {
    "id": "uuid",
    "type": "notice_collection",
    "status": "queued",
    "progress": 0,
    "message": "Queued notice collection",
    "storage": "memory",
    "result": null,
    "error": null,
    "created_at": "2026-05-13T00:00:00Z",
    "started_at": null,
    "completed_at": null,
    "updated_at": "2026-05-13T00:00:00Z",
    "events": []
  }
}
```

Terminal successful result:

```json
{
  "collected": 2,
  "notices": [
    {"id": "n1", "title": "Notice 1", "source": "KDDF"}
  ]
}
```

### `POST /jobs/papers/index`

Creates a paper reindexing job for an uploaded paper.

Auth: required.

Rate limit: `10/minute`.

Request body:

```json
{
  "paper_id": "paper-or-cid"
}
```

Validation:

- `paper_id` is required and must be non-empty.

Access rules:

- `404` if the paper or saved paper manifest does not exist.
- `403` if the paper has no verifiable owner.
- `403` if the current user is not the paper owner.

Terminal successful result includes paper metadata and indexing analysis:

```json
{
  "id": "paper-or-cid",
  "cid": "paper-or-cid",
  "title": "Paper title",
  "abstract": "Paper abstract",
  "authors": ["Jane Doe"],
  "ipfs_url": "https://ipfs.io/ipfs/paper-or-cid",
  "type": "paper",
  "indexed": true,
  "reindexed": true,
  "analysis": {
    "status": "indexed",
    "parser": "pypdf",
    "text_length": 1234,
    "metadata_keys": [],
    "reference_count": 0,
    "structured_fields": ["title", "abstract", "authors"]
  }
}
```

### `POST /jobs/match/paper`

Creates a paper-to-RFP matching job.

Auth: required.

Rate limit: `20/minute`.

Request body:

```json
{
  "paper_id": "paper-or-cid",
  "limit": 5,
  "target_trl": 4,
  "enrich": false
}
```

Validation:

- `paper_id` is required and must be non-empty.
- `limit` defaults to `5` and must be between `1` and `20`.
- `target_trl`, when present, must be between `0` and `9`.
- `enrich` defaults to `false`.

Access rules:

- Same paper ownership rules as `POST /jobs/papers/index`.
- `404` if the paper has not been indexed into the vector store.

Terminal successful result:

```json
{
  "matches": [
    {
      "id": "rfp-1",
      "similarity": 0.91,
      "document": "summary text",
      "metadata": {
        "title": "Grant A",
        "source": "KDDF",
        "keywords": "bio"
      }
    }
  ]
}
```

When `enrich=true`, result may also contain:

```json
{
  "enrichment": {
    "applied": true,
    "concepts": ["drug discovery"],
    "source": "openalex"
  }
}
```

### `POST /jobs/proposal/generate`

Creates a proposal generation job.

Auth: required.

Tier: `pro` or higher.

Usage action: `proposal_generation`.

Rate limit: `10/minute`.

Request body:

```json
{
  "paper_id": "paper-or-cid",
  "rfp_id": "rfp-id"
}
```

Validation:

- `paper_id` is required and must be non-empty.
- `rfp_id` is required and must be non-empty.

Access rules:

- Same paper ownership rules as `POST /jobs/papers/index`.
- `404` if the paper is not indexed.
- `404` if the RFP is not indexed.
- `403` if the current subscription tier is below `pro`.
- `403` if the monthly proposal-generation usage limit is exceeded.

Terminal successful result:

```json
{
  "draft": "# Proposal: Grant A\n...",
  "critique": "Review text"
}
```

### `GET /jobs/{job_id}`

Returns the latest job snapshot.

Auth:

- Not required for public jobs such as `notice_collection`.
- Required for private jobs such as paper indexing, paper matching, and proposal
  generation.

Access rules:

- `404` if the job does not exist.
- `401` if the job is private and auth is missing.
- `403` if the job is private and belongs to another user.

Response `200`: `JobSnapshot`.

### `GET /jobs/{job_id}/events`

Streams job snapshots as server-sent events.

Auth and access rules are the same as `GET /jobs/{job_id}`.

Response media type: `text/event-stream`.

Each event uses this format:

```text
data: {"id":"uuid","status":"running","progress":55,...}

```

The stream ends after a terminal `succeeded` or `failed` snapshot.

## RFP API

### `POST /analyze`

Auth required through `UsageGuard("rfp_analysis")`.

Request body:

```json
{
  "rfp_text": "raw RFP text",
  "rfp_url": "https://example.com/rfp",
  "user_profile": {
    "company_name": "Test Biotech",
    "tech_keywords": ["AI", "drug discovery"],
    "tech_description": "AI-powered antibody discovery",
    "company_size": "SME",
    "current_trl": "TRL 4"
  }
}
```

Response `200`:

```json
{
  "rfp": {
    "id": "rfp-1",
    "title": "Grant A",
    "source": "KDDF",
    "body_text": "...",
    "keywords": ["AI"]
  },
  "result": {
    "fit_score": 85,
    "fit_grade": "A",
    "match_summary": ["reason"],
    "required_docs": [],
    "risk_flags": [],
    "recommended_actions": []
  }
}
```

### `GET /match/rfp`

Auth required through `UsageGuard("rfp_search")`.

Query parameters:

- `query` required
- `limit` default `5`, range `1..50`
- `source`
- `document_type`
- `keyword`
- `deadline_from`
- `deadline_to`
- `trl_min` range `0..9`
- `trl_max` range `0..9`

Response `200`: vector-search results from the configured vector store.

### Legacy RFP endpoints

These endpoints remain available for compatibility:

- `POST /parse`
- `POST /match/paper`
- `POST /match/smart`
- `POST /similar/profile`
- `GET /enrich/external`
- `GET /enrich/external/cache-stats`
- `POST /proposal/generate`

New frontend flows should prefer the Job API for paper matching and proposal
generation.

## Crawling API

- `GET /notices`: list collected notices. Query: `source`, `limit`.
- `POST /notices/collect`: synchronous notice collection. Prefer
  `POST /jobs/notices/collect` for UI flows.
- `GET /notices/kddf`: raw KDDF notices. Query: `page`.
- `GET /notices/ntis`: raw NTIS notices. Query: `keyword`, `page`.

## Web3 and Asset API

- `GET /wallet/{address}`: wallet balance payload.
- `POST /reward/paper`: query/body parameter `user_address`.
- `POST /reward/review`: query/body parameter `user_address`.
- `POST /reward/share`: query/body parameter `user_address`.
- `GET /reward/amounts`: configured reward amounts.
- `POST /nft/mint`: body requires `user_address` and `token_uri`; optional
  `consent_hash`, `consent_timestamp`.
- `POST /assets/upload`: `multipart/form-data`, fields `file`,
  optional `asset_type`.
- `POST /upload`: auth required, `multipart/form-data`, fields `file`,
  optional `title`, `authors`, `abstract`.
- `GET /papers/me`: auth required, returns papers owned by current user.
- `GET /papers/public`: public paper list.
- `GET /assets`: local uploaded asset list.

## Agent API

Locale headers:

- `X-User-Locale`, default `ko-KR`
- `X-Output-Language`, currently normalized to `ko`

Endpoints:

- `POST /api/agent/research`
- `POST /api/agent/write`
- `POST /api/agent/youtube`
- `POST /api/agent/literature-review`

Validation failures use `400` when a required semantic field such as `topic`,
`raw_text`, or `url` is missing.

## Governance API

- `GET /governance/proposals`
- `POST /governance/proposals`: body requires `title` and `description`.
- `POST /governance/proposals/{proposal_id}/vote`: body requires `voter`;
  optional `support`, default `true`.

## Subscription API

- `GET /subscription/pricing`: public pricing plans.
- `GET /subscription/usage`: auth required.
- `GET /subscription/tier`: auth required.
- `POST /subscription/checkout`: auth required; body uses `tier` and `billing`.
- `POST /subscription/upgrade`: auth required; body uses `tier`.
- `POST /subscription/webhook/stripe`: Stripe webhook receiver.

## Verification

The API contract is covered by the backend test suite:

```bash
cd apps/desci-platform/backend
python -m pytest tests -q
```

Focused Job API coverage:

```bash
cd apps/desci-platform/backend
python -m pytest tests/test_jobs.py -q
```

# AgriGuard QC Report - Metrics Runtime Integration

**Date:** 2026-03-29
**Status:** FAILED (3 findings: 1 high, 1 medium, 1 low)
**Environment:** Windows development with Docker Desktop + `apps/AgriGuard/docker-compose.yml`
**Scope:** Recent AgriGuard metrics integration and related runtime coverage

---

## Summary

This QC pass focused on the recently added Prometheus metrics support in AgriGuard.

The main result is that the metrics feature is not currently available in the shipped backend container, even though local source imports can make it appear functional during direct Python execution from the repository checkout. In addition, the current path-normalization logic computes labels too early to use FastAPI route templates, and the new tests do not exercise a real app/container path that would catch either regression.

Because `/metrics` is currently missing from the default Docker-backed runtime, this change set should not be considered production-ready in its current form.

---

## Findings

### 1. High - `/metrics` is not available in the backend container

The backend now attempts to enable metrics from `main.py`, but the default Docker build path does not include the tracked metrics helper module and does not install `prometheus_client`.

Why this fails in practice:
- `apps/AgriGuard/docker-compose.yml` builds the backend from `./backend`
- `apps/AgriGuard/backend/Dockerfile` copies only the backend build context into the image
- `packages/shared/metrics.py` lives outside that build context
- `apps/AgriGuard/backend/requirements.txt` does not include `prometheus_client`

Observed runtime evidence:
- `http://localhost:8002/metrics` returned `404`
- `docker exec agriguard-backend` could not import `packages.shared.metrics`
- `docker exec agriguard-backend` could not import `prometheus_client`

Impact:
- the PR currently advertises backend observability that is not actually present in the default containerized runtime
- local source-tree imports can mask this problem during direct Python checks

### 2. Medium - route-template normalization is computed too early

The metrics middleware currently resolves the request path before `call_next()`. In FastAPI, `request.scope["route"]` is not reliably populated until routing has happened inside the request pipeline.

Observed behavior in a reproduction:
- before `call_next()`: route was `None`, path was the raw URL
- after `call_next()`: route template became available, for example `/items/{item_id}`

Impact:
- once metrics are enabled, labels are likely to use raw request paths such as `/products/123`
- this reintroduces high-cardinality label values instead of normalized route templates like `/products/{product_id}`

### 3. Low - current metrics tests are too narrow to catch runtime regressions

The added metrics tests validate the normalization helper in isolation, but they do not verify that a real FastAPI app exposes `/metrics` or that a container/runtime path can import the metrics module successfully.

Impact:
- the current test suite can stay green even when the shipping container returns `404` for `/metrics`
- the tests also would not catch the timing issue around route-template resolution

---

## Verification Evidence

The following checks were run during this QC pass:

```powershell
python -m pytest tests\test_shared_metrics.py -q
python -m pytest apps\AgriGuard\backend\tests\test_smoke.py -q
Invoke-WebRequest http://localhost:8002/metrics
docker exec agriguard-backend python -c "import importlib.util; print(importlib.util.find_spec('packages.shared.metrics'))"
docker exec agriguard-backend python -c "import prometheus_client"
```

Observed outcome summary:
- helper unit tests passed
- backend smoke tests passed
- `/metrics` returned `404`
- `packages.shared.metrics` was missing in the container
- `prometheus_client` was missing in the container

---

## Recommended Fixes

1. Make the metrics code part of the backend runtime.
   Either move the helper into the backend package, or change the backend image build so the shared tracked module is copied into the image and importable at runtime.

2. Add the missing dependency.
   Add `prometheus_client` to the backend runtime dependencies used by Docker builds.

3. Normalize paths after routing has happened.
   Resolve the route template after `call_next()` or otherwise use a point in the request lifecycle where FastAPI route metadata is available.

4. Add an integration test.
   Create at least one FastAPI-level test that mounts the middleware, hits a real route plus `/metrics`, and verifies both endpoint availability and normalized route labels.

---

## Conclusion

**Assessment:** metrics integration is incomplete in the current runtime path and should be treated as failing QC until the backend container can actually expose `/metrics` and the label normalization logic is verified end-to-end.

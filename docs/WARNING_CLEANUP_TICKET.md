# Warning Cleanup Ticket

## Title
Reduce `pytest` warning noise after test stabilization

## Context
- Date: 2026-02-25
- Baseline command:
  - `.\.venv\Scripts\python.exe -m pytest -q -s -p no:cacheprovider`
- Baseline result:
  - `5 passed, 4 deselected, 51 warnings`

## Scope
- In scope:
  - Remove project-owned warning sources and improve test signal quality.
  - Keep integration/external tests optional by marker.
- Out of scope:
  - Feature changes unrelated to warning cleanup.

## Work Items
1. FastAPI/OpenAPI deprecations
- Replace deprecated `example=` usage with `examples=` in request/response models.
- Confirm smoke tests still pass.

2. Multipart pending deprecation
- Migrate imports/usages toward `python_multipart` compatibility path.
- Verify upload-related endpoints and tests.

3. LangChain/GenAI deprecations
- Remove deprecated chat model options (for example, system message conversion flags).
- Keep behavior equivalent in proposal generation and analyzer flows.

4. Python version compatibility
- Decide policy:
  - Option A: pin runtime to Python 3.12/3.13 for current stack.
  - Option B: upgrade libs to fully support Python 3.14.
- Update `README`/dev setup docs accordingly.

5. Warning budget gate
- Add a CI warning budget check for core smoke suite.
- Initial target: no new warnings introduced by project-owned code.

## Acceptance Criteria
- Default test run keeps passing:
  - `.\.venv\Scripts\python.exe -m pytest -q -s -p no:cacheprovider`
- Project-owned warning categories reduced and documented.
- Integration marker behavior remains:
  - default run excludes integration tests
  - `-m integration` still runs external/integration tests when services are available

## Notes
- Current integration command status in local environment:
  - `.\.venv\Scripts\python.exe -m pytest -q -s -p no:cacheprovider -m integration`
  - Fails when dependent services are down (`localhost:8000`/`localhost:8001`) or endpoints differ.

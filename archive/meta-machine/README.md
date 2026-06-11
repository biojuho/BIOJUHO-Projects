# Meta Machine Archive

This folder preserves historical launch/proof/meta documents that are no longer the root onboarding surface.

## Contents

- `README.full-before-slim.md` - the previous long-form root README before the June 2026 cleanup.

## Current Boundary

The live static app still reads selected release cache files from `autoresearch-results/` because `package-release`, `verify-release`, and `smoke-release` validate those JSON artifacts as runtime evidence cache inputs.

Do not treat this archive as a runtime dependency. New operator guidance should go in the root `README.md`, and detailed loop history should stay in `docs/product-direction.md` or purpose-specific docs.

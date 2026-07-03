# AutoResearch Loop - AgriGuard Registry Label Accessibility

Date: 2026-07-04
App: AgriGuard
Cycle: Product registry form accessibility

## Baseline

The product registry form used visible labels, but most labels were not connected to their controls with `htmlFor` and `id`. Tests had to locate required fields by placeholder text instead of accessible names.

## Variant

Added stable field ids and explicit label associations for:

- Crop Name
- Owner ID
- Category
- Origin Region
- Harvest Date
- Description

Updated `ProductRegistry.test.jsx` to fill required fields through `getByLabelText`, proving the accessible names work.

## Evidence

- `npm run test -- ProductRegistry.test.jsx`
  - Test files: 1 passed
  - Tests: 1 passed
- `npm run lint`
  - Status: pass
- `npm run build:lts`
  - Status: pass

## Decision

Adopt the explicit label associations. The registry form is more accessible and the test now follows the same interaction path a screen reader or keyboard user relies on.

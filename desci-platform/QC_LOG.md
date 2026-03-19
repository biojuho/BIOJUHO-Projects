# DSCI QC Log

## 2026-03-18

### Scope
- Frontend claymorphism rebrand follow-up QC
- Login layout and typography polish
- Korean locale copy and rendering cleanup

### Changes
- Reworked the login layout to remove excessive vertical stretching and align the two-panel composition to content height.
- Adjusted desktop and mobile spacing in the login shell for better card balance and reduced empty space.
- Added a Korean-safe font stack and Korean-specific heading fallback to prevent awkward mixed-script rendering.
- Reduced the visual noise overlay intensity on clay/glass surfaces so text remains clearer.
- Localized Korean login and shell labels that were still showing English marketplace terms.

### Files
- `frontend/src/components/Login.jsx`
- `frontend/src/index.css`
- `frontend/src/i18n/messages.js`

### Verification
- Browser QA on `/login` at desktop and mobile widths
- `npm run test`
- `npm run lint`
- `npm run build:lts`

### Result
- Login screen alignment is stable on desktop and mobile.
- Korean copy renders cleanly and no longer mixes the English panel heading on the login card.
- Automated checks passed after the fix.

## 2026-03-18 (QC rerun)

### Scope
- Frontend regression QC after login polish
- Browser smoke check for locale persistence and protected routes
- Test runner stability verification on Windows

### Changes
- Updated `frontend/vite.config.js` to use the Vitest `threads` pool instead of `forks`.
- Kept the suite single-worker to match the existing deterministic test setup.

### Verification
- `npm run test`
- `npm run lint`
- `npm run build:lts`
- Headless browser check on `/login`
- Locale persistence check for `KO -> EN`
- Unauthenticated redirect check for `/dashboard` and `/governance`
- Browser console error check

### Result
- `npm run test` now passes reliably in this Windows environment.
- Default locale initializes as `ko-KR` with `dsci.outputLanguage=ko`.
- Switching to English persists after reload with `dsci.locale=en-US`, `dsci.outputLanguage=en`, and `document.lang=en-US`.
- Unauthenticated access to protected routes redirects back to `/login`.
- No browser console errors were observed during the smoke check.

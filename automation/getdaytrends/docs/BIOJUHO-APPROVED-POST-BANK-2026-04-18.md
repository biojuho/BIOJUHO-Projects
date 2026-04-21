# Biojuho Approved Post Bank

## Implemented

- Added a draft repository query that loads recent `approved`, `published`, `measured`, and `learned` X drafts as reusable voice references.
- Injected a short `Approved Post Bank` section into tweet prompts so new copy can anchor to previously accepted sentence density and rhythm.
- Wired the same bank into QA regeneration so retries do not drift into a different voice from the first pass.

## Scope

- Current source: local `draft_bundles` database
- Current platform focus: `x`
- Current prompt usage: up to 3 short references, rhythm only, no direct copying

## Next Upgrade

- Add edited-vs-final deltas from the review loop
- Rank references by performance once 24h and 72h metrics are available
- Extend the same bank concept to Threads and blog openings after review data is richer

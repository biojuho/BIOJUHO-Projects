# Insight Quality Check

This document is the operator-facing counterpart to
`src/antigravity_mcp/insights/validator.py`.

Every generated insight should satisfy all three principles below.

## Principle 1: Fact -> Pattern

The insight must connect at least one concrete fact from the source set to a
broader pattern or trend.

Checklist:
- Use at least 2 concrete anchors from the source set or clearly label extra context as `[Background]`.
- Mention a time horizon, timing signal, or sequence when making a trend claim.
- Explain the link between the fact and the broader pattern instead of merely restating the article.
- When possible, end the main analytic sentence with an evidence tag such as `[A1]` or `[Inference:A1+A2]`.

Fail examples:
- "AI is growing quickly."
- "This seems important for the market."

Better examples:
- "GPU supply remains tight while cloud vendors keep expanding custom accelerators. That combination raises the odds that inference costs stay sticky through the next two quarters."

## Principle 2: Ripple Effect

The insight must describe a second-order effect, not just a first-order summary.

Checklist:
- Include at least one explicit causality phrase such as `because`, `therefore`, `which means`, or `leading to`.
- Show a chain with stages such as `1st order`, `2nd order`, `3rd order`, or an equivalent sequence.
- Avoid vague "there may be impacts" language.

Hard fail:
- No stage language and no causality language in the ripple section.

## Principle 3: Actionable Item

The reader should know what to do next.

Checklist:
- Name a specific audience.
- Use a concrete action verb.
- Include a timeframe or deadline.
- Refer to a specific asset, metric, company, tool, or decision target.

Hard fail:
- CTA ends in generic verbs like `review`, `consider`, `watch`, `monitor`, `pay attention` without a concrete target or timeframe.
- More than 3 audience segments are named in one insight.

Good:
- "Investor: compare CoreWeave pricing against your current GPU rental benchmark this week."

Bad:
- "Monitor the AI market closely."

## Runtime Hard-Fail Rules

The runtime validator currently applies these hard-fail rules:

1. Generic CTA with no target or timeframe.
2. More than 3 audience groups in `target_audience`.
3. Ripple section missing both stage language and causality language.
4. New numbers not present in the source set are not a hard fail, but they produce a warning and should move the report into `needs_review`.

## Evidence Tag Contract

For base LLM report generation, analytic lines in:

- `Signal`
- `Pattern`
- `Ripple Effects`
- `Counterpoint`
- `Action Items`

should end with exactly one of:

- `[A1]`, `[A2]`, ...
- `[Inference:A1+A2]`
- `[Background]`
- `[Insufficient evidence]`

`Draft Post` should remain clean reader-facing text and should not include evidence tags.

## Editor Review Guidance

Before approving a report, check:

- Can the main claim be traced back to the provided article set?
- Does the ripple section explain what changes after the headline?
- Could the action item be completed within a real operating window?
- If the report is marked `fallback` or `needs_review`, do not auto-publish it.

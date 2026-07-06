# AgriGuard QR Page A/B Test Draft

- Generated: 2026-07-06T11:51:47Z
- Dataset: built-in sample
- Sessions: 20

## Audience

- Type: B2B plus consumer verification
- Personas: Supply Chain Manager, Safety-Conscious Consumer
- Profile: Users need immediate confidence that a QR scan will verify the right product without friction or ambiguity, especially on mobile in noisy real-world environments.

## Hypothesis

- The guided verification variant will improve QR verification completion by at least 15% relative while reducing time to successful verification and keeping invalid-scan friction flat or lower.
- Primary KPI: verification_success_rate
- Decision rule: Adopt version B if verification success improves by >=15% relative, median time to verify improves, and invalid error rate does not increase.

## Metrics

| Variant | Sessions | Verification Success | Scan Success | Invalid Error | Median Time (s) | Trust Score |
|---|---:|---:|---:|---:|---:|---:|
| A - scanner-first control | 10 | 0.60 | 0.80 | 0.40 | 20.00 | 3.16 |
| B - guided verification variant | 10 | 0.90 | 1.00 | 0.10 | 12.95 | 4.17 |

## Decision

- Outcome: Adopt version B
- Verification relative lift: 50.00%
- Time improved: True
- Error rate not worse: True

## Notes

- This is a draft experiment harness for the QR verification experience.
- Replace the sample sessions with real telemetry once scan and verification events are instrumented.

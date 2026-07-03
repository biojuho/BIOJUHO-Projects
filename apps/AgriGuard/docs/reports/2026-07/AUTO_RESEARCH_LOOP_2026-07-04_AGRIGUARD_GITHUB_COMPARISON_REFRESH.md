# AutoResearch Loop - AgriGuard GitHub Comparison Refresh

Date: 2026-07-04
App: AgriGuard
Cycle: Source-backed product radar refresh

## Sources Compared

Searched current public GitHub projects for agricultural or food supply-chain traceability, QR verification, cold-chain/temperature evidence, and blockchain-backed provenance patterns.

- Farm2Table - Food Supplychain Traceability Application: https://github.com/MoigeMatino/food-supplychain-traceability-app
- FoodTraze Hyperledger Fabric network: https://github.com/hyperledger-foodtraze/foodtraze-network
- Agricultural Supply Chain Traceability with Blockchain: https://github.com/vendkura/Sup-Prod-Track
- Organic food trackchain: https://github.com/NaikAayush/organic-food-trackchain
- Agriculture product tracking chain: https://github.com/SOSANE/agriculture-product-tracking-chain
- FarmXchain: https://github.com/jathinvasukula/FarmXchain

## Patterns

| Pattern | External signal | AgriGuard state | Decision |
| --- | --- | --- | --- |
| Consumer QR transparency | Farm2Table, FoodTraze, Sup-Prod-Track, and OrganicChain all center consumer QR verification. | AgriGuard already has `/verify/:token`, seeded QR browser smoke, invalid QR recovery, token hashing, and public-field redaction. | Keep covered; continue browser proof on fresh DBs. |
| Route, temperature, and proof evidence | OrganicChain and Sup-Prod-Track emphasize journey, origin, and storage-temperature visibility. | AgriGuard public verification shows origin, route checkpoints, temperature summary, and blockchain proof metadata. | Keep covered; current priority is evidence reliability and launch config. |
| Low-bandwidth or offline-friendly verification | Sup-Prod-Track explicitly frames offline-first/low-bandwidth rural use; FoodTraze emphasizes farmer-friendly mobile capture. | AgriGuard has an unavailable/retry state, but no dedicated browser smoke for API outage or cached last-known public proof. | Candidate next slice: add unavailable/retry browser coverage before considering cached proof. |
| Multi-stakeholder admin surfaces | FoodTraze and Sup-Prod-Track describe farmer/processor/distributor/consumer interfaces. | AgriGuard now has operator admin routes for QR tokens, sensors, product detail, supply chain, cold-chain, and consumer verify. | Covered for launch path; keep fail-closed auth checks. |
| Lab/quality report artifacts | FoodTraze includes ingredient/lab-test traceability. | AgriGuard has certifications and chain events, but no uploaded lab-report artifact workflow. | Backlog; not higher priority than launch env/browser reliability. |
| Staging/real-token smoke portability | Related projects generally document Docker/API startup paths, while AgriGuard has multiple browser smokes. | Browser smokes previously mixed local fallback tokens and explicit token flags. | Adopted today: no-flag local defaults plus `AGRIGUARD_BROWSER_OPERATOR_TOKEN` override consistency. |

## Adopted Since Last Radar

- `3601a89` hardened nav and QR browser-smoke defaults.
- `d8c512c` hardened supply-chain browser-smoke defaults.
- `42d7e2e` aligned QR/admin/product-detail smokes with `AGRIGUARD_BROWSER_OPERATOR_TOKEN`.

## Next Candidate

The strongest source-backed gap not already covered by local launch hardening is unavailable-network consumer verification proof. A focused next loop should exercise `/verify/:token` when the verification API is down, assert that the page does not go blank, confirm the retry/scan recovery controls, and avoid adding cached proof until privacy and staleness rules are explicit.

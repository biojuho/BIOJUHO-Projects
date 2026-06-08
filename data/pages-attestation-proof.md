# JooPark Pages Attestation Proof

- status: pass
- proofComplete: false
- signedProofReady: false
- proofFieldCoverage: 1
- completedFieldCount: 0/6
- repo: biojuho/BIOJUHO-Projects
- sourceProofInput: not provided

## Fields
- pages_workflow_run: missing
- attestation_url: missing
- attestation_id: missing
- manifest_verify: missing
- index_verify: missing
- predicate_type: missing

## Commands
- gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle
- gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects
- gh attestation verify dist/release/index.html -R biojuho/BIOJUHO-Projects
- gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects --format json --jq '.[].verificationResult.statement.predicateType'

## Receipt
# JooPark Pages Attestation Proof Capture

Status: blocked; not signed proof yet
Repo: biojuho/BIOJUHO-Projects
Workflow: joopark-pages.yml
Proof complete: false
Signed proof ready: false
Completed fields: 0/6
False positive guard: false

Parser-ready proof block:
pages_workflow_run:
attestation_url:
attestation_id:
manifest_verify:
index_verify:
predicate_type:
bundle_path:

Verification commands:
- gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle
- gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects
- gh attestation verify dist/release/index.html -R biojuho/BIOJUHO-Projects
- gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects --format json --jq '.[].verificationResult.statement.predicateType'

Missing fields:
- pages_workflow_run
- attestation_url
- attestation_id
- manifest_verify
- index_verify
- predicate_type

Guard:
Do not claim signed GitHub artifact attestation proof, archive proof, public launch complete, or readyForExternalClaim=true until all required attestation proof fields are valid, both gh attestation verify commands pass, and publish evidence plus launch handoff proof gates are ready.

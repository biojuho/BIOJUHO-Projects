# JooPark Launch Handoff Verification

- status: pass
- repo: biojuho/BIOJUHO-Projects
- verificationOnly: true
- dispatchExecuted: false
- launchProofCaptured: false
- remoteWorkflowFilesReady: true
- remoteWorkflowVisibilityReady: true
- workflowScopeAvailable: true
- workflowScopeInstallBlocked: false
- allDispatchReady: true
- safeToDispatch: true
- acceptance: 5/5 pass; pending=0

## Verification Artifacts
- artifactCoverage: 2
- json: data/launch-handoff-verification.json
- markdown: data/launch-handoff-verification.md
- write: true

## Auth Preflight
- checked: true
- source: gh-api-header
- workflowScopeAvailable: true
- workflowScopeInstallBlocked: false
- scopes: gist, read:org, repo, workflow
- refresh: gh auth refresh -h github.com -s workflow
- refreshWithClipboard: gh auth refresh -h github.com -s workflow --clipboard
- recheck: node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects
- approval: not_required
- interactiveApprovalRequired: false
- terminalWaitRequired: false
- incompleteApprovalSignal: Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.

## Commands Run
- pass: `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`
- pass: `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write`
- pass: `node scripts/capture-launch-execution-packet.mjs --write`
- pass: `node scripts/capture-output-quality-audit.mjs --write`

## Acceptance Checklist
- Operator auth path: pass - workflowScopeAvailable=true; workflowScopeInstallBlocked=false; workflowScope.scopes=gist, read:org, repo, workflow; workflowScopeMissing=none; workflowScopeRefreshCommand=gh auth refresh -h github.com -s workflow
- Local template parity: pass - localTargetParityReady=true
- Remote workflow file parity: pass - remoteWorkflowFilesReady=true; nextVerificationCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write
- Workflow visibility: pass - remoteWorkflowVisibilityReady=true; workflowListCommand=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id
- Dispatch guard: pass - allDispatchReady=true; withheldCommands=2

## Blocker Resolution Checklist
- source: generated_from_launch_execution_packet
- status: pass
- activeItemKey: not available
- items: 6/6 pass; actionRequired=0; deferred=0; proofCommands=6
- guard: Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.
- operator_auth_path: pass - action=Refresh GitHub CLI with workflow scope, or choose the GitHub UI path with a workflow-capable browser session.; proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects; expectedValue=workflowScopeAvailable=true; workflowScopeInstallBlocked=false, or GitHub UI path chosen to apply each workflow row's installAction on the default branch.; stopCondition=If workflowScopeInstallBlocked=true remains after recheck, do not run the CLI installer; use the GitHub UI path and keep dispatch withheld.
- local_template_parity: pass - action=Regenerate or restage local workflow targets if template parity fails before copying anything to GitHub.; proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects; expectedValue=localTargetParityReady=true; each local target SHA-256 matches its template SHA-256.; stopCondition=Do not create remote workflow files from stale or mismatched local targets.
- remote_workflow_file_parity: pass - action=Apply each workflow row's installAction on the default branch, then compare remote SHA-256 values against local templates.; proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; expectedValue=remoteWorkflowFilesReady=true; every workflow file has remoteExists=true and remoteMatchesTemplate=true.; stopCondition=If any workflow file is missing_on_default_branch or sha_mismatch, do not run dispatch.
- workflow_visibility: pass - action=List repository workflows and rerun the dispatch plan after remote file parity passes.; proofCommand=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id; expectedValue=remoteWorkflowVisibilityReady=true; Publish JooPark Pages and Watch JooPark Candidate Drift are visible.; stopCondition=If GitHub Actions does not list both workflows, keep suggestedDispatchCommands empty.
- dispatch_guard: pass - action=Rerun launch handoff verification and use only suggestedDispatchCommands after the guard reports safeToDispatch=true.; proofCommand=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown; expectedValue=allDispatchReady=true; safeToDispatch=true before gh workflow run.; stopCondition=If safeToDispatch=false, gh workflow run commands must stay withheld.
- launch_proof_capture: pass - action=After guarded dispatch completes, capture Pages site proof, workflow run proof, freshness, release receipt, and public-claim guard evidence.; proofCommand=node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write; expectedValue=postPublishEvidenceReady=true; evidenceFresh=true; readyForExternalClaim=true only after live proof is saved.; stopCondition=Do not post public launch copy, archive proof, or claim readyForExternalClaim until all launch proof fields are live and successful.

## Post-install Evidence Intake
- source: generated_from_launch_execution_packet
- status: proof_complete
- ready: true
- proofComplete: true
- fields: 6/6 complete; pending=0; coverage=1
- fieldKeys: pages_workflow_commit, drift_workflow_commit, remote_parity_proof, actions_visibility_proof, dispatch_readiness_proof, handoff_verifier_proof
- commands: 4; signals=8; checklist=5; sequence=4
- verificationSequenceReady: true
- finalVerificationCommand: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown
- quickProofReady: true; steps=4; coverage=1; final=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown
- quickProofFieldMappingReady: true; mapped=4; completed=4/4; coverage=1
- guard: Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.
- Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.

## Post-install Quick Proof
- 1. remote_file_parity: command=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; expected=remoteWorkflowFilesReady=true; evidenceField=remote_parity_proof; status=proof_ready
- 2. actions_visibility: command=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id; expected=remoteWorkflowVisibilityReady=true; evidenceField=actions_visibility_proof; status=proof_ready
- 3. dispatch_readiness: command=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects; expected=allDispatchReady=true; evidenceField=dispatch_readiness_proof; status=proof_ready
- 4. handoff_verifier: command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown; expected=safeToDispatch=true before gh workflow run; evidenceField=handoff_verifier_proof; status=proof_ready
- mapped field 1 remote_file_parity -> remote_parity_proof: proof_ready; completed=true; currentValue=remoteWorkflowFilesReady=true; filesReady=2/2; missing=0; mismatch=0; expectedValue=remoteWorkflowFilesReady=true and every workflow file has remoteExists=true and remoteMatchesTemplate=true.; proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write
- mapped field 2 actions_visibility -> actions_visibility_proof: proof_ready; completed=true; currentValue=remoteWorkflowVisibilityReady=true; expectedValue=remoteWorkflowVisibilityReady=true and GitHub Actions lists both workflow files.; proofCommand=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id
- mapped field 3 dispatch_readiness -> dispatch_readiness_proof: proof_ready; completed=true; currentValue=dispatchReady=true; driftDispatchReady=true; allDispatchReady=true; expectedValue=dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true.; proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects
- mapped field 4 handoff_verifier -> handoff_verifier_proof: proof_ready; completed=true; currentValue=safeToDispatch=true; allDispatchReady=true; expectedValue=verify-launch-handoff reports safeToDispatch=true before gh workflow run.; proofCommand=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown
- command: node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write
- command: gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id
- command: node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects
- command: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown
- sequence 1 remote_file_parity: Remote workflow file check; command=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; expected=remoteWorkflowFilesReady=true; guard=Confirm both default-branch workflow files exist and match local templates before checking Actions visibility.
- sequence 2 actions_visibility: Actions visibility check; command=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id; expected=remoteWorkflowVisibilityReady=true; guard=Confirm GitHub Actions lists both workflow files before planning dispatch.
- sequence 3 dispatch_readiness: Dispatch readiness plan; command=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects; expected=allDispatchReady=true; guard=Confirm pages and drift dispatch readiness are both true before final handoff verification.
- sequence 4 handoff_verifier: Launch handoff verifier; command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown; expected=safeToDispatch=true before gh workflow run; guard=Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.
- expected signal: remoteWorkflowFilesReady=true
- expected signal: pages remoteExists=true and remoteMatchesTemplate=true
- expected signal: drift-watch remoteExists=true and remoteMatchesTemplate=true
- expected signal: remoteWorkflowVisibilityReady=true
- expected signal: dispatchReady=true
- expected signal: driftDispatchReady=true
- expected signal: allDispatchReady=true
- expected signal: safeToDispatch=true before gh workflow run
- field pages_workflow_commit: proof_ready; completed=true; currentValue=.github/workflows/joopark-pages.yml; status=ready; remoteSha256=7d47ffeb39201dacff42a52825e7988d20aa28e81d2d54dfcf628a3c1e39619e; expectedValue=.github/workflows/joopark-pages.yml exists on main and remoteMatchesTemplate=true.; proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; stopCondition=If pages remoteExists=false or remoteMatchesTemplate=false, do not run dispatch.
- field drift_workflow_commit: proof_ready; completed=true; currentValue=.github/workflows/joopark-drift-watch.yml; status=ready; remoteSha256=1e6f0ed82323d4762a9bd78dfff01f18ec5e2b4882ee346acabed4542e5d46f2; expectedValue=.github/workflows/joopark-drift-watch.yml exists on main and remoteMatchesTemplate=true.; proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; stopCondition=If drift-watch remoteExists=false or remoteMatchesTemplate=false, do not run dispatch.
- field remote_parity_proof: proof_ready; completed=true; currentValue=remoteWorkflowFilesReady=true; filesReady=2/2; missing=0; mismatch=0; expectedValue=remoteWorkflowFilesReady=true and every workflow file has remoteExists=true and remoteMatchesTemplate=true.; proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write; stopCondition=If any workflow file is missing_on_default_branch or sha_mismatch, do not run dispatch.
- field actions_visibility_proof: proof_ready; completed=true; currentValue=remoteWorkflowVisibilityReady=true; expectedValue=remoteWorkflowVisibilityReady=true and GitHub Actions lists both workflow files.; proofCommand=gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id; stopCondition=If GitHub Actions does not list both workflows, keep suggestedDispatchCommands empty.
- field dispatch_readiness_proof: proof_ready; completed=true; currentValue=dispatchReady=true; driftDispatchReady=true; allDispatchReady=true; expectedValue=dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true.; proofCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects; stopCondition=If allDispatchReady=false, suggestedDispatchCommands must remain empty.
- field handoff_verifier_proof: proof_ready; completed=true; currentValue=safeToDispatch=true; allDispatchReady=true; expectedValue=verify-launch-handoff reports safeToDispatch=true before gh workflow run.; proofCommand=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown; stopCondition=If safeToDispatch=false, gh workflow run commands must stay withheld.

## Withheld Dispatch Commands
- none

## Suggested Dispatch Commands
- gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release
- gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory

## Blockers
- none

## Next Actions
- Run the suggested dispatch commands only after confirming the repo and workflow names.
- Capture launch proof with node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write after workflow runs finish.

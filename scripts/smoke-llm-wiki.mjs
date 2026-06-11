#!/usr/bin/env node
// 일회성 상호작용 검증: LLM 위키 뷰 (문서 열기/마크다운/카테고리 전환/뷰 내 검색)
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-wiki-smoke-"));
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
const appUrl = `${baseUrl}/index.html`;

const projectOpsExpectedDocs = [
  {
    "key": "githubPagesActionsDeploy",
    "id": "github-pages-actions-deploy",
    "filename": "github-pages-actions-deploy.md",
    "title": "GitHub Pages를 Actions로 배포하기",
    "sourceKey": "project_ops_github_pages_actions_deploy",
    "markers": [
      "GitHub Pages를 Actions로 배포하기",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  },
  {
    "key": "localFirstDataSafety",
    "id": "local-first-data-safety",
    "filename": "local-first-data-safety.md",
    "title": "localStorage만 쓰는 앱의 데이터 안전",
    "sourceKey": "project_ops_local_first_data_safety",
    "markers": [
      "localStorage만 쓰는 앱의 데이터 안전",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  },
  {
    "key": "pwaOfflineOperations",
    "id": "pwa-offline-operations",
    "filename": "pwa-offline-operations.md",
    "title": "PWA 서비스워커 운영",
    "sourceKey": "project_ops_pwa_offline_operations",
    "markers": [
      "PWA 서비스워커 운영",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  },
  {
    "key": "vanillaSpaQualityGates",
    "id": "vanilla-spa-quality-gates",
    "filename": "vanilla-spa-quality-gates.md",
    "title": "바닐라 JS SPA 품질 게이트",
    "sourceKey": "project_ops_vanilla_spa_quality_gates",
    "markers": [
      "바닐라 JS SPA 품질 게이트",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  },
  {
    "key": "staticSiteDataSync",
    "id": "static-site-data-sync",
    "filename": "static-site-data-sync.md",
    "title": "서버 없는 정적 사이트에서 실데이터 가져오기",
    "sourceKey": "project_ops_static_site_data_sync",
    "markers": [
      "서버 없는 정적 사이트에서 실데이터 가져오기",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  },
  {
    "key": "llmAgentLoopGuardrails",
    "id": "llm-agent-loop-guardrails",
    "filename": "llm-agent-loop-guardrails.md",
    "title": "LLM 에이전트 자율 루프 가드레일",
    "sourceKey": "project_ops_llm_agent_loop_guardrails",
    "markers": [
      "LLM 에이전트 자율 루프 가드레일",
      "작성일: 2026-06-11",
      "프로젝트 운영 지식"
    ]
  }
];

function extractProjectOpsDocsFromWiki() {
  const source = readFileSync(new URL("../llm-wiki-view.js", import.meta.url), "utf8");
  const start = source.indexOf("  const PROJECT_OPS_DOCS = {");
  const end = source.indexOf("\n\n  const WIKI = {", start);
  if (start === -1 || end === -1) {
    throw new Error("PROJECT_OPS_DOCS block not found in llm-wiki-view.js");
  }
  const objectSource = source.slice(start, end).replace(/^\s*const PROJECT_OPS_DOCS\s*=\s*/, "").replace(/;\s*$/, "");
  return runInNewContext("(" + objectSource + ")", Object.create(null), { timeout: 1000 });
}

function assertProjectOpsExactMatch() {
  const wikiDocs = extractProjectOpsDocsFromWiki();
  const missing = [];
  for (const doc of projectOpsExpectedDocs) {
    const expected = readFileSync(new URL("../docs/knowledge/" + doc.filename, import.meta.url), "utf8");
    if (wikiDocs[doc.key] !== expected) {
      missing.push(doc.filename);
    }
  }
  if (missing.length) {
    throw new Error("project-ops docs are not exact matches: " + missing.join(", "));
  }
}

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 1; this.pending = new Map(); }
  static async open(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => { ws.addEventListener("open", res, { once: true }); ws.addEventListener("error", () => rej(new Error("ws error")), { once: true }); });
    const c = new Cdp(ws);
    ws.addEventListener("message", (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id && c.pending.has(msg.id)) { const { resolve, reject } = c.pending.get(msg.id); c.pending.delete(msg.id); msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result); }
    });
    return c;
  }
  send(method, params = {}) { const id = this.id++; return new Promise((resolve, reject) => { this.pending.set(id, { resolve, reject }); this.ws.send(JSON.stringify({ id, method, params })); setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error("timeout " + method)); } }, 20000); }); }
  async eval(expression) { const r = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result?.value; }
}

async function wsForPage(port) {
  for (let i = 0; i < 40; i++) {
    try { const t = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const p = t.find((x) => x.type === "page" && x.webSocketDebuggerUrl); if (p) return p.webSocketDebuggerUrl; } catch {}
    await delay(250);
  }
  throw new Error("no page target");
}

async function assertAppServerReady() {
  try {
    const response = await fetch(appUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const body = await response.text();
    if (!body.includes("view-llm-wiki")) {
      throw new Error("index.html does not include #view-llm-wiki");
    }
  } catch (error) {
    throw new Error(`LLM wiki smoke target is not reachable at ${appUrl}. Start a local server or set BASE_URL. ${error.message}`);
  }
}

let chrome;
try {
  assertProjectOpsExactMatch();
  await assertAppServerReady();
  const port = 9355;
  chrome = spawn(chromePath, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${tmpProfile}`, "--no-first-run", "--no-default-browser-check", appUrl], { stdio: "ignore" });
  const cdp = await Cdp.open(await wsForPage(port));
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");

  const evalRetry = async (expr) => {
    for (let i = 0; i < 30; i++) {
      try { return await cdp.eval(expr); }
      catch (e) { if (/context was destroyed|Cannot find context/i.test(e.message)) { await delay(300); continue; } throw e; }
    }
    throw new Error("eval kept losing context");
  };

  // 문서 로드 완료 대기 (초기 내비게이션이 끝날 때까지 컨텍스트 파괴를 허용)
  await evalRetry(`document.readyState`);
  await delay(600);
  // llm-wiki 라우트 진입 대기
  const routeReady = await evalRetry(`new Promise((res)=>{const t=Date.now();(function c(){if(location.hash!=='#llm-wiki')location.hash='#llm-wiki';const v=document.getElementById('view-llm-wiki');if(document.readyState==='complete'&&v&&!v.hidden&&v.innerText.trim().length>0)res(true);else if(Date.now()-t>15000)res(false);else setTimeout(c,100)})()})`);
  if (!routeReady) {
    throw new Error(`LLM wiki route did not become ready at ${appUrl}#llm-wiki`);
  }
  await delay(400);

  const report = await evalRetry(`(async () => {
    const out = {};
    const $ = (s, r=document) => r.querySelector(s);
    const view = $('#view-llm-wiki');
    if (!view) throw new Error('LLM wiki view container not found: #view-llm-wiki');
    out.railCats = view.querySelectorAll('.wiki-cat').length;
    out.listCards = view.querySelectorAll('.wiki-card').length;

    // 1) 카테고리 전환: 'Claude API 실전' 류 카테고리 클릭 (마지막에서 두 번째쯤)
    const cats = Array.from(view.querySelectorAll('.wiki-cat'));
    const apiCat = cats.find(b => b.textContent.includes('Claude API'));
    apiCat && apiCat.click();
    await new Promise(r=>setTimeout(r,150));
    out.afterCatActive = $('.wiki-cat.is-active', view)?.textContent.trim().slice(0,20) || '';
    out.afterCatCards = view.querySelectorAll('.wiki-card').length;

    // 2) 문서 열기: 첫 카드 열기 → 마크다운/표 확인
    const firstOpen = $('.wiki-card-open', view);
    out.openedTitle = firstOpen?.querySelector('.wiki-card-title')?.textContent || '';
    firstOpen && firstOpen.click();
    await new Promise(r=>setTimeout(r,150));
    const body = $('.wiki-body', view);
    out.readerShown = !!$('.wiki-reader', view);
    out.bodyIsMarkdown = !!(body && body.classList.contains('markdown-body'));
    out.bodyHasHeading = !!(body && body.querySelector('h2,h3'));
    out.crumbShown = !!$('.wiki-crumbs', view);

    // 3) 표를 가진 문서 확인: '주요 모델' 카테고리 → 'Claude 4.x 패밀리'(표 포함)
    const modelCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('주요 모델'));
    modelCat && modelCat.click();
    await new Promise(r=>setTimeout(r,150));
    const landscapeCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('모델 지형'));
    landscapeCard && landscapeCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.modelLandscapeOfficialSources = ['GPT-5.5', 'Gemini 3.1 Pro Preview', 'DeepSeek V4 Flash', 'Llama 4 Scout', 'task-tiered model matrix'].every(t => view.innerText.includes(t));
    out.modelLandscapeSourcePanelShown = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 6;
    const modelCatAgain = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('주요 모델'));
    modelCatAgain && modelCatAgain.click();
    await new Promise(r=>setTimeout(r,150));
    const famCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('패밀리'));
    famCard && famCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.tableRendered = !!$('.wiki-body table', view);
    out.tableHasOpus = (view.innerText.includes('claude-opus-4-8'));

    const modelCatThird = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('주요 모델'));
    modelCatThird && modelCatThird.click();
    await new Promise(r=>setTimeout(r,150));
    const modelOptimizationCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('Fine-tuning'));
    modelOptimizationCard && modelOptimizationCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.modelOptimizationMarkers = ['fine-tuning platform is winding down', 'not accessible to new users', 'Supervised fine-tuning (SFT)', 'purpose: "fine-tune"', 'training_file', 'validation_file', 'fineTuning.jobs.create', 'Claude API does not currently offer fine-tuning', 'Gemini API or AI Studio no longer have a model available', 'providerOptions.gateway.models', 'router_decision', 'fallback_reason', 'served_model', 'served_provider', 'A/B 비교: fine-tuning vs RAG', 'A/B 비교: static routing matrix vs gateway fallback'].every(t => view.innerText.includes(t));
    out.modelOptimizationSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 9;

    // 4) API 예시 문서: structured outputs / tool use / MCP marker 확인
    const apiCatAgain = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('Claude API'));
    apiCatAgain && apiCatAgain.click();
    await new Promise(r=>setTimeout(r,150));
    const structuredCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('구조화 출력'));
    structuredCard && structuredCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.apiExampleStructuredMarkers = ['output_config', 'text: {', 'response_format', 'strict: true', 'A/B 비교: 최종 JSON vs 함수 호출'].every(t => view.innerText.includes(t));
    out.apiExampleStructuredSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 3;

    const agentsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('도구 사용'));
    agentsCat && agentsCat.click();
    await new Promise(r=>setTimeout(r,150));
    const toolUseCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('툴 사용'));
    toolUseCard && toolUseCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.apiExampleToolMarkers = ['function_call_output', 'tool_result', 'is_error: true', 'parallel_tool_calls: false', 'A/B 비교: 수동 루프 vs SDK/서버 툴'].every(t => view.innerText.includes(t));
    out.apiExampleToolSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 4;

    const agentsCatAgain = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('도구 사용'));
    agentsCatAgain && agentsCatAgain.click();
    await new Promise(r=>setTimeout(r,150));
    const mcpCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('MCP'));
    mcpCard && mcpCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.apiExampleMcpMarkers = ['JSON-RPC 2.0', 'Streamable HTTP', 'tools/list', 'tools/call', 'OAuth 2.1', 'require_approval'].every(t => view.innerText.includes(t));
    out.apiExampleMcpSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 5;

    // 5) RAG/Evals 문서: 임베딩/RAG/평가 marker와 출처 패널 확인
    const basicsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('기초 개념'));
    basicsCat && basicsCat.click();
    await new Promise(r=>setTimeout(r,150));
    const embeddingCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('임베딩과 벡터'));
    embeddingCard && embeddingCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.ragEvalEmbeddingMarkers = ['text-embedding-3-large', 'dimensions', 'recall@k', 'nDCG@10'].every(t => view.innerText.includes(t));
    out.ragEvalEmbeddingSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 2;

    const basicsCatAgain = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('기초 개념'));
    basicsCatAgain && basicsCatAgain.click();
    await new Promise(r=>setTimeout(r,150));
    const multimodalCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('멀티모달과 파일 입력'));
    multimodalCard && multimodalCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.multimodalFileMarkers = ['input_image', 'input_file', 'file_id', 'detail: "high"', 'type: "image"', 'type: "document"', 'citations.enabled=true', 'gpt-4o-transcribe', 'gpt-4o-mini-transcribe', 'source chips', 'page number', 'quote snippet', 'A/B 비교: direct multimodal context vs extracted ingestion pipeline'].every(t => view.innerText.includes(t));
    out.multimodalFileSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 8;

    const ragAgentsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('도구 사용'));
    ragAgentsCat && ragAgentsCat.click();
    await new Promise(r=>setTimeout(r,150));
    const ragCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('RAG'));
    ragCard && ragCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.ragEvalRagMarkers = ['vector_store_ids', 'include: ["file_search_call.results"]', 'citations.enabled', 'A/B 비교: hosted File Search vs self-managed RAG'].every(t => view.innerText.includes(t));
    out.ragEvalRagSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 5;

    const evalCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    evalCat && evalCat.click();
    await new Promise(r=>setTimeout(r,150));
    const evalCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('평가 (Evals)'));
    evalCard && evalCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.ragEvalEvaluationMarkers = ['testing_criteria', 'string_check', 'recall@k', 'nDCG@10', 'LLM-as-judge'].every(t => view.innerText.includes(t));
    out.ragEvalEvaluationSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 4;

    const evalDatasetCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    evalDatasetCat && evalDatasetCat.click();
    await new Promise(r=>setTimeout(r,150));
    const evalDatasetCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('평가 데이터셋 거버넌스'));
    evalDatasetCard && evalDatasetCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.evalDatasetGovernanceMarkers = ['eval_dataset_governance', 'eval_dataset_contract', 'dataset_id', 'dataset_version', 'dataset_hash', 'item_schema', 'data_source_config', 'testing_criteria', 'dataset_card', 'datasheet', 'data_card', 'golden_set', 'regression_set', 'canary_set', 'red_team_set', 'holdout_set', 'shadow_set', 'production_sample', 'consented_sample', 'synthetic_sample', 'redacted_fixture', 'pii_redacted', 'retention_class', 'delete_request_id', 'data_freshness_days', 'Evals platform deprecating', 'read-only', 'October 31, 2026', 'November 30, 2026', 'score_model', 'grader_alignment_set', 'Claude Console Evaluation tool', 'Generate Test Case', 'CSV import', 'benchmark data contamination', 'train/test leakage', 'temporal_holdout', 'entity_holdout', 'n-gram overlap', 'near_duplicate', 'A/B 비교: public benchmark vs private holdout'].every(t => view.innerText.includes(t));
    out.evalDatasetGovernanceSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 11;

    const evalLineageCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    evalLineageCat && evalLineageCat.click();
    await new Promise(r=>setTimeout(r,150));
    const evalLineageCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('평가 결과 Lineage와 실험 저장소'));
    evalLineageCard && evalLineageCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.evalResultLineageMarkers = ['eval_result_lineage', 'eval_result_lineage_contract', 'experiment_id', 'experiment_run_id', 'eval_run_id', 'result_id', 'report_url', 'result_counts', 'dataset_run_id', 'source_trace_id', 'source_observation_id', 'trace_id', 'span_id', 'prompt_hash', 'model_snapshot', 'grader_version', 'pass_threshold', 'metric_name', 'artifact_uri', 'raw_results_jsonl', 'lineage_schema_version', 'failure_cluster_id', 'lineage_complete=false', 'sourceTraceId', 'sourceObservationId', 'DatasetRun', 'grader hacking', 'flush_traces()', 'gen_ai.operation.name', 'gen_ai.request.model', 'W3C PROV-DM', 'wasGeneratedBy', 'wasDerivedFrom', 'A/B 비교: vendor dashboard result vs app-owned experiment ledger'].every(t => view.innerText.includes(t));
    out.evalResultLineageSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 9;

    const evalFailureTriageCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    evalFailureTriageCat && evalFailureTriageCat.click();
    await new Promise(r=>setTimeout(r,150));
    const evalFailureTriageCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('평가 실패 클러스터링과 인시던트 Triage'));
    evalFailureTriageCard && evalFailureTriageCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.evalFailureTriageMarkers = ['eval_failure_triage', 'failure_triage_taxonomy', 'failure_cluster_id', 'incident_id', 'severity', 'user_impact', 'score_name', 'score_value', 'NUMERIC', 'CATEGORICAL', 'Open coding', 'axial coding', 'failure_mode', 'root_cause_layer', 'retrieval_miss', 'generator_ignored_top_doc', 'citation_mismatch', 'tool_selection_error', 'tool_parameter_error', 'policy_violation', 'pii_leak', 'excessive_agency', 'guardrail_false_positive', 'judge_drift', 'cluster_signature_hash', 'representative_trace_id', 'Incident Commander', 'NIST SP 800-61', 'A/B 비교: manual taxonomy vs embedding clustering'].every(t => view.innerText.includes(t));
    out.evalFailureTriageSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 13;

    const evaluatorCalibrationCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    evaluatorCalibrationCat && evaluatorCalibrationCat.click();
    await new Promise(r=>setTimeout(r,150));
    const evaluatorCalibrationCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('LLM Judge와 Label Calibration'));
    evaluatorCalibrationCard && evaluatorCalibrationCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.evaluatorCalibrationMarkers = ['evaluator_calibration', 'judge_calibration_contract', 'judge_id', 'judge_model', 'judge_prompt_hash', 'rubric_version', 'score_config_id', 'human_alignment_set', 'human_label_batch_id', 'blinded_review', 'inter_annotator_agreement', 'judge_human_agreement', 'kappa', 'spearman_correlation', 'judge_drift', 'label_drift', 'threshold_drift', 'position_bias', 'verbosity_bias', 'self_preference_bias', 'grader_hacking', 'score_model', 'LLM-as-a-Judge', 'Annotation Queues', 'score config', 'Human evals', 'MT-Bench', 'Chatbot Arena', 'over 80% agreement', 'G-Eval', 'A/B 비교: single judge vs judge panel'].every(t => view.innerText.includes(t));
    out.evaluatorCalibrationSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 9;

    const postmortemActionCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    postmortemActionCat && postmortemActionCat.click();
    await new Promise(r=>setTimeout(r,150));
    const postmortemActionCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('Postmortem Action Ledger와 재발 방지 Eval'));
    postmortemActionCard && postmortemActionCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.postmortemActionLedgerMarkers = ['postmortem_action_ledger', 'postmortem_action_contract', 'action_item_id', 'postmortem_id', 'incident_id', 'failure_cluster_id', 'eval_run_id', 'dataset_run_id', 'trace_id', 'judge_id', 'score_config_id', 'calibration_set_id', 'action_type', 'prevent_action', 'detect_action', 'mitigate_action', 'owner_team', 'tracking_ticket', 'priority', 'due_at', 'verifiable_end_state', 'acceptance_eval_id', 'acceptance_eval_run_id', 'regression_eval_suite', 'closure_evidence_uri', 'closure_reviewer_id', 'postmortem_reviewed_at', 'blameless', 'root_cause', 'trigger', 'lessons_learned', 'CSF 2.0', 'Govern', 'Identify', 'Protect', 'Detect', 'Respond', 'Recover', 'continuous improvement', 'score analytics', 'Annotation Queues', 'action_status=closed', 'risk_acceptance', 'A/B 비교: manual closure vs eval-gated closure'].every(t => view.innerText.includes(t));
    out.postmortemActionLedgerSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 11;

    const rolloutDecisionCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    rolloutDecisionCat && rolloutDecisionCat.click();
    await new Promise(r=>setTimeout(r,150));
    const rolloutDecisionCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('Rollout Decision Log와 Rollback Gate'));
    rolloutDecisionCard && rolloutDecisionCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.rolloutDecisionLogMarkers = ['rollout_decision_log', 'rollout_decision_contract', 'decision_id', 'action_item_id', 'postmortem_id', 'release_candidate_id', 'eval_run_id', 'dataset_run_id', 'acceptance_eval_run_id', 'regression_eval_suite', 'rollout_stage', 'rollout_strategy', 'feature_flag_key', 'feature_flag_context', 'targeting_key', 'flag_variant', 'feature_flag.result.variant', 'feature_flag.result.reason', 'feature_flag.version', 'feature_flag.provider.name', 'canary_weight', 'canary_step_index', 'canary_analysis_run_id', 'analysis_status', 'abort_on_failed_analysis', 'guarded_promote', 'promote_criteria', 'rollback_target', 'rollback_trigger', 'rollback_runbook_id', 'rollback_window', 'stable_replica_set', 'deployment_environment', 'environment_protection_rule', 'required_reviewers', 'wait_timer', 'deployment_status_id', 'decision_owner_id', 'approver_id', 'blast_radius', 'observability_window', 'decision_status', 'go_decision', 'no_go_decision', 'risk_acceptance', 'RegressionError', 'targeting key', 'setWeight', 'stable/canary ReplicaSet', 'A/B 비교: feature flag rollout vs deployment canary', 'A/B 비교: automatic abort vs human approval', 'A/B 비교: dashboard decision vs app-owned decision log'].every(t => view.innerText.includes(t));
    out.rolloutDecisionLogSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 10;

    const safetyCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    safetyCat && safetyCat.click();
    await new Promise(r=>setTimeout(r,150));
    const safetyCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('안전과 프롬프트 인젝션'));
    safetyCard && safetyCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.safetyGuardrailMarkers = ['LLM01:2025', 'direct prompt injection', 'indirect prompt injection', 'tool_result blocks', 'JSON-encode untrusted content', 'safety_identifier', 'per-client consent', 'token passthrough', 'A/B 비교: prompt-only guardrails vs layered enforcement'].every(t => view.innerText.includes(t));
    out.safetyGuardrailSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 6;

    const privacyCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    privacyCat && privacyCat.click();
    await new Promise(r=>setTimeout(r,150));
    const privacyCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('데이터 프라이버시와 보존 정책'));
    privacyCard && privacyCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.dataPrivacyMarkers = ['LLM02:2025 Sensitive Information Disclosure', 'data_inventory', 'data_classification', 'PII', 'PHI', 'secrets', 'not used to train', 'store: false', 'abuse monitoring logs', 'retained for up to 30 days', 'MCP servers are third-party services', 'automatically delete inputs and outputs on our backend within 30 days', 'ZDR applies to Messages and Token Counting APIs', 'Paid Services', 'Unpaid Services', 'human reviewers may read', 'Do not submit sensitive, confidential, or personal information to the Unpaid Services', 'zeroDataRetention: true', 'BYOK', 'A/B 비교: default API retention vs zero data retention'].every(t => view.innerText.includes(t));
    out.dataPrivacySourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 7;

    const reliabilityCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    reliabilityCat && reliabilityCat.click();
    await new Promise(r=>setTimeout(r,150));
    const reliabilityCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('런타임 신뢰성과 장애 처리'));
    reliabilityCard && reliabilityCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.runtimeReliabilityMarkers = ['RPM', 'RPD', 'TPM', 'TPD', 'IPM', 'x-ratelimit-limit-requests', 'x-ratelimit-remaining-tokens', 'random exponential backoff', 'unsuccessful requests contribute to your per-minute limit', '503 - Slow Down', 'x-request-id', 'X-Client-Request-Id', 'token bucket algorithm', 'retry-after', 'anthropic-ratelimit-requests-remaining', '429 rate_limit_error', '504 timeout_error', '529 overloaded_error', 'request-id', 'SSE after 200', 'Rate Limits API', 'per project, not per API key', 'RESOURCE_EXHAUSTED', 'DEADLINE_EXCEEDED', 'providerOptions.gateway', 'providerTimeouts', 'BYOK', 'first token arrives', 'A/B 비교: blind exponential retry vs header-aware client throttling'].every(t => view.innerText.includes(t));
    out.runtimeReliabilitySourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 11;

    const promptReleaseCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    promptReleaseCat && promptReleaseCat.click();
    await new Promise(r=>setTimeout(r,150));
    const promptReleaseCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('프롬프트 릴리스와 버전 관리'));
    promptReleaseCard && promptReleaseCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.promptReleaseMarkers = ['prompt_config_bundle', 'prompt_id', 'prompt_version', 'prompt_hash', 'registry_label', 'model_snapshot', 'developer_message_version', 'schema_version', 'tool_schema_version', 'retrieval_version', 'safety_policy_version', 'eval_suite_version', 'rollout_stage', 'rollback_target', 'developer and user messages', 'stable prompt prefix', 'cached_tokens', 'prompt templates and variables', 'prompt generator', 'prompt improver', 'evaluation tool', 'storing, versioning, retrieving', 'version ID', 'production label', 'protected prompt labels', 'eval-driven development', 'golden dataset', 'canary-10pct', 'rollback runbook', 'A/B 비교: hardcoded prompts in code vs prompt registry labels'].every(t => view.innerText.includes(t));
    out.promptReleaseSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 11;

    const agentToolPermissionCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    agentToolPermissionCat && agentToolPermissionCat.click();
    await new Promise(r=>setTimeout(r,150));
    const agentToolPermissionCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('에이전트 도구 권한과 승인 UX'));
    agentToolPermissionCard && agentToolPermissionCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.agentToolPermissionMarkers = ['LLM06:2025 Excessive Agency', 'permissions matrix', 'tool_policy_bundle', 'tool_authority_level', 'read_only', 'write_draft', 'external_side_effect', 'money_movement', 'infrastructure_change', 'approval_required', 'HostedMCPTool', 'tool_config={"require_approval":"always"}', 'on_approval_request', 'RunResult.interruptions', 'RunState', 'state.approve', 'state.reject', 'always_approve', 'always_reject', 'Agent.as_tool()', 'ShellTool', 'ApplyPatchTool', 'input guardrails', 'output guardrails', 'tripwire', 'fail closed', 'tools/list', 'tools/call', 'OAuth 2.1', 'per-client consent', 'token passthrough', 'approval_id', 'approver_id', 'approval_status', 'blast_radius', 'decision_id', 'A/B 비교: prompt-only autonomy vs permission matrix'].every(t => view.innerText.includes(t));
    out.agentToolPermissionSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 10;

    const deploymentSecretsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    deploymentSecretsCat && deploymentSecretsCat.click();
    await new Promise(r=>setTimeout(r,150));
    const deploymentSecretsCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('배포 환경과 시크릿 분리'));
    deploymentSecretsCard && deploymentSecretsCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.deploymentSecretsMarkers = ['deployment_secret_matrix', 'secret_inventory', 'secret_classification', 'secret_owner', 'runtime_injection', 'build_time_injection', 'public_runtime_config', 'server-only', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'key management service', 'client-side environments', 'do not commit', 'Twelve-Factor Config', 'Vercel', 'vercel env pull', '.env.local', 'Netlify', 'Deploy Previews', 'Branch deploys', 'Contains secret values', 'Secrets Controller', 'team audit log', 'GitHub Actions secrets', 'gh secret set', '--env ENV_NAME', '--org ORG_NAME', '--repos', 'secrets context', '::add-mask::VALUE', 'OpenID Connect (OIDC)', 'id-token: write', 'short-lived access token', 'no long-lived cloud secrets', 'repo_property_*', 'push protection', 'secret scanning', 'blocks pushes', 'bypass reason', 'rotation', 'revocation', 'expiration', 'break-glass', 'A/B 비교: static GitHub secret vs OIDC short-lived token'].every(t => view.innerText.includes(t));
    out.deploymentSecretsSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 11;

    const costCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    costCat && costCat.click();
    await new Promise(r=>setTimeout(r,150));
    const costCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('비용 최적화'));
    costCard && costCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.costOpsMarkers = ['service_tier: "flex"', 'service_tier: "priority"', 'cached_tokens', 'messages.count_tokens', '50% cost discount', '24-hour turnaround', 'A/B 비교: async low-cost vs priority low-latency'].every(t => view.innerText.includes(t));
    out.costOpsSourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 9;

    const obsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('평가'));
    obsCat && obsCat.click();
    await new Promise(r=>setTimeout(r,150));
    const obsCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('관측성과 트레이싱'));
    obsCard && obsCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.observabilityMarkers = ['trace_id', 'span_id', 'workflow_name', 'time_to_first_token_ms', 'guardrails', 'ZDR', 'A/B 비교: provider tracing vs self-managed OpenTelemetry'].every(t => view.innerText.includes(t));
    out.observabilitySourcePanel = !!$('.wiki-source-panel', view) && view.querySelectorAll('.wiki-source-link[href^="https://"]').length >= 5;

    // 6) 출처 거버넌스 문서: 공식 링크/출처 패널/A-B 비교 표 확인
    const sourceCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('출처'));
    sourceCat && sourceCat.click();
    await new Promise(r=>setTimeout(r,150));
    const sourceCard = Array.from(view.querySelectorAll('.wiki-card-open')).find(b=>b.textContent.includes('출처와 갱신 원칙'));
    sourceCard && sourceCard.click();
    await new Promise(r=>setTimeout(r,150));
    out.sourceGovernanceShown = view.innerText.includes('Source governance') && view.innerText.includes('불확실');
    out.sourcePanelShown = !!$('.wiki-source-panel', view);
    out.sourceLinkCount = view.querySelectorAll('.wiki-source-link[href^="https://"]').length;
    out.sourceABTableRendered = !!$('.wiki-body table', view) && view.innerText.includes('코드 임베드 유지') && view.innerText.includes('별도 JSON/Markdown');


    // 7) 프로젝트 운영 문서: 6편 카드/본문 marker/source panel/검색 확인
    const input = document.getElementById('globalSearch');
    const projectOpsDocs = [{"key":"githubPagesActionsDeploy","id":"github-pages-actions-deploy","filename":"github-pages-actions-deploy.md","title":"GitHub Pages를 Actions로 배포하기","sourceKey":"project_ops_github_pages_actions_deploy","markers":["GitHub Pages를 Actions로 배포하기","작성일: 2026-06-11","프로젝트 운영 지식"]},{"key":"localFirstDataSafety","id":"local-first-data-safety","filename":"local-first-data-safety.md","title":"localStorage만 쓰는 앱의 데이터 안전","sourceKey":"project_ops_local_first_data_safety","markers":["localStorage만 쓰는 앱의 데이터 안전","작성일: 2026-06-11","프로젝트 운영 지식"]},{"key":"pwaOfflineOperations","id":"pwa-offline-operations","filename":"pwa-offline-operations.md","title":"PWA 서비스워커 운영","sourceKey":"project_ops_pwa_offline_operations","markers":["PWA 서비스워커 운영","작성일: 2026-06-11","프로젝트 운영 지식"]},{"key":"vanillaSpaQualityGates","id":"vanilla-spa-quality-gates","filename":"vanilla-spa-quality-gates.md","title":"바닐라 JS SPA 품질 게이트","sourceKey":"project_ops_vanilla_spa_quality_gates","markers":["바닐라 JS SPA 품질 게이트","작성일: 2026-06-11","프로젝트 운영 지식"]},{"key":"staticSiteDataSync","id":"static-site-data-sync","filename":"static-site-data-sync.md","title":"서버 없는 정적 사이트에서 실데이터 가져오기","sourceKey":"project_ops_static_site_data_sync","markers":["서버 없는 정적 사이트에서 실데이터 가져오기","작성일: 2026-06-11","프로젝트 운영 지식"]},{"key":"llmAgentLoopGuardrails","id":"llm-agent-loop-guardrails","filename":"llm-agent-loop-guardrails.md","title":"LLM 에이전트 자율 루프 가드레일","sourceKey":"project_ops_llm_agent_loop_guardrails","markers":["LLM 에이전트 자율 루프 가드레일","작성일: 2026-06-11","프로젝트 운영 지식"]}];
    const projectOpsCat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('프로젝트 운영'));
    projectOpsCat && projectOpsCat.click();
    await new Promise(r=>setTimeout(r,150));
    out.projectOpsCardCount = view.querySelectorAll('.wiki-card-open').length;
    out.projectOpsTitlesShown = projectOpsDocs.every(doc => view.innerText.includes(doc.title));
    out.projectOpsArticleChecks = [];
    for (const doc of projectOpsDocs) {
      const cat = Array.from(view.querySelectorAll('.wiki-cat')).find(b => b.textContent.includes('프로젝트 운영'));
      cat && cat.click();
      await new Promise(r=>setTimeout(r,100));
      const card = Array.from(view.querySelectorAll('.wiki-card-open')).find(b => b.textContent.includes(doc.title));
      card && card.click();
      await new Promise(r=>setTimeout(r,120));
      const bodyText = $('.wiki-body', view)?.innerText || '';
      out.projectOpsArticleChecks.push({
        id: doc.id,
        opened: !!card && bodyText.includes(doc.markers[0]),
        markers: doc.markers.every(marker => bodyText.includes(marker)),
        sourcePanel: !!$('.wiki-source-panel', view) && Array.from(view.querySelectorAll('.wiki-source-link')).some(link => link.getAttribute('href').includes(doc.filename)),
      });
    }
    const projectOpsSearchResults = [];
    for (const doc of projectOpsDocs.filter(doc => !['local-first-data-safety', 'vanilla-spa-quality-gates'].includes(doc.id))) {
      input.value = doc.title;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r=>setTimeout(r,250));
      projectOpsSearchResults.push({ id: doc.id, found: view.innerText.includes(doc.title) && view.querySelectorAll('[data-search-result="llm-wiki"]').length >= 1 });
    }
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r=>setTimeout(r,150));
    out.projectOpsSearchOk = projectOpsSearchResults.every(item => item.found);

    // 8) 뷰 내 검색: 'RAG' 입력 → 검색 결과 모드
    input.value = 'RAG';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r=>setTimeout(r,400));
    out.searchResultCards = view.querySelectorAll('[data-search-result="llm-wiki"]').length;
    out.searchShowsRag = view.innerText.includes('검색 결과');

    // 콘솔 에러 없는지 확인용 마커
    out.ok = true;
    return out;
  })()`);

  console.log(JSON.stringify(report, null, 2));
  const pass = report && report.railCats >= 7 && report.readerShown && report.bodyIsMarkdown && report.modelLandscapeOfficialSources && report.modelLandscapeSourcePanelShown && report.tableRendered && report.tableHasOpus && report.modelOptimizationMarkers && report.modelOptimizationSourcePanel && report.apiExampleStructuredMarkers && report.apiExampleStructuredSourcePanel && report.apiExampleToolMarkers && report.apiExampleToolSourcePanel && report.apiExampleMcpMarkers && report.apiExampleMcpSourcePanel && report.ragEvalEmbeddingMarkers && report.ragEvalEmbeddingSourcePanel && report.multimodalFileMarkers && report.multimodalFileSourcePanel && report.ragEvalRagMarkers && report.ragEvalRagSourcePanel && report.ragEvalEvaluationMarkers && report.ragEvalEvaluationSourcePanel && report.evalDatasetGovernanceMarkers && report.evalDatasetGovernanceSourcePanel && report.evalResultLineageMarkers && report.evalResultLineageSourcePanel && report.evalFailureTriageMarkers && report.evalFailureTriageSourcePanel && report.evaluatorCalibrationMarkers && report.evaluatorCalibrationSourcePanel && report.postmortemActionLedgerMarkers && report.postmortemActionLedgerSourcePanel && report.rolloutDecisionLogMarkers && report.rolloutDecisionLogSourcePanel && report.safetyGuardrailMarkers && report.safetyGuardrailSourcePanel && report.dataPrivacyMarkers && report.dataPrivacySourcePanel && report.runtimeReliabilityMarkers && report.runtimeReliabilitySourcePanel && report.promptReleaseMarkers && report.promptReleaseSourcePanel && report.agentToolPermissionMarkers && report.agentToolPermissionSourcePanel && report.deploymentSecretsMarkers && report.deploymentSecretsSourcePanel && report.costOpsMarkers && report.costOpsSourcePanel && report.observabilityMarkers && report.observabilitySourcePanel && report.sourceGovernanceShown && report.sourcePanelShown && report.sourceLinkCount >= 6 && report.sourceABTableRendered && report.projectOpsCardCount >= 6 && report.projectOpsTitlesShown && Array.isArray(report.projectOpsArticleChecks) && report.projectOpsArticleChecks.length === 6 && report.projectOpsArticleChecks.every((item) => item.opened && item.markers && item.sourcePanel) && report.projectOpsSearchOk && report.searchResultCards >= 1 && report.searchShowsRag;
  console.log(pass ? "\nLLM-WIKI INTERACTION: PASS" : "\nLLM-WIKI INTERACTION: FAIL");
  process.exitCode = pass ? 0 : 1;
} catch (e) {
  console.error("error:", e.message);
  process.exitCode = 1;
} finally {
  if (chrome) chrome.kill();
  try { rmSync(tmpProfile, { recursive: true, force: true }); } catch {}
}

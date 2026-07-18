#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const rawArgs = process.argv.slice(2);
const write = rawArgs.includes("--write");
const markdown = rawArgs.includes("--markdown");
const repo = argValue("--repo") || suggestedRepoFromRemote() || "OWNER/REPO";
const inputRel = argValue("--input") || "";
const outRel = argValue("--out") || "data/pages-attestation-proof.json";
const outMarkdownRel = argValue("--out-markdown") || "data/pages-attestation-proof.md";
const generatedAt = new Date().toISOString();

const proofFields = [
  {
    key: "pages_workflow_run",
    label: "Pages workflow run",
    required: "Successful joopark-pages.yml run URL plus headSha.",
    validate: (value) => /github\.com\/[^/\s]+\/[^/\s]+\/actions\/runs\/\d+/i.test(value) && /headSha[:=\s]+[0-9a-f]{7,40}/i.test(value),
  },
  {
    key: "attestation_url",
    label: "Attestation URL",
    required: "actions/attest attestation-url output.",
    validate: (value) => new RegExp(`https://github\\.com/${escapeRegExp(repo)}/attestations/\\d+`, "i").test(value),
  },
  {
    key: "attestation_id",
    label: "Attestation ID",
    required: "actions/attest attestation-id output.",
    validate: (value) => /^\d{3,}$/.test(value.trim()),
  },
  {
    key: "manifest_verify",
    label: "Manifest verification",
    required: "Passing gh attestation verify output for dist/release/release-manifest.json.",
    validate: (value) => proofVerifySucceeded(value) && value.includes("dist/release/release-manifest.json"),
  },
  {
    key: "index_verify",
    label: "Index verification",
    required: "Passing gh attestation verify output for dist/release/index.html.",
    validate: (value) => proofVerifySucceeded(value) && value.includes("dist/release/index.html"),
  },
  {
    key: "predicate_type",
    label: "Predicate type",
    required: "SLSA build provenance predicate.",
    validate: (value) => value.includes("https://slsa.dev/provenance/v1"),
  },
];

function argValue(name) {
  return optionValue(rawArgs, name);
}

function optionValue(argsList, name) {
  const inline = argsList.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = argsList.indexOf(name);
  if (index < 0) return "";
  const value = argsList[index + 1] || "";
  return value.startsWith("--") ? "" : value;
}

function gitText(argsList) {
  try {
    return execFileSync("git", argsList, {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "";
  }
}

function githubNameWithOwner(remoteUrl) {
  const trimmed = String(remoteUrl || "").trim();
  const httpsMatch = trimmed.match(/^https:\/\/github\.com\/([^/]+)\/(.+?)(?:\.git)?$/i);
  if (httpsMatch) return `${httpsMatch[1]}/${httpsMatch[2].replace(/\.git$/i, "")}`;
  const sshMatch = trimmed.match(/^(?:git@github\.com:|ssh:\/\/git@github\.com\/)([^/]+)\/(.+?)(?:\.git)?$/i);
  if (sshMatch) return `${sshMatch[1]}/${sshMatch[2].replace(/\.git$/i, "")}`;
  return "";
}

function suggestedRepoFromRemote() {
  const remotes = gitText(["remote"]).split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const remoteName = remotes.includes("biojuho-projects") ? "biojuho-projects" : remotes.includes("origin") ? "origin" : remotes[0] || "";
  if (!remoteName) return "";
  return githubNameWithOwner(gitText(["config", "--get", `remote.${remoteName}.url`]));
}

function readText(relPath) {
  if (!relPath) return "";
  try {
    return readFileSync(resolve(root, relPath), "utf-8");
  } catch {
    return "";
  }
}

function writeText(relPath, text) {
  const target = resolve(root, relPath);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, text, "utf-8");
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function valueOrPending(value) {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined || value === "") return "not available";
  return String(value);
}

function proofVerifySucceeded(value) {
  const text = String(value || "").toLowerCase();
  if (/gh attestation verify\s+dist\/release\//i.test(text) && !/(verified|verification succeeded|passed|valid|✓|success)/i.test(text)) {
    return false;
  }
  return /(verified|verification succeeded|passed|valid|✓|success)/i.test(text);
}

function parserReadyTemplate() {
  return [
    "pages_workflow_run:",
    "attestation_url:",
    "attestation_id:",
    "manifest_verify:",
    "index_verify:",
    "predicate_type:",
    "bundle_path:",
  ].join("\n");
}

function actualValue(value) {
  const text = String(value || "").trim();
  if (!text) return false;
  if (/^\[[^\]]+\]$/.test(text)) return false;
  if (/(paste|pending|not available|blocked_until|expected shape|after the Pages workflow run|todo)/i.test(text)) return false;
  return true;
}

function fieldLinePattern(key) {
  return new RegExp(`^\\s*(?:[-*]\\s*)?${escapeRegExp(key)}\\s*[:=][^\\S\\r\\n]*(.*)$`, "i");
}

function startsFieldLine(line) {
  return /^\s*(?:[-*]\s*)?[a-z_]+\s*[:=]/i.test(line);
}

function extractFieldValue(text, key) {
  const lines = String(text || "").split(/\r?\n/);
  const pattern = fieldLinePattern(key);
  const startIndex = lines.findIndex((line) => pattern.test(line));
  if (startIndex < 0) return "";
  const firstLine = lines[startIndex].match(pattern)?.[1] || "";
  const valueLines = [firstLine];
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    if (startsFieldLine(lines[index])) break;
    valueLines.push(lines[index]);
  }
  return valueLines.join("\n").trim();
}

function parseProofText(text) {
  const fields = proofFields.map((field) => {
    const value = extractFieldValue(text, field.key);
    const present = actualValue(value);
    const valid = present && field.validate(value);
    return {
      key: field.key,
      label: field.label,
      required: field.required,
      value: present ? value : "",
      present,
      valid,
      status: valid ? "pass" : present ? "invalid" : "missing",
    };
  });
  const validFields = fields.filter((field) => field.valid);
  return {
    fields,
    detectedFieldCount: fields.filter((field) => field.present).length,
    validFieldCount: validFields.length,
    missingFields: fields.filter((field) => !field.valid).map((field) => field.key),
    proofComplete: validFields.length === fields.length,
  };
}

function commandSet(targetRepo) {
  return [
    `gh run list --repo ${targetRepo} --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`,
    `gh attestation verify dist/release/release-manifest.json -R ${targetRepo}`,
    `gh attestation verify dist/release/index.html -R ${targetRepo}`,
    `gh attestation verify dist/release/release-manifest.json -R ${targetRepo} --format json --jq '.[].verificationResult.statement.predicateType'`,
  ];
}

function receiptText(payload) {
  return [
    "# JooPark Pages Attestation Proof Capture",
    "",
    `Status: ${payload.proofComplete ? "signed proof fields complete" : "blocked; not signed proof yet"}`,
    `Repo: ${payload.repo}`,
    `Workflow: ${payload.workflow}`,
    `Proof complete: ${valueOrPending(payload.proofComplete)}`,
    `Signed proof ready: ${valueOrPending(payload.signedProofReady)}`,
    `Completed fields: ${payload.completedFieldCount}/${payload.requiredFieldCount}`,
    `False positive guard: ${valueOrPending(payload.falsePositiveGuard)}`,
    "",
    "Parser-ready proof block:",
    parserReadyTemplate(),
    "",
    "Verification commands:",
    ...payload.verificationCommands.map((command) => `- ${command}`),
    "",
    "Missing fields:",
    ...(payload.missingFields.length ? payload.missingFields.map((field) => `- ${field}`) : ["- none"]),
    "",
    "Guard:",
    payload.guard,
  ].join("\n");
}

function markdownText(payload) {
  return [
    "# JooPark Pages Attestation Proof",
    "",
    `- status: ${payload.status}`,
    `- proofComplete: ${valueOrPending(payload.proofComplete)}`,
    `- signedProofReady: ${valueOrPending(payload.signedProofReady)}`,
    `- proofFieldCoverage: ${payload.proofFieldCoverage}`,
    `- completedFieldCount: ${payload.completedFieldCount}/${payload.requiredFieldCount}`,
    `- repo: ${payload.repo}`,
    `- sourceProofInput: ${payload.sourceProofInput || "not provided"}`,
    "",
    "## Fields",
    ...payload.fields.map((field) => `- ${field.key}: ${field.status}`),
    "",
    "## Commands",
    ...payload.verificationCommands.map((command) => `- ${command}`),
    "",
    "## Receipt",
    payload.receipt,
  ].join("\n");
}

const proofText = readText(inputRel);
const parsedProof = parseProofText(proofText);
const templateGuard = parseProofText(parserReadyTemplate());
const verificationCommands = commandSet(repo);
const payload = {
  schemaVersion: "joopark-pages-attestation-proof/v1",
  status: "pass",
  generatedAt,
  source: inputRel ? inputRel : "operator proof input not provided",
  sourceProofInput: inputRel,
  repo,
  workflow: "joopark-pages.yml",
  action: "actions/attest@v4",
  subjectPath: "dist/release/**",
  requiredPermission: "attestations: write",
  proofCaptureReady: true,
  proofComplete: parsedProof.proofComplete,
  signedProofReady: parsedProof.proofComplete,
  verificationOnly: !parsedProof.proofComplete,
  readyForExternalClaim: false,
  proofFieldCoverage: 1,
  requiredFieldCount: proofFields.length,
  detectedFieldCount: parsedProof.detectedFieldCount,
  completedFieldCount: parsedProof.validFieldCount,
  missingFields: parsedProof.missingFields,
  fields: parsedProof.fields,
  parserReadyProofBlock: parserReadyTemplate(),
  verificationCommands,
  commandCount: verificationCommands.length,
  falsePositiveGuard: templateGuard.detectedFieldCount === 0 && templateGuard.validFieldCount === 0 && templateGuard.proofComplete === false,
  falsePositiveGuardDetail: "Blank parser-ready template fields are not treated as completed attestation proof.",
  guard: "Do not claim signed GitHub artifact attestation proof, archive proof, public launch complete, or readyForExternalClaim=true until all required attestation proof fields are valid, both gh attestation verify commands pass, and publish evidence plus launch handoff proof gates are ready.",
  nextAction: parsedProof.proofComplete
    ? {
        key: "capture_live_publish_evidence",
        status: "ready",
        command: `node scripts/capture-publish-evidence.mjs --live --repo ${repo} --write`,
      }
    : {
        key: "fill_pages_attestation_proof",
        status: "action_required",
        command: verificationCommands[0],
      },
  externalComparison: [
    {
      key: "github_artifact_attestation_verify",
      label: "GitHub artifact attestation verification",
      url: "https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations",
      detail: "Use gh attestation verify against the artifact and repository before trusting signed provenance.",
    },
    {
      key: "actions_attest_outputs",
      label: "actions/attest outputs",
      url: "https://github.com/actions/attest",
      detail: "Capture attestation-id, attestation-url, and bundle-path from the action outputs.",
    },
  ],
};
payload.receipt = receiptText(payload);

if (write) {
  writeText(outRel, `${JSON.stringify(payload, null, 2)}\n`);
  if (markdown) writeText(outMarkdownRel, `${markdownText(payload)}\n`);
}

if (markdown) {
  process.stdout.write(`${markdownText(payload)}\n`);
} else {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function rootPath(...parts) {
  return join(root, ...parts);
}

const appPath = rootPath("app.js");
const appText = readFileSync(appPath, "utf-8");
const lines = appText.split(/\r?\n/);

function readOptionalText(relPath) {
  const path = rootPath(relPath);
  return existsSync(path) ? readFileSync(path, "utf-8") : "";
}

function loadModuleTexts(paths) {
  return Object.fromEntries(paths.map((path) => [path, readOptionalText(path)]));
}

const moduleTexts = loadModuleTexts([
  "search-empty-state.js",
  "home-execution-view.js",
  "calendar-view.js",
  "todo-view.js",
  "notes-view.js",
  "habits-view.js",
  "stats-view.js",
  "portfolio-view.js",
  "kanban-view.js",
  "gantt-view.js",
  "team-view.js",
  "workspace-storage.js",
  "storage-status-view.js",
  "settings-view.js",
  "system-status-view.js",
  "backup-import-guards.js",
  "backup-import-ui.js",
  "release-status.js",
  "operations-copy-actions.js",
  "verify-workspace-summary.js",
  "dialog-shell.js",
  "project-picker.js",
  "global-search.js",
  "command-palette.js",
  "db-catalog.js",
  "review-handoff.js",
  "review-result-view.js",
  "review-execution-checklist.js",
  "review-issue-payload.js",
  "review-result-state.js",
  "review-result-draft-state.js",
  "review-creation-actions.js",
  "review-package-view.js",
  "review-artifact-view.js",
  "review-artifact-state.js",
  "review-copy-actions.js",
  "review-submission-copy.js",
  "review-recommendation-export.js",
  "pwa-runtime.js",
]);

const {
  "search-empty-state.js": searchEmptyStateText,
  "home-execution-view.js": homeExecutionViewText,
  "calendar-view.js": calendarViewText,
  "todo-view.js": todoViewText,
  "notes-view.js": notesViewText,
  "habits-view.js": habitsViewText,
  "stats-view.js": statsViewText,
  "portfolio-view.js": portfolioViewText,
  "kanban-view.js": kanbanViewText,
  "gantt-view.js": ganttViewText,
  "team-view.js": teamViewText,
  "workspace-storage.js": workspaceStorageText,
  "storage-status-view.js": storageStatusViewText,
  "settings-view.js": settingsViewText,
  "system-status-view.js": systemStatusViewText,
  "backup-import-guards.js": backupImportGuardsText,
  "backup-import-ui.js": backupImportUiText,
  "release-status.js": releaseStatusText,
  "operations-copy-actions.js": operationsCopyActionsText,
  "verify-workspace-summary.js": verifyWorkspaceSummaryText,
  "dialog-shell.js": dialogShellText,
  "project-picker.js": projectPickerText,
  "global-search.js": globalSearchText,
  "command-palette.js": commandPaletteText,
  "db-catalog.js": dbCatalogText,
  "review-handoff.js": reviewHandoffText,
  "review-result-view.js": reviewResultViewText,
  "review-execution-checklist.js": reviewExecutionChecklistText,
  "review-issue-payload.js": reviewIssuePayloadText,
  "review-result-state.js": reviewResultStateText,
  "review-result-draft-state.js": reviewResultDraftStateText,
  "review-creation-actions.js": reviewCreationActionsText,
  "review-package-view.js": reviewPackageViewText,
  "review-artifact-view.js": reviewArtifactViewText,
  "review-artifact-state.js": reviewArtifactStateText,
  "review-copy-actions.js": reviewCopyActionsText,
  "review-submission-copy.js": reviewSubmissionCopyText,
  "review-recommendation-export.js": reviewRecommendationExportText,
  "pwa-runtime.js": pwaRuntimeText,
} = moduleTexts;

const maxAppLines = 12500;
const maxSectionLines = 5200;
const maxFunctionLines = 700;
const minActionHandlerMaps = 21;
const requiredActionHandlerMaps = [
  "MODAL_ACTION_HANDLERS",
  "APP_SHELL_ACTION_HANDLERS",
  "SETTINGS_STORAGE_ACTION_HANDLERS",
  "OPERATIONS_COPY_ACTION_HANDLERS",
  "OPERATIONS_PARSER_ACTION_HANDLERS",
  "PM_CRUD_ACTION_HANDLERS",
  "DB_CRUD_ACTION_HANDLERS",
  "RECORD_OPEN_ACTION_HANDLERS",
];

const requiredBoundaries = [
  { id: "shell_utilities", label: "Shell utilities and markdown safety", terms: ["function renderMarkdown", "DOMPurify.sanitize", "searchEmptyStateHelpers", "function searchEmptyState"] },
  { id: "state_refs", label: "State, seed data, and DOM references", terms: ["const dashboard = {", "const refs = {", "currentView: \"home\""] },
  { id: "home_view", label: "Home dashboard view", terms: ["* View: Home", "function renderHome", "home-quickadd"] },
  { id: "portfolio_review", label: "Portfolio and review handoff surface", terms: ["* View: Portfolio", "function renderPortfolio", "portfolioViewHelpers", "reviewPackageViewHelpers", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "REVIEW_HANDOFF_SCHEMA_VERSION"] },
  { id: "pm_views", label: "PM execution views", terms: ["* View: Kanban", "function renderKanban", "kanbanViewHelpers", "function renderGantt", "ganttViewHelpers", "function renderTeam", "teamViewHelpers"] },
  { id: "db_views", label: "DB catalog views and provenance", terms: ["* View: DB Instances", "function dbCatalogProvenanceHTML", "function renderDbQueries", "function renderDbBackups"] },
  { id: "settings_system", label: "Settings, storage health, and system status", terms: ["* View: Settings", "function renderSettings", "settingsViewHelpers", "function renderSystemStatus", "systemStatusViewHelpers", "storageStatusViewHelpers", "function publishReadinessItems"] },
  { id: "persistence_import", label: "Persistence and backup import guards", terms: ["function persist", "function loadPersisted", "workspaceStorageHelpers", "MAX_IMPORT_BYTES", "function handleImportFile"] },
  { id: "personal_views", label: "Calendar, todo, notes, habits, stats", terms: ["* View: 일정", "function renderCalendar", "calendarViewHelpers", "function renderTodos", "todoViewHelpers", "function renderNotes", "notesViewHelpers", "function renderHabits", "habitsViewHelpers", "function renderStats", "statsViewHelpers"] },
  { id: "routing_actions", label: "Routing and delegated action handling", terms: ["const VIEWS = [", "function renderCurrentView", "function handleActions", "document.body.addEventListener(\"click\""] },
  { id: "crud_surfaces", label: "PM and DB CRUD surfaces", terms: ["* PM CRUD", "function saveProjectFromForm", "* DB CRUD", "function saveInstanceFromForm"] },
  { id: "command_palette_bootstrap", label: "Command palette, shortcuts, and bootstrap", terms: ["function renderPaletteResults", "function openPalette", "window.addEventListener(\"hashchange\"", "document.addEventListener(\"visibilitychange\""] },
];

function candidateModule(path, text, terms) {
  return { path, text, terms };
}

const extractionCandidates = [
  {
    id: "search-empty-state",
    owner: "navigation",
    terms: ["searchEmptyStateHelpers", "function searchEmptyState", "searchEmptyStateCall(\"searchEmptyState\""],
    module: candidateModule("search-empty-state.js", searchEmptyStateText, ["JooParkSearchEmptyState", "joopark-search-empty-state/v1", "function createSearchEmptyState", "function searchEmptyState", "role=\"status\"", "data-action=\"clear-search\""]),
  },
  {
    id: "home-execution-view",
    owner: "home-cockpit",
    terms: ["homeExecutionViewHelpers", "function homeExecutionQueueHTML", "homeExecutionViewCall(\"homeExecutionQueueHTML\""],
    module: candidateModule("home-execution-view.js", homeExecutionViewText, ["JooParkHomeExecutionView", "joopark-home-execution-view/v1", "function createHomeExecutionView", "function homeExecutionQueueHTML", "function homeExecutionBucketSummaryHTML", "function homeExecutionReasonChipsHTML", "data-home-execution-queue", "aria-describedby=\"homeExecutionReceiptDetail\""]),
  },
  {
    id: "calendar-view",
    owner: "personal-productivity",
    terms: ["calendarViewHelpers", "function renderCalendar", "calendarViewCall(\"renderCalendarHTML\""],
    module: candidateModule("calendar-view.js", calendarViewText, ["JooParkCalendarView", "joopark-calendar-view/v1", "function createCalendarView", "function calLegend", "function eventRow", "function calendarViewModel", "function renderCalendarHTML", "role=\"grid\"", "data-search-result=\"calendar\"", "searchEmptyState(\"calendar\""]),
  },
  {
    id: "todo-view",
    owner: "personal-productivity",
    terms: ["todoViewHelpers", "function renderTodos", "todoViewCall(\"renderTodosHTML\""],
    module: candidateModule("todo-view.js", todoViewText, ["JooParkTodoView", "joopark-todo-view/v1", "function createTodoView", "function todoMatchesFilter", "function todoRow", "function todoViewModel", "function renderTodosHTML", "data-search-result=\"todo\"", "searchEmptyState(\"todo\"", "data-action=\"todo-filter\""]),
  },
  {
    id: "notes-view",
    owner: "personal-productivity",
    terms: ["notesViewHelpers", "function renderNotes", "notesViewCall(\"renderNotesHTML\""],
    module: candidateModule("notes-view.js", notesViewText, ["JooParkNotesView", "joopark-notes-view/v1", "function createNotesView", "function notesViewModel", "function noteCard", "function renderNotesHTML", "data-search-result=\"notes\"", "searchEmptyState(\"notes\"", "aria-pressed=\"${raw(note.pinned ? \"true\" : \"false\")}\""]),
  },
  {
    id: "habits-view",
    owner: "personal-productivity",
    terms: ["habitsViewHelpers", "function renderHabits", "habitsViewCall(\"renderHabitsHTML\""],
    module: candidateModule("habits-view.js", habitsViewText, ["JooParkHabitsView", "joopark-habits-view/v1", "function createHabitsView", "function habitsViewModel", "function habitCard", "function renderHabitsHTML", "data-search-result=\"habits\"", "searchEmptyState(\"habits\"", "aria-pressed=\"${raw(checked ? \"true\" : \"false\")}\""]),
  },
  {
    id: "stats-view",
    owner: "personal-productivity",
    terms: ["statsViewHelpers", "function renderStats", "statsViewCall(\"renderStatsHTML\""],
    module: candidateModule("stats-view.js", statsViewText, ["JooParkStatsView", "joopark-stats-view/v1", "function createStatsView", "function statsViewModel", "function accessibleSpark", "function barChart", "function renderStatsHTML", "data-stats-chart=\"todo-trend\"", "role=\"img\""]),
  },
  {
    id: "portfolio-view",
    owner: "pm-portfolio",
    terms: ["portfolioViewHelpers", "function renderPortfolio", "portfolioViewCall(\"renderPortfolioHTML\""],
    module: candidateModule("portfolio-view.js", portfolioViewText, ["JooParkPortfolioView", "joopark-portfolio-view/v1", "function createPortfolioView", "function portfolioViewModel", "function projectCard", "function renderPortfolioHTML", "data-search-result=\"pm-portfolio\"", "searchEmptyState(\"pm-portfolio\"", "role=\"listitem\"", "projectListItemLabel"]),
  },
  {
    id: "kanban-view",
    owner: "pm-execution",
    terms: ["kanbanViewHelpers", "function renderKanban", "kanbanViewCall(\"renderKanbanHTML\""],
    module: candidateModule("kanban-view.js", kanbanViewText, ["JooParkKanbanView", "joopark-kanban-view/v1", "function createKanbanView", "function kanbanViewModel", "function issueCard", "function renderKanbanHTML", "data-search-result=\"pm-kanban\"", "searchEmptyState(\"pm-kanban\"", "role=\"listitem\""]),
  },
  {
    id: "gantt-view",
    owner: "pm-execution",
    terms: ["ganttViewHelpers", "function renderGantt", "ganttViewCall(\"renderGanttHTML\""],
    module: candidateModule("gantt-view.js", ganttViewText, ["JooParkGanttView", "joopark-gantt-view/v1", "function createGanttView", "function ganttViewModel", "function taskShapeHTML", "function renderGanttHTML", "data-search-result=\"pm-gantt\"", "searchEmptyState(\"pm-gantt\"", "role=\"button\""]),
  },
  {
    id: "team-view",
    owner: "pm-execution",
    terms: ["teamViewHelpers", "function renderTeam", "teamViewCall(\"renderTeamHTML\""],
    module: candidateModule("team-view.js", teamViewText, ["JooParkTeamView", "joopark-team-view/v1", "function createTeamView", "function teamViewModel", "function memberRow", "function renderTeamHTML", "data-search-result=\"pm-team\"", "searchEmptyState(\"pm-team\"", "role=\"table\""]),
  },
  {
    id: "review-handoff",
    owner: "product-review",
    terms: ["REVIEW_HANDOFF_SCHEMA_VERSION", "reviewHandoffHelpers", "function validateReviewResult"],
    module: candidateModule("review-handoff.js", reviewHandoffText, ["JooParkReviewHandoff", "joopark-review-handoff-runtime/v1", "function createReviewHandoff", "function reviewPackageBundleMarkdown", "function reviewPromptHandoffMarkdown", "function validateReviewResultShape"]),
  },
  {
    id: "review-result-view",
    owner: "product-review",
    terms: ["reviewResultViewHelpers", "function reviewResultViewCall", "function reviewResultSavedCard", "function compactReviewResult", "function setReviewResultValidation", "reviewResultViewCall(\"reviewSavedResultBody\"", "reviewResultViewCall(\"reviewSavedResultNoteBody\"", "reviewResultViewCall(\"reviewAssigneeFollowUpPanel\"", "reviewResultViewCall(\"issueExecutionChecklistControls\"", "reviewResultViewCall(\"reviewIssueDraftPanel\"", "reviewResultViewCall(\"reviewGithubCommentMarkdown\"", "reviewResultViewCall(\"reviewGithubCommentDraftPanel\"", "reviewResultViewCall(\"reviewResultValidationOutput\""],
    module: candidateModule("review-result-view.js", reviewResultViewText, ["JooParkReviewResultView", "joopark-review-result-view/v1", "function createReviewResultView", "function reviewResultSavedCard", "function compactReviewResult", "function reviewSavedResultBody", "function reviewSavedResultNoteBody", "function reviewAssigneeFollowUpPanel", "function issueExecutionChecklistControls", "function reviewIssueDraftPanel", "function reviewGithubCommentMarkdown", "function reviewGithubCommentDraftPanel", "function reviewResultRepairReceiptMarkdown", "function reviewResultPostRepairReceiptPanel", "function reviewResultValidationOutput", "data-review-result-saved-card", "data-review-result-failures", "data-review-result-repair-receipt", "Assignee Follow-up", "data-issue-draft-owner-follow-up", "data-review-issue-draft", "data-review-github-comment-text", "data-issue-execution-checklist-view"]),
  },
  {
    id: "review-execution-checklist",
    owner: "product-review",
    terms: ["reviewExecutionChecklistHelpers", "function reviewExecutionChecklistCall", "reviewExecutionChecklistCall(\"reviewExecutionChecklistItemsFromSavedResult\"", "reviewExecutionChecklistCall(\"issueExecutionChecklistItems\"", "reviewExecutionChecklistCall(\"issueExecutionChecklistProgress\"", "reviewExecutionChecklistCall(\"syncIssueBodyExecutionChecklist\"", "function reviewExecutionChecklistItemsFromSavedResult", "function issueExecutionChecklistItems", "function issueExecutionChecklistProgress", "function syncIssueBodyExecutionChecklist"],
    module: candidateModule("review-execution-checklist.js", reviewExecutionChecklistText, ["JooParkReviewExecutionChecklist", "joopark-review-execution-checklist/v1", "function createReviewExecutionChecklist", "function reviewExecutionChecklistItemsFromSavedResult", "function issueExecutionChecklistItems", "function issueExecutionChecklistProgress", "function reviewExecutionChecklistLines", "function syncIssueBodyExecutionChecklist", "function reviewExecutionChecklistCountLabel", "function firstPositiveTimeboxHours"]),
  },
  {
    id: "review-issue-payload",
    owner: "product-review",
    terms: ["reviewIssuePayloadHelpers", "function reviewIssuePayloadCall", "reviewIssuePayloadCall(\"reviewIssueBodyLines\"", "reviewIssuePayloadCall(\"reviewSavedResultTrackerFields\"", "function reviewIssueBodyLines", "function reviewIssueDecisionSummaryLines", "function reviewSavedResultTrackerFields"],
    module: candidateModule("review-issue-payload.js", reviewIssuePayloadText, ["JooParkReviewIssuePayload", "joopark-review-issue-payload/v1", "function createReviewIssuePayload", "function reviewOperationalReadinessLines", "function reviewIssueDecisionSummaryLines", "function reviewIssueBodyLines", "function reviewPackageNoteBody", "function reviewExecutionDueDate", "function reviewSavedResultTrackerFields"]),
  },
  {
    id: "review-result-state",
    owner: "product-review",
    terms: ["reviewResultStateHelpers", "function reviewResultStateCall", "reviewResultStateCall(\"setValidation\"", "reviewResultStateCall(\"attachRepairReceipt\"", "reviewResultStateCall(\"copyRepair\"", "function setReviewResultValidation", "function attachReviewResultRepairReceipt", "function copyReviewResultRepairReceipt"],
    module: candidateModule("review-result-state.js", reviewResultStateText, ["JooParkReviewResultState", "joopark-review-result-state/v1", "function createReviewResultState", "function recordRepairSnapshot", "function postRepairReceiptModel", "function attachRepairReceipt", "function setValidation", "function copyRepair", "function copyRepairReceipt", "data-review-result-repair", "data-review-result-repair-receipt", "reviewResultRepairReceiptCopied"]),
  },
  {
    id: "review-result-draft-state",
    owner: "product-review",
    terms: ["reviewResultDraftStateHelpers", "function reviewResultDraftStateCall", "reviewResultDraftStateCall(\"copyGithubComment\"", "reviewResultDraftStateCall(\"updateIssueDraftAssignee\"", "reviewResultDraftStateCall(\"issueDraftNode\"", "function copyReviewGithubComment", "function updateReviewIssueDraftAssignee", "function reviewIssueDraftAssigneeCopy"],
    module: candidateModule("review-result-draft-state.js", reviewResultDraftStateText, ["JooParkReviewResultDraftState", "joopark-review-result-draft-state/v1", "function createReviewResultDraftState", "function copyGithubComment", "function updateIssueDraftAssignee", "function issueDraftNode", "function issueDraftAssigneePanel", "function issueDraftAssigneeCopy", "data-review-github-comment-text", "data-review-issue-draft", "reviewGithubCommentCopied", "assignee-confirmed"]),
  },
  {
    id: "review-creation-actions",
    owner: "product-review",
    terms: ["reviewCreationActionsHelpers", "function reviewCreationActionsCall", "reviewCreationActionsCall(\"createBenchmarkReviewIssue\"", "reviewCreationActionsCall(\"publishReviewHandoffNote\"", "function createBenchmarkReviewIssue", "function publishReviewHandoffNote"],
    module: candidateModule("review-creation-actions.js", reviewCreationActionsText, ["JooParkReviewCreationActions", "joopark-review-creation-actions/v1", "function createReviewCreationActions", "function createBenchmarkReviewIssue", "function publishReviewHandoffNote", "function ensureDashboardArray", "ensureDashboardArray(\"issues\").push", "ensureDashboardArray(\"notes\").push", "validated-review-result", "review note를 발행했습니다"]),
  },
  {
    id: "review-package-view",
    owner: "product-review",
    terms: ["reviewPackageViewHelpers", "reviewPackageViewCall(\"reviewPackageHandoffHTML\"", "function candidateWorkspaceReviewHandoff", "function candidateKnowledgeBaseReviewHandoff", "function candidateBenchmarkReviewQueueHandoff"],
    module: candidateModule("review-package-view.js", reviewPackageViewText, ["JooParkReviewPackageView", "joopark-review-package-view/v1", "function createReviewPackageView", "function reviewPackageHandoffModel", "function reviewPackageHandoffHTML", "data-workspace-review-handoff", "data-review-package-bundle-text"]),
  },
  {
    id: "review-artifact-view",
    owner: "product-review",
    terms: ["reviewArtifactViewHelpers", "reviewArtifactViewCall(\"issueFreshReceiptControls\"", "reviewArtifactViewCall(\"reviewArtifactDiffPanel\"", "function reviewArtifactDiffPanel", "function reviewArtifactReceiptComparison", "function reviewArtifactReceiptCompareOutput"],
    module: candidateModule("review-artifact-view.js", reviewArtifactViewText, ["JooParkReviewArtifactView", "joopark-review-artifact-view/v1", "function createReviewArtifactView", "function issueFreshReceiptControls", "function reviewArtifactDiffPanel", "function reviewArtifactReceiptMarkdown", "function reviewArtifactReceiptCompareOutput", "data-review-artifact-diff", "data-review-artifact-receipt-compare", "data-issue-fresh-receipt-view"]),
  },
  {
    id: "review-artifact-state",
    owner: "product-review",
    terms: ["reviewArtifactStateHelpers", "function reviewArtifactStateCall", "reviewArtifactStateCall(\"repairPreview\"", "reviewArtifactStateCall(\"compareReceipt\"", "function reviewArtifactRepairPreview", "function applyReviewArtifactRepairBody", "function undoReviewArtifactRepair", "function compareReviewArtifactReceipt"],
    module: candidateModule("review-artifact-state.js", reviewArtifactStateText, ["JooParkReviewArtifactState", "joopark-review-artifact-state/v1", "function createReviewArtifactState", "function repairPreview", "function applyRepairBody", "function undoRepair", "function setReceiptCompareState", "function compareReceipt", "function insertReceipt", "function clearReceipt", "data-review-artifact-repair-preview", "data-review-artifact-receipt-compare"]),
  },
  {
    id: "review-copy-actions",
    owner: "product-review",
    terms: ["reviewCopyActionsHelpers", "function reviewCopyActionsCall", "reviewCopyActionsCall(\"copyReviewPackagePasteBody\"", "reviewCopyActionsCall(\"copyReviewPackagePanelText\"", "reviewCopyActionsCall(\"copyReviewArtifactReceipt\"", "reviewCopyActionsCall(\"copyReviewArtifactRepairPayload\"", "reviewCopyActionsCall(\"copyIssueFreshReceipt\"", "reviewCopyActionsCall(\"copyReviewArtifactPostApplyReceipt\"", "reviewCopyActionsCall(\"copyReviewPostRepairArtifactLink\""],
    module: candidateModule("review-copy-actions.js", reviewCopyActionsText, ["JooParkReviewCopyActions", "joopark-review-copy-actions/v1", "function createReviewCopyActions", "function copyReviewPackagePasteBody", "function copyReviewPackagePanelText", "function copyReviewArtifactReceipt", "function copyReviewArtifactRepairPayload", "function copyIssueFreshReceipt", "function copyReviewArtifactPostApplyReceipt", "function copyReviewPostRepairArtifactLink", "reviewPackagePastePreviewCopied", "reviewArtifactReceiptCopied", "reviewArtifactPostApplyReceiptCopied", "paste body를 복사했습니다", "post-apply fresh receipt를 복사했습니다"]),
  },
  {
    id: "review-submission-copy",
    owner: "product-review",
    terms: ["reviewSubmissionCopyHelpers", "function reviewSubmissionCopyCall", "reviewSubmissionCopyCall(\"copyReviewPackageFilledText\"", "reviewSubmissionCopyCall(\"copyReviewPackageExternalReceiptFilled\"", "reviewSubmissionCopyCall(\"copyReviewPackageSubmissionUpdateFilled\""],
    module: candidateModule("review-submission-copy.js", reviewSubmissionCopyText, ["JooParkReviewSubmissionCopy", "joopark-review-submission-copy/v1", "function createReviewSubmissionCopy", "function fillExternalIssueText", "function copyReviewPackageFilledText", "function copyReviewPackageExternalReceiptFilled", "function copyReviewPackageSubmissionUpdateFilled"]),
  },
  {
    id: "review-recommendation-export",
    owner: "product-review",
    terms: ["reviewRecommendationExportHelpers", "function reviewRecommendationExportCall", "reviewRecommendationExportCall(\"candidateWorkspaceRecommendationExport\"", "reviewRecommendationExportCall(\"candidateKnowledgeBaseRecommendationExport\"", "reviewRecommendationExportCall(\"candidateBenchmarkRecommendationExport\""],
    module: candidateModule("review-recommendation-export.js", reviewRecommendationExportText, ["JooParkReviewRecommendationExport", "joopark-review-recommendation-export/v1", "function createReviewRecommendationExport", "function recommendationMarkdown", "function recommendationExport", "function candidateWorkspaceRecommendationExport", "function candidateKnowledgeBaseRecommendationExport", "function candidateBenchmarkRecommendationExport"]),
  },
  {
    id: "pwa-runtime",
    owner: "runtime-delivery",
    terms: ["pwaRuntimeHelpers", "function pwaRuntimeCall", "pwaRuntimeCall(\"inspect\"", "pwaRuntimeCall(\"setupObservers\"", "pwaRuntimeCall(\"register\""],
    module: candidateModule("pwa-runtime.js", pwaRuntimeText, ["JooParkPwaRuntime", "joopark-pwa-runtime/v1", "function createPwaRuntime", "function statusLabel", "async function inspect", "function setupObservers", "function register"]),
  },
  {
    id: "db-catalog",
    owner: "data-catalog",
    terms: ["function dbCatalogProvenanceHTML", "function renderDbInstances", "function openInstanceModal"],
    module: candidateModule("db-catalog.js", dbCatalogText, ["JooParkDbCatalog", "joopark-db-catalog/v1", "function createDbCatalog", "function renderDbBackups", "function saveMigrationFromForm"]),
  },
  {
    id: "workspace-storage",
    owner: "storage",
    terms: ["workspaceStorageHelpers", "function persist", "function loadPersisted", "function refreshStorageHealth"],
    module: candidateModule("workspace-storage.js", workspaceStorageText, ["JooParkWorkspaceStorage", "joopark-workspace-storage/v1", "function createWorkspaceStorage", "function persistPayload", "function refreshStorageHealth", "function loadPersisted"]),
  },
  {
    id: "storage-status-view",
    owner: "operations",
    terms: ["storageStatusViewHelpers", "function settingsStorageHealthHTML", "function systemStorageHealthHTML"],
    module: candidateModule("storage-status-view.js", storageStatusViewText, ["JooParkStorageStatusView", "joopark-storage-status-view/v1", "function createStorageStatusView", "function storageStatusModel", "function settingsStorageHealthHTML", "function systemStorageHealthHTML"]),
  },
  {
    id: "settings-view",
    owner: "operations",
    terms: ["settingsViewHelpers", "function renderSettings", "settingsViewCall(\"renderSettingsHTML\""],
    module: candidateModule("settings-view.js", settingsViewText, ["JooParkSettingsView", "joopark-settings-view/v1", "function createSettingsView", "function settingsViewModel", "function renderSettingsHTML", "data-settings-handoff", "data-settings-handoff-copy=\"${kind}\"", "배포 handoff 복사", "role=\"listitem\""]),
  },
  {
    id: "system-status-view",
    owner: "operations",
    terms: ["systemStatusViewHelpers", "function renderSystemStatus", "systemStatusViewCall(\"renderSystemStatusHTML\""],
    module: candidateModule("system-status-view.js", systemStatusViewText, ["JooParkSystemStatusView", "joopark-system-status-view/v1", "function createSystemStatusView", "function systemStatusModel", "function projectSnapshotHealthHTML", "function renderSystemStatusHTML", "data-system-status-module", "data-system-source-snapshots"]),
  },
  {
    id: "backup-import",
    owner: "storage",
    terms: ["MAX_IMPORT_BYTES", "backupImportUiHelpers", "function handleImportFile"],
    module: candidateModule("backup-import-guards.js + backup-import-ui.js", `${backupImportGuardsText}\n${backupImportUiText}`, ["JooParkImportGuards", "joopark-import-guards/v1", "recordLimitViolations", "backupSummaryItems", "JooParkBackupImportUi", "joopark-backup-import-ui/v1", "function createBackupImportUi", "function handleImportFile", "function applyImported"]),
  },
  {
    id: "release-status",
    owner: "operations",
    terms: ["function publishReadinessItems", "function publishEvidenceHTML", "function publishUnblockHandoffText"],
    module: candidateModule("release-status.js", releaseStatusText, ["JooParkReleaseStatus", "joopark-release-status/v1", "publishReadinessItems", "publishEvidenceHTML", "publishUnblockHandoffText"]),
  },
  {
    id: "operations-copy-actions",
    owner: "operations",
    terms: ["operationsCopyActionsHelpers", "function operationsCopyActionsCall", "operationsCopyActionsCall(\"copySettingsHandoff\"", "operationsCopyActionsCall(\"copyPublishEvidenceShareUpdate\"", "operationsCopyActionsCall(\"copyWorkflowUiInstallReceipt\"", "operationsCopyActionsCall(\"copyOutputQualityAuditReceipt\""],
    module: candidateModule("operations-copy-actions.js", operationsCopyActionsText, ["JooParkOperationsCopyActions", "joopark-operations-copy-actions/v1", "function createOperationsCopyActions", "function copyConfiguredText", "function copySettingsHandoff", "function copyWorkflowUiInstallReceipt", "function copyOutputQualityAuditReceipt", "workflowUiInstallPastePacketCopied", "outputQualityAuditReceiptCopied"]),
  },
  {
    id: "verify-workspace-summary",
    owner: "operations",
    terms: ["verifyWorkspaceSummaryHelpers", "function verifyWorkspaceSummaryCall", "function loadVerifyWorkspaceSummary"],
    module: candidateModule("verify-workspace-summary.js", verifyWorkspaceSummaryText, ["JooParkVerifyWorkspaceSummary", "joopark-verify-workspace-summary/v1", "function createVerifyWorkspaceSummary", "function validateSummary", "release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync"]),
  },
  {
    id: "dialog-shell",
    owner: "navigation",
    terms: ["dialogShellHelpers", "function dialogShellCall", "dialogShellCall(\"openSheet\"", "dialogShellCall(\"closeSheet\"", "dialogShellCall(\"openModal\"", "dialogShellCall(\"trapTab\""],
    module: candidateModule("dialog-shell.js", dialogShellText, ["JooParkDialogShell", "joopark-dialog-shell/v1", "function createDialogShell", "function renderSheetMeta", "function setNotificationTriggerExpanded", "function restoreFocusAfterClose", "function openSheet", "function closeSheet", "function openModal", "function closeModal", "function getOpenDialogRoot", "function trapTab"]),
  },
  {
    id: "project-picker",
    owner: "navigation",
    terms: ["projectPickerHelpers", "function projectPickerCall", "projectPickerCall(\"renderOptions\"", "projectPickerCall(\"setOpen\"", "projectPickerCall(\"closeIfOutside\""],
    module: candidateModule("project-picker.js", projectPickerText, ["JooParkProjectPicker", "joopark-project-picker/v1", "function createProjectPicker", "function normalizeAccessibility", "function renderOptions", "function restoreFocus", "function ensureScaffold", "function setOpen", "function closeIfOutside"]),
  },
  {
    id: "global-search",
    owner: "navigation",
    terms: ["globalSearchHelpers", "function globalSearchCall", "globalSearchCall(\"syncAffordance\"", "globalSearchCall(\"revealEmptyIfNeeded\"", "globalSearchCall(\"clear\""],
    module: candidateModule("global-search.js", globalSearchText, ["JooParkGlobalSearch", "joopark-global-search/v1", "function createGlobalSearch", "const SEARCH_INERT_VIEWS", "function syncAffordance", "function revealEmptyIfNeeded", "event.key !== \"Escape\"", "openPalette();"]),
  },
  {
    id: "command-palette",
    owner: "navigation",
    terms: ["function _buildPaletteItems", "function renderPaletteResults", "function _palRunIndex"],
    module: candidateModule("command-palette.js", commandPaletteText, ["JooParkCommandPalette", "joopark-command-palette/v1", "buildItems", "aria-activedescendant", "runIndex"]),
  },
];

function lineNumberOf(term) {
  const index = lines.findIndex((line) => line.includes(term));
  return index >= 0 ? index + 1 : null;
}

function hasLineNumber(line) {
  return line !== null;
}

function presentLineNumbers(terms) {
  return terms.map(lineNumberOf).filter(hasLineNumber);
}

function firstLineOf(terms) {
  const firstLine = Math.min(...presentLineNumbers(terms));
  return Number.isFinite(firstLine) ? firstLine : null;
}

function appLineCount() {
  return lines.length;
}

function termBucket(term, text) {
  return text.includes(term) ? "present" : "missing";
}

function emptyTermPresence() {
  return { present: [], missing: [] };
}

function termPresence(terms, text) {
  const presence = emptyTermPresence();
  for (const term of terms) {
    presence[termBucket(term, text)].push(term);
  }
  return presence;
}

function hasMissingTerms(missing) {
  return missing.length > 0;
}

function missingTermsText(missing) {
  return missing.join(", ");
}

function lineListText(lineNumbers) {
  return lineNumbers.join(", ");
}

function passFail(passes) {
  return passes ? "pass" : "fail";
}

function missingTermStatus(missing) {
  return passFail(!hasMissingTerms(missing));
}

function boundaryEvidence(boundary) {
  const { missing } = termPresence(boundary.terms, appText);
  return {
    ...boundary,
    status: missingTermStatus(missing),
    firstLine: firstLineOf(boundary.terms),
    missing,
  };
}

function collectLineRanges(createMarker) {
  const markers = [];
  lines.forEach((line, index) => {
    const marker = createMarker(line, index);
    if (marker) markers.push(marker);
  });
  return withLineRanges(markers);
}

function sectionMarkers() {
  const viewPattern = /^\s*\*\s+(View|PM CRUD|DB CRUD|Projects CRUD|Issues \(Kanban\) CRUD|Gantt Tasks CRUD|Team Members CRUD|Real CRUD persisted|Event delegation|Calendar)\b/;
  return collectLineRanges((line, index) => {
    const trimmed = line.trim();
    if (!viewPattern.test(trimmed)) return null;
    return {
      line: index + 1,
      title: trimmed.replace(/^\*\s*/, "").trim(),
    };
  });
}

function declaredFunctions() {
  const functionPattern = /^function\s+([A-Za-z0-9_$]+)\s*\(/;
  return collectLineRanges((line, index) => {
    const match = line.match(functionPattern);
    return match ? { name: match[1], line: index + 1 } : null;
  });
}

function oversizedItems(items, maxLines) {
  return items.filter((item) => item.lines > maxLines);
}

function lineRange(item, next) {
  const endLine = next ? next.line - 1 : appLineCount();
  return {
    endLine,
    lines: endLine - item.line + 1,
  };
}

function withLineRanges(items) {
  return items.map((item, index) => {
    const next = items[index + 1];
    return {
      ...item,
      ...lineRange(item, next),
    };
  });
}

function sourceBlockForFunction(functionName) {
  const marker = `function ${functionName}(`;
  const start = appText.indexOf(marker);
  if (start < 0) return "";
  let depth = 0;
  let opened = false;
  for (let index = start; index < appText.length; index += 1) {
    const char = appText[index];
    if (char === "{") {
      depth += 1;
      opened = true;
    } else if (char === "}") {
      depth -= 1;
      if (opened && depth === 0) return appText.slice(start, index + 1);
    }
  }
  return appText.slice(start);
}

function actionHandlerMapNames() {
  return [...appText.matchAll(/const\s+([A-Z_]+ACTION_HANDLERS)\s*=\s*new Map/g)].map((match) => match[1]);
}

function actionHandlerDispatchSequence(source) {
  return [...source.matchAll(/runActionHandler\(action, target, ([A-Z_]+ACTION_HANDLERS)\)/g)].map((match) => match[1]);
}

function directActionBranches(source) {
  return [...source.matchAll(/if\s*\(\s*action\s*===\s*"([^"]+)"\s*\)/g)].map((match) => match[1]);
}

function actionDispatchGuardEvidence() {
  const handleActionsSource = sourceBlockForFunction("handleActions");
  const handlerMaps = actionHandlerMapNames();
  const dispatchSequence = actionHandlerDispatchSequence(handleActionsSource);
  const directBranches = directActionBranches(handleActionsSource);
  const missingRequiredMaps = requiredActionHandlerMaps.filter((mapName) => !handlerMaps.includes(mapName));
  const firstHandler = dispatchSequence[0] || null;
  const status = passFail(
    handleActionsSource.length > 0
      && directBranches.length === 0
      && handlerMaps.length >= minActionHandlerMaps
      && missingRequiredMaps.length === 0
      && firstHandler === "MODAL_ACTION_HANDLERS",
  );
  return {
    status,
    handleActionsFound: handleActionsSource.length > 0,
    directActionBranchCount: directBranches.length,
    directActionBranches: directBranches,
    actionHandlerMapCount: handlerMaps.length,
    minActionHandlerMaps,
    missingRequiredMaps,
    firstHandler,
  };
}

function duplicateFunctionRecord(previous, current) {
  return { name: current.name, lines: [previous.line, current.line] };
}

function duplicateFunctionNames(functions) {
  const seen = new Map();
  const duplicates = [];
  for (const fn of functions) {
    const previous = seen.get(fn.name);
    if (previous) duplicates.push(duplicateFunctionRecord(previous, fn));
    else seen.set(fn.name, fn);
  }
  return duplicates;
}

function moduleCoverageReport(candidate, moduleTerms, moduleTermCoverage) {
  const module = candidateExtractionModule(candidate);
  if (!module) return null;
  return {
    path: candidateModulePath(candidate),
    status: missingTermStatus(moduleTermCoverage.missing),
    present: moduleTermCoverage.present.length,
    total: moduleTerms.length,
    missing: moduleTermCoverage.missing,
  };
}

function coverageComplete(totalPresent, totalTerms) {
  return totalPresent === totalTerms;
}

function candidateExtractionModule(candidate) {
  return candidate.module;
}

function candidateHasModule(candidate) {
  return Boolean(candidateExtractionModule(candidate));
}

function candidateModulePath(candidate) {
  return candidateExtractionModule(candidate).path;
}

function candidateModuleMissing(candidate) {
  return candidateExtractionModule(candidate).missing;
}

function coverageStatus(candidate, totalPresent, totalTerms) {
  if (!coverageComplete(totalPresent, totalTerms)) return "partial";
  return candidateHasModule(candidate) ? "extracted" : "ready";
}

function combinedCoverageCounts(candidate, appTerms, moduleTerms, moduleTermCoverage) {
  return {
    present: appTerms.present.length + moduleTermCoverage.present.length,
    total: candidate.terms.length + moduleTerms.length,
  };
}

function candidateModuleTerms(candidate) {
  return candidateHasModule(candidate) ? candidateExtractionModule(candidate).terms : [];
}

function moduleTermPresence(candidate, moduleTerms) {
  return candidateHasModule(candidate) ? termPresence(moduleTerms, candidateExtractionModule(candidate).text) : emptyTermPresence();
}

function termCoverage(candidate) {
  const appTerms = termPresence(candidate.terms, appText);
  const moduleTerms = candidateModuleTerms(candidate);
  const moduleTermCoverage = moduleTermPresence(candidate, moduleTerms);
  const counts = combinedCoverageCounts(candidate, appTerms, moduleTerms, moduleTermCoverage);
  return {
    ...candidate,
    module: moduleCoverageReport(candidate, moduleTerms, moduleTermCoverage),
    status: coverageStatus(candidate, counts.present, counts.total),
    present: counts.present,
    total: counts.total,
    firstLine: firstLineOf(candidate.terms),
  };
}

function moduleMissingSummary(candidate) {
  const missing = candidateModuleMissing(candidate);
  return hasMissingTerms(missing) ? missingTermsText(missing) : "app boundary terms";
}

function boundaryFailure(boundary) {
  if (boundary.status === "pass") return null;
  return `${boundary.id} missing terms: ${missingTermsText(boundary.missing)}`;
}

function duplicateFunctionFailure(duplicate) {
  return `duplicate function ${duplicate.name} at lines ${lineListText(duplicate.lines)}`;
}

function extractionFailure(candidate) {
  if (!candidateHasModule(candidate) || candidate.status === "extracted") return null;
  return `${candidate.id} extracted module incomplete: ${candidateModulePath(candidate)} missing ${moduleMissingSummary(candidate)}`;
}

function actionDispatchGuardFailure(actionDispatchGuard) {
  if (actionDispatchGuard.status === "pass") return null;
  const issues = [];
  if (!actionDispatchGuard.handleActionsFound) issues.push("handleActions missing");
  if (actionDispatchGuard.directActionBranchCount > 0) issues.push(`direct action branches: ${actionDispatchGuard.directActionBranches.join(", ")}`);
  if (actionDispatchGuard.actionHandlerMapCount < actionDispatchGuard.minActionHandlerMaps) issues.push(`action handler maps ${actionDispatchGuard.actionHandlerMapCount}/${actionDispatchGuard.minActionHandlerMaps}`);
  if (actionDispatchGuard.missingRequiredMaps.length > 0) issues.push(`missing maps: ${actionDispatchGuard.missingRequiredMaps.join(", ")}`);
  if (actionDispatchGuard.firstHandler !== "MODAL_ACTION_HANDLERS") issues.push(`first handler: ${actionDispatchGuard.firstHandler || "missing"}`);
  return `action dispatcher map-only guard failed: ${issues.join("; ")}`;
}

function appLineCountFailure() {
  const lineCount = appLineCount();
  if (lineCount <= maxAppLines) return null;
  return `app.js has ${lineCount} lines; max allowed ${maxAppLines}`;
}

function collectMappedFailures(items, createFailure) {
  return items.map(createFailure).filter(Boolean);
}

function collectMappedMessages(items, createMessage) {
  return items.map(createMessage);
}

function collectFailures({ boundaries, duplicateFunctions, extractionPlan, actionDispatchGuard }) {
  return [
    appLineCountFailure(),
    ...collectMappedFailures(boundaries, boundaryFailure),
    ...collectMappedFailures(duplicateFunctions, duplicateFunctionFailure),
    ...collectMappedFailures(extractionPlan, extractionFailure),
    actionDispatchGuardFailure(actionDispatchGuard),
  ].filter(Boolean);
}

function sectionWarning(section) {
  return `${section.title} section is ${section.lines} lines; split this before adding large features`;
}

function functionWarning(fn) {
  return `${fn.name} is ${fn.lines} lines; extract helpers before expanding it`;
}

function collectWarnings({ oversizedSections, oversizedFunctions }) {
  return [
    ...collectMappedMessages(oversizedSections, sectionWarning),
    ...collectMappedMessages(oversizedFunctions, functionWarning),
  ];
}

function resultStatus(failures) {
  return passFail(failures.length === 0);
}

function thresholdSummary() {
  return {
    maxAppLines,
    maxSectionLines,
    maxFunctionLines,
  };
}

function structureResult({
  boundaries,
  actionDispatchGuard,
  sections,
  oversizedSections,
  oversizedFunctions,
  duplicateFunctions,
  extractionPlan,
  warnings,
  failures,
}) {
  return {
    status: resultStatus(failures),
    appFile: relative(root, appPath),
    totalLines: appLineCount(),
    thresholds: thresholdSummary(),
    boundaries,
    actionDispatchGuard,
    sectionCount: sections.length,
    oversizedSections,
    oversizedFunctions,
    duplicateFunctions,
    extractionPlan,
    warnings,
    failures,
  };
}

const boundaries = requiredBoundaries.map(boundaryEvidence);
const sections = sectionMarkers();
const functions = declaredFunctions();
const duplicateFunctions = duplicateFunctionNames(functions);
const oversizedSections = oversizedItems(sections, maxSectionLines);
const oversizedFunctions = oversizedItems(functions, maxFunctionLines);
const extractionPlan = extractionCandidates.map(termCoverage);
const actionDispatchGuard = actionDispatchGuardEvidence();
const warnings = collectWarnings({ oversizedSections, oversizedFunctions });
const failures = collectFailures({ boundaries, duplicateFunctions, extractionPlan, actionDispatchGuard });

const result = structureResult({
  boundaries,
  actionDispatchGuard,
  sections,
  oversizedSections,
  oversizedFunctions,
  duplicateFunctions,
  extractionPlan,
  warnings,
  failures,
});

console.log(JSON.stringify(result, null, 2));
if (result.status !== "pass") process.exit(1);

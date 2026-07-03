#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-delete-undo-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async open() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.addEventListener("message", (event) => this.handleMessage(event.data));
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timed out opening CDP websocket")), 8000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error(`Failed to open CDP websocket: ${this.wsUrl}`));
      }, { once: true });
    });
  }

  handleMessage(data) {
    const message = JSON.parse(String(data));
    if (!message.id || !this.pending.has(message.id)) return;
    const { resolve, reject, timer } = this.pending.get(message.id);
    this.pending.delete(message.id);
    clearTimeout(timer);
    if (message.error) reject(new Error(message.error.message || "CDP error"));
    else resolve(message.result || {});
  }

  send(method, params = {}, timeoutMs = 10000) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
    });
  }

  close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close();
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function progress(event, extra = {}) {
  if (!progressEnabled) return;
  console.error(JSON.stringify({ event, ...extra }));
}

async function waitForProcessExit(child, timeoutMs) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return true;
  return await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve(true);
    });
  });
}

async function terminateProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  const exited = await waitForProcessExit(child, 1500);
  if (exited) return;
  child.kill("SIGKILL");
  await waitForProcessExit(child, 1500);
}

async function waitForDevTools(chrome) {
  let stderr = "";
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for DevTools endpoint.\n${stderr}`)), 12000);
    chrome.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    chrome.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited before DevTools endpoint was ready: ${code}\n${stderr}`));
    });
  });
}

async function pageWebSocketUrl(browserWsUrl) {
  const { port } = new URL(browserWsUrl);
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Retry until Chrome exposes the page target.
    }
    await delay(250);
  }
  throw new Error("No page target exposed by Chrome");
}

async function evaluate(client, expression, timeoutMs = 30000) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, timeoutMs);
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Runtime evaluation failed";
    throw new Error(detail);
  }
  return result.result ? result.result.value : undefined;
}

const deleteUndoExpression = `
(async () => {
  const marker = "UNDO-SMOKE-" + Date.now();
  const failures = [];
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const waitFor = async (predicate, message, timeout = 4000) => {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (predicate()) return true;
      await sleep(50);
    }
    throw new Error(message);
  };
  const payload = () => JSON.parse(localStorage.getItem("joopark.workspace.v3") || "{}");
  const clickUndo = async (expectedText) => {
    await waitFor(() => Array.from(document.querySelectorAll("#toastRegion .toast")).some((toast) => toast.textContent.includes(expectedText) && toast.textContent.includes("되돌리기")), "undo toast missing for " + expectedText);
    const actions = Array.from(document.querySelectorAll("#toastRegion [data-toast-action]"));
    assert(actions.length > 0, "undo action button missing for " + expectedText);
    actions[actions.length - 1].click();
    await sleep(160);
  };

  try {
    const projectId = (dashboard.projects[0] && dashboard.projects[0].id) || "proj-undo-smoke";
    const instanceId = (dashboard.dbInstances[0] && dashboard.dbInstances[0].id) || "db-undo-smoke";
    const baselineDeletedCount = Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems.length : 0;

    const expiredDeletedId = marker + "-expired-deleted";
    dashboard.deletedItems.push({
      id: expiredDeletedId,
      kind: "todo",
      recordId: marker + "-expired-todo",
      label: marker + " expired todo",
      deletedAt: new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString(),
      index: 0,
      record: { id: marker + "-expired-todo", title: marker + " expired todo", due: null, priority: "low", done: false, category: "", memo: "expired", createdAt: nowISO() },
      meta: {},
    });
    normalizeAllData();
    assert(!dashboard.deletedItems.some((item) => item.id === expiredDeletedId), "expired deleted item was not pruned");
    commit();
    assert(!payload().deletedItems.some((item) => item.id === expiredDeletedId), "expired deleted item pruning did not persist");

    const eventId = marker + "-event";
    dashboard.events.push({ id: eventId, title: marker + " event", date: todayISO(), allDay: true, start: null, end: null, category: "work", location: "", memo: "undo smoke", repeat: "none", repeatUntil: null, exceptions: [], createdAt: nowISO() });
    commit();
    deleteEvent(eventId);
    assert(!dashboard.events.some((item) => item.id === eventId), "event was not deleted");
    await sleep(3600);
    await clickUndo("일정을 삭제했습니다");
    assert(dashboard.events.some((item) => item.id === eventId && item.memo === "undo smoke"), "event was not restored");

    const todoId = marker + "-todo";
    dashboard.todos.push({ id: todoId, title: marker + " todo", due: null, priority: "med", done: false, category: "", memo: "undo smoke", createdAt: nowISO() });
    commit();
    deleteTodo(todoId);
    assert(!dashboard.todos.some((item) => item.id === todoId), "todo was not deleted");
    await clickUndo("할 일을 삭제했습니다");
    assert(dashboard.todos.some((item) => item.id === todoId && item.memo === "undo smoke"), "todo was not restored");

    const noteId = marker + "-note";
    dashboard.notes.push({ id: noteId, title: marker + " note", body: "undo smoke", color: "#22d3ee", pinned: false, updatedAt: nowISO() });
    commit();
    deleteNote(noteId);
    assert(!dashboard.notes.some((item) => item.id === noteId), "note was not deleted");
    await clickUndo("메모를 삭제했습니다");
    assert(dashboard.notes.some((item) => item.id === noteId && item.body === "undo smoke"), "note was not restored");

    const habitId = marker + "-habit";
    if (!Array.isArray(dashboard.habits)) dashboard.habits = [];
    dashboard.habits.push({ id: habitId, name: marker + " habit", emoji: "✓", color: "#17d983", target: 5, createdAt: nowISO(), archived: false, log: { [todayISO()]: true } });
    commit();
    deleteHabit(habitId);
    assert(!dashboard.habits.some((item) => item.id === habitId), "habit was not deleted");
    await clickUndo("습관을 삭제했습니다");
    assert(dashboard.habits.some((item) => item.id === habitId && item.log && item.log[todayISO()] === true), "habit was not restored");

    const issueId = marker + "-issue";
    dashboard.issues.push({ id: issueId, project: projectId, title: marker + " issue", status: "todo", priority: "med", assignee: "", labels: ["undo"], due: null, estimate: 1 });
    rebuildIndexes();
    commit();
    deleteIssue(issueId);
    assert(!dashboard.issues.some((item) => item.id === issueId), "issue was not deleted");
    await clickUndo("이슈를 삭제했습니다");
    assert(dashboard.issues.some((item) => item.id === issueId && item.labels.includes("undo")), "issue was not restored");

    const taskA = marker + "-task-a";
    const taskB = marker + "-task-b";
    dashboard.gantt.tasks.push(
      { id: taskA, project: projectId, name: marker + " task A", start: "2026-06-08", end: "2026-06-09", owner: "", deps: [], milestone: false, color: "blue" },
      { id: taskB, project: projectId, name: marker + " task B", start: "2026-06-09", end: "2026-06-10", owner: "", deps: [taskA], milestone: false, color: "green" }
    );
    commit();
    deleteTask(taskA);
    assert(!dashboard.gantt.tasks.some((item) => item.id === taskA), "task was not deleted");
    assert(!dashboard.gantt.tasks.find((item) => item.id === taskB).deps.includes(taskA), "task dependency was not removed");
    await clickUndo("작업을 삭제했습니다");
    assert(dashboard.gantt.tasks.some((item) => item.id === taskA), "task was not restored");
    assert(dashboard.gantt.tasks.find((item) => item.id === taskB).deps.includes(taskA), "task dependency was not restored");

    const queryId = marker + "-query";
    dashboard.queries.push({ id: queryId, instance: instanceId, db: "app", text: "select 1", avgMs: 1, p95Ms: 2, count: 3, planHint: "undo smoke", lastRun: "2026-06-08 10:00" });
    commit();
    if (typeof deleteQuery === "function") deleteQuery(queryId);
    else dbCatalogCall("deleteQuery", queryId);
    assert(!dashboard.queries.some((item) => item.id === queryId), "query was not deleted");
    await clickUndo("쿼리를 삭제했습니다");
    assert(dashboard.queries.some((item) => item.id === queryId && item.planHint === "undo smoke"), "query was not restored");

    const migrationId = marker + "-migration";
    dashboard.migrations.push({ id: migrationId, instance: instanceId, title: marker + " migration", status: "pending", scheduledAt: "2026-06-08 02:00" });
    commit();
    if (typeof deleteMigration === "function") deleteMigration(migrationId);
    else dbCatalogCall("deleteMigration", migrationId);
    assert(!dashboard.migrations.some((item) => item.id === migrationId), "migration was not deleted");
    await clickUndo("마이그레이션을 삭제했습니다");
    assert(dashboard.migrations.some((item) => item.id === migrationId && item.scheduledAt === "2026-06-08 02:00"), "migration was not restored");

    const stored = payload();
    assert(stored.events.some((item) => item.id === eventId), "restored event did not persist");
    assert(stored.todos.some((item) => item.id === todoId), "restored todo did not persist");
    assert(stored.notes.some((item) => item.id === noteId), "restored note did not persist");
    assert(stored.habits.some((item) => item.id === habitId), "restored habit did not persist");
    assert(stored.issues.some((item) => item.id === issueId), "restored issue did not persist");
    assert(stored.gantt.tasks.some((item) => item.id === taskA), "restored task did not persist");
    assert(stored.gantt.tasks.find((item) => item.id === taskB).deps.includes(taskA), "restored dependency did not persist");
    assert(stored.queries.some((item) => item.id === queryId), "restored query did not persist");
    assert(stored.migrations.some((item) => item.id === migrationId), "restored migration did not persist");
    assert(Array.isArray(dashboard.deletedItems) && dashboard.deletedItems.length === baselineDeletedCount, "immediate undo left entries in deletedItems");
    assert(Array.isArray(stored.deletedItems) && stored.deletedItems.length === baselineDeletedCount, "deletedItems cleanup did not persist after immediate undo");
    const deletedImportShape = {
      app: "JooPark Workspace",
      v: 3,
      deletedItems: [{
        id: marker + "-import-deleted",
        kind: "todo",
        recordId: marker + "-import-todo",
        label: marker + " import deleted todo",
        deletedAt: nowISO(),
        index: 0,
        record: { id: marker + "-import-todo", title: marker + " import todo", due: null, priority: "low", done: false, category: "", memo: "import guard", createdAt: nowISO() },
        meta: {},
      }],
    };
    const importGuards = window.JooParkImportGuards;
    assert(importGuards && importGuards.arrayKeys.includes("deletedItems"), "import guards do not expose deletedItems array key");
    assert(importGuards.isBackupShape(deletedImportShape), "deletedItems-only backup shape was not accepted");
    assert(importGuards.importArrayCount(deletedImportShape, "deletedItems") === 1, "deletedItems import count was not detected");
    assert(importGuards.backupSummaryItems(deletedImportShape).some(([label, count]) => label === "최근 삭제" && count === 1), "deletedItems import summary was missing");
    const deletedLimitViolations = importGuards.recordLimitViolations({
      deletedItems: Array.from({ length: 41 }, (_, index) => ({ ...deletedImportShape.deletedItems[0], id: marker + "-limit-" + index })),
    });
    assert(deletedLimitViolations.some((violation) => violation.key === "deletedItems" && violation.max === 40 && violation.count === 41), "deletedItems import limit guard did not trigger");

    const recoveryTodoId = marker + "-recovery-todo";
    dashboard.todos.push({ id: recoveryTodoId, title: marker + " recovery todo", due: null, priority: "high", done: false, category: "recovery", memo: "settings recovery smoke", createdAt: nowISO() });
    commit();
    deleteTodo(recoveryTodoId);
    assert(!dashboard.todos.some((item) => item.id === recoveryTodoId), "recovery todo was not deleted");
    const recoveryEntry = dashboard.deletedItems.find((item) => item && item.kind === "todo" && item.recordId === recoveryTodoId);
    assert(recoveryEntry, "recovery todo was not recorded in deletedItems");
    assert(payload().deletedItems.some((item) => item.recordId === recoveryTodoId), "recovery deletedItems entry did not persist");
    const expectedRecoveryCount = baselineDeletedCount + 1;
    openDataSafetyStatusSheet();
    await waitFor(() => {
      const access = document.querySelector("#sheet [data-topbar-data-safety-action-key='backup_recovery']");
      return access &&
        access.dataset.topbarDataSafetyActionValue === "최근 삭제 " + expectedRecoveryCount &&
        access.dataset.topbarDataSafetyActionStatus === "guarded" &&
        access.textContent.includes("최근 삭제 " + expectedRecoveryCount + "개 복구 가능");
    }, "data safety sheet did not expose recently deleted count");
    closeSheet({ restoreFocus: false });
    await sleep(8400);
    assert(!Array.from(document.querySelectorAll("#toastRegion [data-toast-action]")).some((button) => button.textContent.includes("되돌리기")), "undo action survived past timeout");
    commandPaletteCall("open");
    await waitFor(() => document.querySelector("#palette.open") && document.querySelector("#paletteInput"), "command palette did not open for recovery command");
    const paletteInput = document.querySelector("#paletteInput");
    paletteInput.value = "최근 삭제";
    paletteInput.dispatchEvent(new Event("input", { bubbles: true }));
    await waitFor(() => Array.from(document.querySelectorAll("#paletteResults .pal-item")).some((button) => button.textContent.includes("최근 삭제 복구")), "recently deleted command was missing from palette");
    Array.from(document.querySelectorAll("#paletteResults .pal-item")).find((button) => button.textContent.includes("최근 삭제 복구")).click();
    await waitFor(() => {
      const panel = document.querySelector("[data-settings-deleted-recovery]");
      return document.body.dataset.view === "settings" && panel && panel.dataset.deletedRecoveryCommandFocused === "true";
    }, "command palette recovery command did not focus settings recovery panel");
    assert(document.querySelector("[data-settings-deleted-recovery]").dataset.deletedRecoveryRetentionDays === "30", "settings recovery retention metadata missing");
    const searchInput = document.querySelector("[data-deleted-recovery-search]");
    assert(searchInput, "settings recovery search input missing");
    searchInput.value = "definitely-no-recovery-match";
    searchInput.dispatchEvent(new Event("input", { bubbles: true }));
    await waitFor(() => {
      const panel = document.querySelector("[data-settings-deleted-recovery]");
      return panel &&
        panel.dataset.deletedRecoveryQuery === "definitely-no-recovery-match" &&
        panel.dataset.deletedRecoveryVisibleCount === "0" &&
        document.querySelector("[data-deleted-recovery-empty]");
    }, "settings recovery search did not produce an empty result");
    document.querySelector('[data-action="clear-deleted-recovery-filter"]').click();
    await waitFor(() => document.querySelector("[data-settings-deleted-recovery]").dataset.deletedRecoveryVisibleCount === String(expectedRecoveryCount), "settings recovery filter reset did not restore rows");
    const kindFilter = document.querySelector("[data-deleted-recovery-kind-filter]");
    assert(kindFilter, "settings recovery kind filter missing");
    kindFilter.value = "todo";
    kindFilter.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => {
      const panel = document.querySelector("[data-settings-deleted-recovery]");
      return panel &&
        panel.dataset.deletedRecoveryKind === "todo" &&
        panel.dataset.deletedRecoveryVisibleCount === "1" &&
        document.querySelector('[data-deleted-recovery-item][data-deleted-id="' + recoveryEntry.id + '"]');
    }, "settings recovery kind filter did not keep todo row");
    const row = document.querySelector('[data-deleted-recovery-item][data-deleted-id="' + recoveryEntry.id + '"]');
    assert(row, "settings recovery row missing");
    assert(row.dataset.deletedRecoveryExpiresAt && row.dataset.deletedRecoveryExpiresAt.includes("T"), "settings recovery row did not expose expiry timestamp");
    const daysRemaining = Number(row.dataset.deletedRecoveryDaysRemaining);
    assert(Number.isFinite(daysRemaining) && daysRemaining >= 1 && daysRemaining <= 30, "settings recovery row did not expose bounded days remaining");
    const expiryBadge = row.querySelector("[data-deleted-recovery-expiry]");
    assert(expiryBadge && expiryBadge.textContent.includes("일 남음"), "settings recovery row did not show an expiry badge");
    const restoreButton = row.querySelector('[data-action="restore-deleted-item"]');
    assert(restoreButton, "settings recovery restore button missing");
    restoreButton.click();
    await waitFor(() => dashboard.todos.some((item) => item.id === recoveryTodoId && item.memo === "settings recovery smoke"), "settings recovery did not restore todo");
    assert(!dashboard.deletedItems.some((item) => item.id === recoveryEntry.id), "settings recovery did not remove deletedItems entry");
    const storedAfterRecovery = payload();
    assert(storedAfterRecovery.todos.some((item) => item.id === recoveryTodoId && item.memo === "settings recovery smoke"), "settings recovery restore did not persist");
    assert(!storedAfterRecovery.deletedItems.some((item) => item.id === recoveryEntry.id), "settings recovery cleanup did not persist");

    const discardTodoId = marker + "-discard-todo";
    dashboard.todos.push({ id: discardTodoId, title: marker + " discard todo", due: null, priority: "low", done: false, category: "recovery", memo: "discard smoke", createdAt: nowISO() });
    commit();
    deleteTodo(discardTodoId);
    const discardEntry = dashboard.deletedItems.find((item) => item && item.kind === "todo" && item.recordId === discardTodoId);
    assert(discardEntry, "discard todo was not recorded in deletedItems");
    const discardUndoToast = Array.from(document.querySelectorAll("#toastRegion .toast"))
      .reverse()
      .find((toast) => toast.textContent.includes("할 일을 삭제했습니다") && toast.querySelector("[data-toast-action]"));
    assert(discardUndoToast, "discard todo undo toast missing");
    setView("settings");
    await waitFor(() => document.querySelector('[data-deleted-recovery-item][data-deleted-id="' + discardEntry.id + '"]'), "discard recovery row missing");
    document.querySelector('[data-deleted-recovery-item][data-deleted-id="' + discardEntry.id + '"] [data-action="discard-deleted-item"]').click();
    await waitFor(() => !dashboard.deletedItems.some((item) => item.id === discardEntry.id), "discard did not remove deletedItems entry");
    const staleDiscardUndo = discardUndoToast.querySelector("[data-toast-action]");
    assert(staleDiscardUndo, "discard stale undo action missing");
    staleDiscardUndo.click();
    await sleep(180);
    assert(!dashboard.todos.some((item) => item.id === discardTodoId), "discarded todo was restored by stale undo");
    assert(!payload().deletedItems.some((item) => item.id === discardEntry.id), "discard cleanup did not persist");

    const bulkTodoId = marker + "-bulk-todo";
    const bulkNoteId = marker + "-bulk-note";
    dashboard.todos.push({ id: bulkTodoId, title: marker + " bulk todo", due: null, priority: "med", done: false, category: "bulk", memo: "bulk restore", createdAt: nowISO() });
    dashboard.notes.push({ id: bulkNoteId, title: marker + " bulk note", body: "bulk restore", color: "#22d3ee", pinned: false, updatedAt: nowISO() });
    commit();
    deleteTodo(bulkTodoId);
    deleteNote(bulkNoteId);
    const bulkTodoEntry = dashboard.deletedItems.find((item) => item && item.recordId === bulkTodoId);
    const bulkNoteEntry = dashboard.deletedItems.find((item) => item && item.recordId === bulkNoteId);
    assert(bulkTodoEntry && bulkNoteEntry, "bulk restore entries were not recorded");
    setView("settings");
    await waitFor(() => document.querySelector('[data-action="restore-all-deleted-items"]'), "restore all deleted items button missing");
    document.querySelector('[data-action="restore-all-deleted-items"]').click();
    await waitFor(() => dashboard.todos.some((item) => item.id === bulkTodoId) && dashboard.notes.some((item) => item.id === bulkNoteId), "restore all did not restore every record");
    assert(!dashboard.deletedItems.some((item) => item.id === bulkTodoEntry.id || item.id === bulkNoteEntry.id), "restore all did not remove restored ledger entries");
    const storedAfterBulkRestore = payload();
    assert(storedAfterBulkRestore.todos.some((item) => item.id === bulkTodoId) && storedAfterBulkRestore.notes.some((item) => item.id === bulkNoteId), "restore all records did not persist");
    assert(!storedAfterBulkRestore.deletedItems.some((item) => item.id === bulkTodoEntry.id || item.id === bulkNoteEntry.id), "restore all ledger cleanup did not persist");

    const clearNoteA = marker + "-clear-note-a";
    const clearNoteB = marker + "-clear-note-b";
    dashboard.notes.push(
      { id: clearNoteA, title: marker + " clear note A", body: "clear smoke A", color: "#22d3ee", pinned: false, updatedAt: nowISO() },
      { id: clearNoteB, title: marker + " clear note B", body: "clear smoke B", color: "#22d3ee", pinned: false, updatedAt: nowISO() }
    );
    commit();
    deleteNote(clearNoteA);
    deleteNote(clearNoteB);
    assert(dashboard.deletedItems.some((item) => item.recordId === clearNoteA), "clear note A was not recorded");
    assert(dashboard.deletedItems.some((item) => item.recordId === clearNoteB), "clear note B was not recorded");
    setView("settings");
    await waitFor(() => document.querySelector('[data-action="clear-deleted-items"]'), "clear deleted items button missing");
    document.querySelector('[data-action="clear-deleted-items"]').click();
    await waitFor(() => document.querySelector('#modal.open [data-action="modal-confirm"]'), "clear confirmation modal missing");
    document.querySelector('#modal.open [data-action="modal-confirm"]').click();
    await waitFor(() => !document.querySelector("#modal.open") && dashboard.deletedItems.length === baselineDeletedCount, "clear deleted items did not empty ledger");
    assert(!dashboard.notes.some((item) => item.id === clearNoteA || item.id === clearNoteB), "cleared notes were restored unexpectedly");
    const storedAfterClear = payload();
    assert(!storedAfterClear.deletedItems.some((item) => item.recordId === clearNoteA || item.recordId === clearNoteB), "clear deleted items cleanup did not persist");

    return {
      status: "pass",
      marker,
      checkedTypes: ["event", "todo", "note", "habit", "issue", "task", "query", "migration"],
      persisted: true,
      recentlyDeletedRecovery: true,
      discardAndClear: true,
      retentionPruned: true,
      searchAndKindFilter: true,
      commandPaletteRecovery: true,
      importGuardDeletedItems: true,
      restoreAll: true,
    };
  } catch (error) {
    failures.push(error.message);
    return { status: "fail", marker, failures };
  }
})()
`;

async function main() {
  try {
    const response = await fetch(baseUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    progress("base-url-ok", { baseUrl, status: response.status });
  } catch (error) {
    throw new Error(`Unable to reach BASE_URL ${baseUrl}: ${error.message}${error.cause ? ` (${error.cause})` : ""}`);
  }

  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-extensions",
    "--disable-gpu",
    "--disable-sync",
    "--no-default-browser-check",
    "--no-first-run",
    "--remote-debugging-port=0",
    `--user-data-dir=${tmpProfile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  let pageClient;
  try {
    const browserWs = await waitForDevTools(chrome);
    progress("devtools-ready");
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();
    await pageClient.send("Runtime.enable");
    await pageClient.send("Page.enable");
    await pageClient.send("Page.navigate", { url: `${baseUrl}/index.html#todo` });
    await evaluate(pageClient, `
      new Promise((resolve, reject) => {
        const started = Date.now();
        const check = () => {
          const ready = document.readyState === "complete" &&
            document.body &&
            document.body.dataset.view === "todo" &&
            typeof dashboard !== "undefined";
          if (ready) resolve(true);
          else if (Date.now() - started > 9000) reject(new Error("todo route not ready"));
          else setTimeout(check, 100);
        };
        check();
      })
    `);
    progress("app-ready");

    const result = await evaluate(pageClient, deleteUndoExpression, 70000);
    result.baseUrl = baseUrl;
    console.log(JSON.stringify(result, null, 2));
    if (result.status !== "pass") process.exitCode = 1;
  } finally {
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    rmSync(tmpProfile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  rmSync(tmpProfile, { recursive: true, force: true });
  console.error(error.stack || error.message);
  process.exit(1);
});

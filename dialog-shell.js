(function (root) {
  "use strict";

  const VERSION = "joopark-dialog-shell/v1";
  const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fallbackRaw(value) {
    return { __raw: true, value: value == null ? "" : String(value) };
  }

  function fallbackHtml(strings, ...values) {
    let out = "";
    for (let i = 0; i < strings.length; i += 1) {
      out += strings[i];
      if (i >= values.length) continue;
      const value = values[i];
      if (value === null || value === undefined || value === false) continue;
      if (value && value.__raw) out += value.value;
      else if (Array.isArray(value)) out += value.map((item) => item && item.__raw ? item.value : escapeHtml(item)).join("");
      else out += escapeHtml(value);
    }
    return out;
  }

  function createDialogShell(deps) {
    const options = deps || {};
    const documentRef = options.document || root.document;
    const body = options.body || (documentRef && documentRef.body);
    const refs = options.refs || {};
    const state = options.state || {};
    const html = typeof options.html === "function" ? options.html : fallbackHtml;
    const raw = typeof options.raw === "function" ? options.raw : fallbackRaw;
    const setHTML = typeof options.setHTML === "function"
      ? options.setHTML
      : function assignHTML(node, htmlString) {
          if (node) node.innerHTML = htmlString || "";
        };

    function setNotificationTriggerExpanded(expanded) {
      if (!documentRef) return;
      documentRef.querySelectorAll('[data-action="open-notifications"][aria-expanded]').forEach((trigger) => {
        trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
      });
    }

    function hasOwn(object, key) {
      return Object.prototype.hasOwnProperty.call(object, key);
    }

    function listOf(value) {
      return Array.isArray(value) ? value : [];
    }

    function sheetActionButtonHTML(entry, includeContextIds = false) {
      const target = entry.target || "";
      const extraClass = includeContextIds && entry.action === "show-project-prompt-handoff"
        ? " sheet-action-prompt"
        : "";
      if (!includeContextIds) {
        return raw(html`<button type="button" class="sheet-action" data-action="${entry.action}" data-target="${target}">${entry.label}</button>`);
      }
      return raw(html`<button type="button" class="sheet-action${extraClass}" data-action="${entry.action}" data-project-id="${target}" data-issue-id="${target}" data-task-id="${target}" data-member-id="${target}" data-query-id="${target}" data-mig-id="${target}" data-target="${target}">${entry.label}</button>`);
    }

    function renderSheetMeta(meta) {
      if (!meta) return "";
      const items = listOf(meta.items);
      function actionsHTML(actions) {
        const actionItems = listOf(actions);
        if (!actionItems.length) return "";
        return html`<div class="sheet-actions">${actionItems.map((entry) => sheetActionButtonHTML(entry, true))}</div>`;
      }
      if (meta.type === "list") {
        const listHTML = html`<ul>${items.map((entry) => {
          const cls = entry.pre ? "sheet-meta-pre" : entry.html ? "sheet-meta-html" : "";
          const value = entry.html ? raw(entry.html) : entry.pre ? raw(html`<pre data-sheet-artifact-body>${entry.value}</pre>`) : entry.value;
          return raw(html`<li class="${cls}">${entry.label ? raw(html`<strong>${entry.label}:</strong> `) : ""}${value}</li>`);
        })}</ul>`;
        return listHTML + actionsHTML(meta.actions);
      }
      if (meta.type === "paragraphs") {
        const parasHTML = html`${items.map((entry) => raw(html`<p>${entry.label ? raw(html`<strong>${entry.label}:</strong> `) : ""}${entry.value}</p>`))}`;
        return parasHTML + actionsHTML(meta.actions);
      }
      if (meta.type === "actions") {
        return html`<div class="sheet-actions">${items.map((entry) => sheetActionButtonHTML(entry))}</div>`;
      }
      return "";
    }

    function focusNode(target) {
      if (target && typeof target.focus === "function") target.focus();
    }

    function restoreFocusAfterClose(target, isClosed) {
      if (!target || typeof target.focus !== "function") return;
      focusNode(target);
      [0, 80].forEach((delay) => {
        root.setTimeout(() => {
          if (isClosed()) focusNode(target);
        }, delay);
      });
    }

    function dialogNode(rootNode, selector) {
      return rootNode ? rootNode.querySelector(selector) : null;
    }

    function sheetCloseButton(sheetRefs) {
      return dialogNode(sheetRefs.root, '.sheet-head [data-action="close-sheet"]');
    }

    function modalFirstInput(modalRefs) {
      return dialogNode(modalRefs.body, "input, select, textarea");
    }

    function modalCloseButton(modalRefs) {
      return dialogNode(modalRefs.root, ".modal-close");
    }

    function dialogPanel(rootNode, selector) {
      return dialogNode(rootNode, selector) || rootNode;
    }

    function setDialogOpenState(rootNode, bodyClass, open) {
      if (!rootNode) return;
      rootNode.classList.toggle("open", open);
      rootNode.setAttribute("aria-hidden", open ? "false" : "true");
      if (body) body.classList.toggle(bodyClass, open);
    }

    function openSheet(title, bodyText, meta, config) {
      const sheetRefs = refs.sheets || {};
      if (!sheetRefs.root) return false;
      const openOptions = config || {};
      state.previousFocus = documentRef ? documentRef.activeElement : null;
      setNotificationTriggerExpanded(openOptions.notificationExpanded === true);
      if (sheetRefs.title) sheetRefs.title.textContent = title;
      if (sheetRefs.body) {
        if (hasOwn(openOptions, "bodyHTML")) {
          sheetRefs.body.textContent = "";
          setHTML(sheetRefs.body, openOptions.bodyHTML || "");
        } else {
          sheetRefs.body.textContent = bodyText || "";
        }
      }
      if (sheetRefs.meta) {
        if (hasOwn(openOptions, "metaHTML")) {
          setHTML(sheetRefs.meta, openOptions.metaHTML || "");
        } else {
          setHTML(sheetRefs.meta, renderSheetMeta(meta));
        }
      }
      setDialogOpenState(sheetRefs.root, "sheet-open", true);
      const closeBtn = sheetCloseButton(sheetRefs);
      focusNode(closeBtn);
      return true;
    }

    function closeSheet(config) {
      const sheetRefs = refs.sheets || {};
      if (!isSheetOpen()) return false;
      const closeOptions = config || {};
      const restoreFocus = closeOptions.restoreFocus !== false;
      const previousFocus = state.previousFocus;
      setDialogOpenState(sheetRefs.root, "sheet-open", false);
      setNotificationTriggerExpanded(false);
      if (restoreFocus) restoreFocusAfterClose(previousFocus, () => !isSheetOpen());
      state.previousFocus = null;
      return true;
    }

    function isSheetOpen() {
      const sheetRefs = refs.sheets || {};
      return Boolean(sheetRefs.root && sheetRefs.root.classList.contains("open"));
    }

    function openModal(title, bodyHTML, onConfirm) {
      const modalRefs = refs.modal || {};
      if (!modalRefs.root) return false;
      state.previousFocus = documentRef ? documentRef.activeElement : null;
      if (modalRefs.title) modalRefs.title.textContent = title;
      setHTML(modalRefs.body, bodyHTML);
      state.modalOnConfirm = onConfirm || null;
      setDialogOpenState(modalRefs.root, "modal-open", true);
      const firstInput = modalFirstInput(modalRefs);
      if (firstInput) focusNode(firstInput);
      else {
        const closeBtn = modalCloseButton(modalRefs);
        focusNode(closeBtn);
      }
      return true;
    }

    function closeModal() {
      const modalRefs = refs.modal || {};
      if (!isModalOpen()) return false;
      const previousFocus = state.previousFocus;
      setDialogOpenState(modalRefs.root, "modal-open", false);
      state.modalOnConfirm = null;
      restoreFocusAfterClose(previousFocus, () => !isModalOpen());
      state.previousFocus = null;
      return true;
    }

    function isModalOpen() {
      const modalRefs = refs.modal || {};
      return Boolean(modalRefs.root && modalRefs.root.classList.contains("open"));
    }

    function getOpenDialogRoot() {
      const modalRefs = refs.modal || {};
      const sheetRefs = refs.sheets || {};
      if (isModalOpen()) {
        return dialogPanel(modalRefs.root, ".modal-panel");
      }
      if (isSheetOpen()) {
        return dialogPanel(sheetRefs.root, ".sheet-panel");
      }
      return null;
    }

    function getFocusable(rootNode) {
      if (!rootNode) return [];
      return Array.from(rootNode.querySelectorAll(FOCUSABLE_SELECTOR)).filter((el) => {
        if (el.hasAttribute("hidden")) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      });
    }

    function trapTab(event, rootNode) {
      if (event.key !== "Tab") return;
      const focusable = getFocusable(rootNode);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = documentRef ? documentRef.activeElement : null;
      if (event.shiftKey) {
        if (active === first || !rootNode.contains(active)) {
          event.preventDefault();
          focusNode(last);
        }
      } else if (active === last || !rootNode.contains(active)) {
        event.preventDefault();
        focusNode(first);
      }
    }

    return {
      version: VERSION,
      renderSheetMeta,
      setNotificationTriggerExpanded,
      restoreFocusAfterClose,
      openSheet,
      closeSheet,
      isSheetOpen,
      openModal,
      closeModal,
      isModalOpen,
      getOpenDialogRoot,
      getFocusable,
      trapTab,
    };
  }

  root.JooParkDialogShell = {
    version: VERSION,
    create: createDialogShell,
  };
})(window);

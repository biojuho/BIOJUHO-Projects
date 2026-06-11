(function (root) {
  "use strict";

  const VERSION = "joopark-project-picker/v1";
  const NO_RESULTS_TEXT = "일치하는 프로젝트가 없습니다. 다른 검색어를 입력하세요.";

  function fallbackRaw(value) {
    return { __raw: true, value: value == null ? "" : String(value) };
  }

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
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

  function createProjectPicker(deps) {
    const options = deps || {};
    const documentRef = options.document || root.document;
    const body = options.body || (documentRef && documentRef.body);
    const refs = options.refs || {};
    const state = options.state || { query: "" };
    const dashboard = options.dashboard || { projects: [] };
    const html = typeof options.html === "function" ? options.html : fallbackHtml;
    const raw = typeof options.raw === "function" ? options.raw : fallbackRaw;
    const setHTML = typeof options.setHTML === "function"
      ? options.setHTML
      : function assignHTML(node, htmlString) {
          if (node) node.innerHTML = htmlString || "";
        };
    const matches = typeof options.matches === "function"
      ? options.matches
      : function defaultMatches(value, query) {
          return !query || String(value || "").toLowerCase().includes(String(query || "").toLowerCase());
        };
    const projectSearchText = typeof options.projectSearchText === "function"
      ? options.projectSearchText
      : function defaultProjectSearchText(project) {
          return [project && project.name, project && project.owner, project && project.description].filter(Boolean).join(" ");
        };
    const spark = typeof options.spark === "function" ? options.spark : function noSpark() { return ""; };
    const healthColor = options.healthColor || {};
    let initialized = false;

    function projectPickerNode(selector) {
      return refs.projectPicker ? refs.projectPicker.querySelector(selector) : null;
    }

    function statusEl() {
      return projectPickerNode("#projectPickerStatus");
    }

    function elements() {
      return {
        searchInput: projectPickerNode("#projectPickerSearch"),
        list: projectPickerNode("#projectPickerList"),
        statusEl: statusEl(),
      };
    }

    function setAttributes(node, attrs) {
      if (!node) return;
      Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, value));
    }

    function bindOnce(node, key, bind) {
      if (!node || node.dataset[key]) return;
      node.dataset[key] = "true";
      bind(node);
    }

    function normalizeAccessibility() {
      setAttributes(refs.projectPicker, { role: "dialog", "aria-labelledby": "projectSelectLabel" });
      setAttributes(refs.projectSelect, { "aria-haspopup": "dialog", "aria-controls": "projectPicker" });
      const current = elements();
      setAttributes(current.searchInput, { "aria-controls": "projectPickerList", "aria-describedby": "projectPickerStatus" });
      setAttributes(current.list, { role: "listbox", "aria-label": "프로젝트 목록" });
      setAttributes(current.statusEl, { role: "status", "aria-live": "polite", "aria-atomic": "true" });
      return current;
    }

    function scaffoldReady() {
      const current = normalizeAccessibility();
      return Boolean(current.searchInput && current.list && current.statusEl);
    }

    function setStatus(message, config) {
      const node = statusEl();
      if (!node) return;
      const text = message || "";
      const optionsForStatus = config || {};
      node.textContent = text;
      node.classList.toggle("is-visible", Boolean(optionsForStatus.visible && text));
    }

    function clearInputValue(input) {
      if (input) input.value = "";
    }

    function resetPickerQuery(input) {
      state.query = "";
      clearInputValue(input);
    }

    function focusProjectSelect() {
      if (refs.projectSelect) refs.projectSelect.focus();
    }

    function isPickerHidden() {
      return Boolean(refs.projectPicker && refs.projectPicker.hasAttribute("hidden"));
    }

    function shouldRestoreHiddenSearchFocus() {
      const active = documentRef.activeElement;
      return Boolean(refs.projectSelect && (!active || active === documentRef.body || refs.projectPicker.contains(active)));
    }

    function projectOptionHTML(project, index) {
      const isCurrent = project.id === dashboard.currentProjectId;
      return html`
        <button type="button" id="project-option-${index}" role="option" class="project-option ${raw(isCurrent ? "is-current" : "")}" data-action="pick-project" data-project-id="${project.id}" aria-selected="${raw(isCurrent ? "true" : "false")}">
          <div class="project-option-row">
            <strong>${project.name}</strong>
            <span class="project-env-pill">${project.category || project.owner}</span>
          </div>
          <div class="project-meta">
            <span><b>진행률</b> ${project.progress}%</span>
            <span><b>이슈</b> ${project.openIssues}</span>
            ${project.description ? raw(html`<span class="project-meta-summary">${project.description}</span>`) : ""}
            <span class="project-meta-spark">${raw(spark(project.burn, healthColor[project.health] || "#22d3ee"))}</span>
          </div>
        </button>
      `;
    }

    function projectList() {
      return Array.isArray(dashboard.projects) ? dashboard.projects : [];
    }

    function projectMatchesQuery(project, query) {
      return matches(projectSearchText(project), query);
    }

    function renderOptions() {
      const list = projectPickerNode("#projectPickerList");
      if (!list) return;
      const query = state.query;
      const filtered = projectList().filter((project) => projectMatchesQuery(project, query));
      if (filtered.length === 0) {
        setHTML(list, "");
        setStatus(NO_RESULTS_TEXT, { visible: true });
        return;
      }
      setStatus(`${filtered.length}개 프로젝트`);
      setHTML(list, filtered.map(projectOptionHTML).join(""));
    }

    function restoreFocus() {
      if (!refs.projectSelect) return;
      focusProjectSelect();
      [0, 80, 180].forEach((delay) => {
        root.setTimeout(() => {
          if (isPickerHidden()) focusProjectSelect();
        }, delay);
      });
    }

    function handleSearchKeydown(event) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
    }

    function handleSearchInput(event) {
      if (isPickerHidden()) {
        resetPickerQuery(event.target);
        setStatus("");
        if (shouldRestoreHiddenSearchFocus()) {
          focusProjectSelect();
        }
        return;
      }
      state.query = event.target.value;
      renderOptions();
    }

    function handlePickerFocusout(event) {
      const next = event.relatedTarget;
      if (!next) return;
      if (containsPickerTarget(next)) return;
      setOpen(false);
    }

    function setPickerShellOpen(open) {
      if (open) {
        refs.projectPicker.removeAttribute("hidden");
        if (body) body.classList.add("project-picker-open");
        refs.projectSelect.setAttribute("aria-expanded", "true");
      } else {
        if (body) body.classList.remove("project-picker-open");
        refs.projectPicker.setAttribute("hidden", "");
        refs.projectSelect.setAttribute("aria-expanded", "false");
      }
    }

    function ensureScaffold() {
      if (!refs.projectPicker) return;
      if (initialized && scaffoldReady()) return;
      setHTML(refs.projectPicker, html`
        <div class="project-search">
          <span aria-hidden="true">⌕</span>
          <input id="projectPickerSearch" type="search" placeholder="프로젝트 검색" autocomplete="off" aria-label="프로젝트 검색" aria-controls="projectPickerList" aria-describedby="projectPickerStatus" />
        </div>
        <div id="projectPickerList" class="project-list" role="listbox" aria-label="프로젝트 목록"></div>
        <div id="projectPickerStatus" class="project-picker-status" role="status" aria-live="polite" aria-atomic="true"></div>
      `);
      const current = normalizeAccessibility();
      bindOnce(current.searchInput, "projectPickerInputBound", (searchInput) => {
        searchInput.addEventListener("keydown", handleSearchKeydown);
        searchInput.addEventListener("input", handleSearchInput);
      });
      bindOnce(refs.projectPicker, "projectPickerFocusoutBound", (projectPicker) => {
        projectPicker.addEventListener("focusout", handlePickerFocusout);
      });
      initialized = true;
    }

    function setOpen(open) {
      if (!refs.projectPicker || !refs.projectSelect) return;
      if (open) {
        ensureScaffold();
        const searchInput = projectPickerNode("#projectPickerSearch");
        resetPickerQuery(searchInput);
        renderOptions();
        setPickerShellOpen(true);
        if (searchInput) searchInput.focus();
      } else {
        const restore = refs.projectPicker.contains(documentRef.activeElement);
        const current = normalizeAccessibility();
        resetPickerQuery(current.searchInput);
        if (current.list) setHTML(current.list, "");
        if (restore) focusProjectSelect();
        setStatus("");
        setPickerShellOpen(false);
        if (restore) restoreFocus();
      }
    }

    function isOpen() {
      return Boolean(refs.projectPicker && !isPickerHidden());
    }

    function containsPickerTarget(target) {
      return Boolean(target && ((refs.projectPicker && refs.projectPicker.contains(target)) || (refs.projectSelect && refs.projectSelect.contains(target))));
    }

    function toggle() {
      if (!refs.projectPicker) return;
      setOpen(!isOpen());
    }

    function closeIfOutside(target) {
      if (!isOpen()) return false;
      if (containsPickerTarget(target)) return false;
      setOpen(false);
      return true;
    }

    return {
      version: VERSION,
      statusEl,
      elements,
      normalizeAccessibility,
      scaffoldReady,
      setStatus,
      renderOptions,
      restoreFocus,
      ensureScaffold,
      setOpen,
      toggle,
      isOpen,
      closeIfOutside,
    };
  }

  root.JooParkProjectPicker = {
    version: VERSION,
    create: createProjectPicker,
  };
})(window);

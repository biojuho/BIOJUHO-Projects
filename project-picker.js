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

    function normalizeAccessibility() {
      if (refs.projectPicker) {
        refs.projectPicker.setAttribute("role", "dialog");
        refs.projectPicker.setAttribute("aria-labelledby", "projectSelectLabel");
      }
      if (refs.projectSelect) {
        refs.projectSelect.setAttribute("aria-haspopup", "dialog");
        refs.projectSelect.setAttribute("aria-controls", "projectPicker");
      }
      const current = elements();
      if (current.searchInput) {
        current.searchInput.setAttribute("aria-controls", "projectPickerList");
        current.searchInput.setAttribute("aria-describedby", "projectPickerStatus");
      }
      if (current.list) {
        current.list.setAttribute("role", "listbox");
        current.list.setAttribute("aria-label", "프로젝트 목록");
      }
      if (current.statusEl) {
        current.statusEl.setAttribute("role", "status");
        current.statusEl.setAttribute("aria-live", "polite");
        current.statusEl.setAttribute("aria-atomic", "true");
      }
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

    function renderOptions() {
      const list = projectPickerNode("#projectPickerList");
      if (!list) return;
      const query = state.query;
      const filtered = (Array.isArray(dashboard.projects) ? dashboard.projects : []).filter((project) => matches(projectSearchText(project), query));
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
      refs.projectSelect.focus();
      root.setTimeout(() => {
        if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) refs.projectSelect.focus();
      }, 0);
      root.setTimeout(() => {
        if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) refs.projectSelect.focus();
      }, 80);
      root.setTimeout(() => {
        if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) refs.projectSelect.focus();
      }, 180);
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
      if (current.searchInput && !current.searchInput.dataset.projectPickerInputBound) {
        current.searchInput.dataset.projectPickerInputBound = "true";
        current.searchInput.addEventListener("keydown", (event) => {
          if (event.key !== "Escape") return;
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
        });
        current.searchInput.addEventListener("input", (event) => {
          if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) {
            event.target.value = "";
            state.query = "";
            setStatus("");
            if (refs.projectSelect && (!documentRef.activeElement || documentRef.activeElement === documentRef.body || refs.projectPicker.contains(documentRef.activeElement))) {
              refs.projectSelect.focus();
            }
            return;
          }
          state.query = event.target.value;
          renderOptions();
        });
      }
      if (!refs.projectPicker.dataset.projectPickerFocusoutBound) {
        refs.projectPicker.dataset.projectPickerFocusoutBound = "true";
        refs.projectPicker.addEventListener("focusout", (event) => {
          const next = event.relatedTarget;
          if (!next) return;
          if (refs.projectPicker.contains(next)) return;
          if (refs.projectSelect && refs.projectSelect.contains(next)) return;
          setOpen(false);
        });
      }
      initialized = true;
    }

    function setOpen(open) {
      if (!refs.projectPicker || !refs.projectSelect) return;
      if (open) {
        ensureScaffold();
        state.query = "";
        const searchInput = projectPickerNode("#projectPickerSearch");
        if (searchInput) searchInput.value = "";
        renderOptions();
        refs.projectPicker.removeAttribute("hidden");
        if (body) body.classList.add("project-picker-open");
        refs.projectSelect.setAttribute("aria-expanded", "true");
        if (searchInput) searchInput.focus();
      } else {
        const restore = refs.projectPicker.contains(documentRef.activeElement);
        const current = normalizeAccessibility();
        state.query = "";
        if (current.searchInput) current.searchInput.value = "";
        if (current.list) setHTML(current.list, "");
        if (restore) refs.projectSelect.focus();
        setStatus("");
        if (body) body.classList.remove("project-picker-open");
        refs.projectPicker.setAttribute("hidden", "");
        refs.projectSelect.setAttribute("aria-expanded", "false");
        if (restore) restoreFocus();
      }
    }

    function isOpen() {
      return Boolean(refs.projectPicker && !refs.projectPicker.hasAttribute("hidden"));
    }

    function toggle() {
      if (!refs.projectPicker) return;
      setOpen(refs.projectPicker.hasAttribute("hidden"));
    }

    function closeIfOutside(target) {
      if (!isOpen()) return false;
      if (refs.projectPicker.contains(target)) return false;
      if (refs.projectSelect && refs.projectSelect.contains(target)) return false;
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

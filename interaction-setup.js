(function (root) {
  "use strict";

  const VERSION = "joopark-interaction-setup/v1";

  function noop() {}

  function createInteractionSetup(deps = {}) {
    const documentRef = deps.document || root.document;
    const state = deps.state || {};
    const callbacks = {
      handleActions: typeof deps.handleActions === "function" ? deps.handleActions : noop,
      projectPickerIsOpen: typeof deps.projectPickerIsOpen === "function" ? deps.projectPickerIsOpen : () => false,
      closeProjectPickerIfOutside: typeof deps.closeProjectPickerIfOutside === "function" ? deps.closeProjectPickerIfOutside : noop,
      updateReviewIssueDraftAssignee: typeof deps.updateReviewIssueDraftAssignee === "function" ? deps.updateReviewIssueDraftAssignee : noop,
      setDeletedRecoveryKind: typeof deps.setDeletedRecoveryKind === "function" ? deps.setDeletedRecoveryKind : noop,
      updatePostInstallProofParser: typeof deps.updatePostInstallProofParser === "function" ? deps.updatePostInstallProofParser : noop,
      postInstallProofParserNode: typeof deps.postInstallProofParserNode === "function" ? deps.postInstallProofParserNode : () => null,
      setDeletedRecoveryQuery: typeof deps.setDeletedRecoveryQuery === "function" ? deps.setDeletedRecoveryQuery : noop,
      isModalOpen: typeof deps.isModalOpen === "function" ? deps.isModalOpen : () => false,
      closeModal: typeof deps.closeModal === "function" ? deps.closeModal : noop,
    };

    function closestTarget(event, selector) {
      const target = event && event.target;
      return target && typeof target.closest === "function" ? target.closest(selector) : null;
    }

    function handleClick(event) {
      const action = closestTarget(event, "[data-action]");
      if (action && action.tagName !== "FORM") {
        event.preventDefault();
        callbacks.handleActions({ target: action });
        return;
      }
      if (callbacks.projectPickerIsOpen()) callbacks.closeProjectPickerIfOutside(event.target);
    }

    function handleChange(event) {
      const assigneeSelect = closestTarget(event, "[data-issue-draft-assignee-select]");
      if (assigneeSelect) callbacks.updateReviewIssueDraftAssignee(assigneeSelect);
      const deletedRecoveryKind = closestTarget(event, "[data-deleted-recovery-kind-filter]");
      if (deletedRecoveryKind) callbacks.setDeletedRecoveryKind(deletedRecoveryKind.value);
    }

    function handleInput(event) {
      const parserInput = closestTarget(event, "[data-post-install-proof-parser-input]");
      if (parserInput) {
        callbacks.updatePostInstallProofParser(callbacks.postInstallProofParserNode(parserInput) || documentRef);
      }
      const deletedRecoverySearch = closestTarget(event, "[data-deleted-recovery-search]");
      if (deletedRecoverySearch) callbacks.setDeletedRecoveryQuery(deletedRecoverySearch.value);
    }

    function handleSubmit(event) {
      event.preventDefault();
      const actionForm = closestTarget(event, "form[data-action]");
      if (actionForm) {
        callbacks.handleActions({ target: actionForm });
        return;
      }
      if (callbacks.isModalOpen() && typeof state.modalOnConfirm === "function") {
        if (state.modalOnConfirm() !== false) callbacks.closeModal();
      }
    }

    function setup() {
      const body = documentRef && documentRef.body;
      if (!body || body.dataset.interactionSetupBound === "true") return;
      body.dataset.interactionSetupBound = "true";
      body.addEventListener("click", handleClick);
      body.addEventListener("change", handleChange);
      body.addEventListener("input", handleInput);
      body.addEventListener("submit", handleSubmit);
    }

    return {
      version: VERSION,
      setup,
      handleClick,
      handleChange,
      handleInput,
      handleSubmit,
    };
  }

  root.JooParkInteractionSetup = {
    version: VERSION,
    create: createInteractionSetup,
  };
})(window);

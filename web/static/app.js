(function () {
  function repeatCurrentPrompt() {
    const form = document.querySelector("form[data-recorder]");
    if (!form) return;

    const button = form.querySelector("[data-record]");
    const status = form.querySelector("[data-record-status]");
    const region = document.querySelector("#result-region");

    if (status) status.textContent = "";
    if (region) region.replaceChildren();
    setInlineRepeatVisible(false);
    form.scrollIntoView({ behavior: "smooth", block: "start" });
    if (button) button.focus({ preventScroll: true });
  }

  function setInlineRepeatVisible(visible) {
    document.querySelectorAll("[data-repeat-inline]").forEach((button) => {
      button.hidden = !visible;
    });
  }

  function toggleIpa(button) {
    const scope = button.closest("[data-ipa-scope]");
    if (!scope) return;

    const willHide = scope.dataset.ipaHidden !== "true";
    scope.dataset.ipaHidden = willHide ? "true" : "false";
    button.setAttribute("aria-pressed", willHide ? "true" : "false");
    button.textContent = willHide ? "Show IPA" : "Hide IPA";
  }

  function togglePromptIpa(button) {
    const shell = button.closest("[data-prompt-ipa]");
    if (!shell) return;

    const willShow = shell.getAttribute("data-ipa-visible") !== "true";
    shell.setAttribute("data-ipa-visible", willShow ? "true" : "false");
    button.setAttribute("aria-pressed", willShow ? "true" : "false");
    button.textContent = willShow ? "Hide IPA" : "Show IPA";
  }

  function toggleConnectedSpeech(button) {
    const shell = button.closest("[data-prompt-ipa]");
    if (!shell) return;

    const willShow = shell.getAttribute("data-connected-visible") !== "true";
    shell.setAttribute("data-connected-visible", willShow ? "true" : "false");
    button.setAttribute("aria-pressed", willShow ? "true" : "false");
    button.textContent = willShow ? "Hide connected speech tips" : "Show connected speech tips";
  }

  document.addEventListener("click", (event) => {
    const repeat = event.target.closest("[data-repeat-prompt]");
    if (repeat) {
      event.preventDefault();
      repeatCurrentPrompt();
      return;
    }

    const toggle = event.target.closest("[data-toggle-ipa]");
    if (toggle) {
      event.preventDefault();
      toggleIpa(toggle);
      return;
    }

    const promptToggle = event.target.closest("[data-toggle-prompt-ipa]");
    if (promptToggle) {
      event.preventDefault();
      togglePromptIpa(promptToggle);
      return;
    }

    const connectedToggle = event.target.closest("[data-toggle-connected-speech]");
    if (connectedToggle) {
      event.preventDefault();
      toggleConnectedSpeech(connectedToggle);
    }
  });

  document.addEventListener("prosody:analysis-rendered", () => {
    setInlineRepeatVisible(true);
  });
})();

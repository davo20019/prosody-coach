// MediaRecorder wrapper for Practice, Train, and Drill run forms.
// Uploads the recorded blob via fetch and replaces #result-region with the response.
(function () {
  const MIN_RECORDING_MS = 1000;

  function regionEl() { return document.querySelector("#result-region"); }

  function showBanner(text, className) {
    const region = regionEl();
    if (!region) return;
    const div = document.createElement("div");
    div.classList.add(className);
    div.textContent = text;
    region.replaceChildren(div);
  }

  function showError(text) { showBanner(text, "error-banner"); }

  async function swapRegionFromHtml(htmlText) {
    const region = regionEl();
    if (!region) return;
    const doc = new DOMParser().parseFromString(htmlText, "text/html");
    // Move parsed children into the region (DOMParser already escaped per the
    // server's Jinja-rendered HTML — Jinja autoescape applies to data values).
    region.replaceChildren(...Array.from(doc.body.childNodes));
  }

  function pickMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
    ];
    return candidates.find((m) => MediaRecorder.isTypeSupported(m)) || "";
  }

  function attach(form) {
    const button = form.querySelector("[data-record]");
    const status = form.querySelector("[data-record-status]");
    if (!button) return;

    let recorder = null;
    let chunks = null;
    let stream = null;
    let startedAt = 0;

    let tickTimer = null;
    function fmt(ms) {
      const s = Math.floor(ms / 1000);
      return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    }
    function setStatus(text, isRecording) {
      if (status) status.textContent = text;
      button.textContent = isRecording ? "Stop" : "Record";
      if (isRecording) {
        button.dataset.recording = "true";
        if (tickTimer) clearInterval(tickTimer);
        tickTimer = setInterval(() => {
          if (status) status.textContent = `Recording · ${fmt(Date.now() - startedAt)}`;
        }, 250);
      } else {
        delete button.dataset.recording;
        if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
      }
    }

    async function uploadBlob(blob) {
      const fd = new FormData(form);
      fd.append("audio", blob, "recording.webm");
      setStatus("Analyzing...", false);
      try {
        const res = await fetch(form.action, { method: "POST", body: fd });
        const text = await res.text();
        if (!res.ok) {
          showError(`Server error (${res.status}). See console for details.`);
          console.error(text);
          return;
        }
        await swapRegionFromHtml(text);
      } catch (err) {
        showError("Network error during upload. Is the server still running?");
        console.error(err);
      }
    }

    button.addEventListener("click", async (e) => {
      e.preventDefault();

      // STOP path
      if (recorder) {
        const elapsed = Date.now() - startedAt;
        recorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          if (elapsed < MIN_RECORDING_MS) {
            showError("Recording too short. Hold the mic for at least 1 second.");
            recorder = null;
            setStatus("", false);
            return;
          }
          const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
          recorder = null;
          uploadBlob(blob);
        };
        recorder.stop();
        return;
      }

      // START path
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { sampleRate: 16000, channelCount: 1 },
        });
      } catch (err) {
        showError("Browser blocked microphone access. Click the lock icon in the address bar to allow it.");
        return;
      }
      const mime = pickMimeType();
      if (!mime) {
        showError("This browser does not support webm/opus recording. Try Chrome or Firefox.");
        return;
      }
      chunks = [];
      recorder = new MediaRecorder(stream, { mimeType: mime });
      recorder.ondataavailable = (ev) => { if (ev.data.size > 0) chunks.push(ev.data); };
      recorder.start();
      startedAt = Date.now();
      setStatus("Recording...", true);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("form[data-recorder]").forEach(attach);
  });
})();

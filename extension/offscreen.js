// Offscreen document — the only place in MV3 where a service worker can
// reach the clipboard. Listens for read/write messages from background.js.

function readClipboard() {
  const ta = document.createElement("textarea");
  document.body.appendChild(ta);
  ta.focus();
  document.execCommand("paste");
  const value = ta.value;
  ta.remove();
  return value;
}

function writeClipboard(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  ta.remove();
  return ok;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.target !== "offscreen") return;
  try {
    if (msg.type === "read") sendResponse(readClipboard());
    else if (msg.type === "write") sendResponse(writeClipboard(msg.text));
  } catch (e) {
    sendResponse(null);
  }
});

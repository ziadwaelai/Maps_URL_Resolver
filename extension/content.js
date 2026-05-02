// Content script — runs on Google Maps domains. When the user copies a Maps
// URL on the page, ask the service worker to resolve it automatically.

const MAP_URL_RE = /^https?:\/\/(?:www\.|maps\.)?google\.[a-z.]+\/maps|^https?:\/\/maps\.app\.goo\.gl|^https?:\/\/goo\.gl\/maps/i;

document.addEventListener(
  "copy",
  () => {
    const text = window.getSelection()?.toString().trim();
    if (text && MAP_URL_RE.test(text)) {
      chrome.runtime.sendMessage({ type: "autoResolve", url: text });
    }
  },
  true
);

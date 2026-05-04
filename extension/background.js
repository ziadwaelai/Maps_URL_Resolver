// Service worker — orchestrates clipboard reads/writes and backend calls.

const DEFAULT_BACKEND = "http://localhost:8001";
const MAP_URL_RE = /^https?:\/\/(?:www\.|maps\.)?google\.[a-z.]+\/maps|^https?:\/\/maps\.app\.goo\.gl|^https?:\/\/goo\.gl\/maps/i;
const BADGE_TIMEOUT = 2000;

// Default field-id → response-field map for portal autofill. Stored in
// chrome.storage.sync so the user can edit it from the popup if the portal
// regenerates IDs (these `:r12X:` ones are React useId() values).
const DEFAULT_FIELD_MAP = {
  ":r12q:": "lat",
  ":r12s:": "lng",
  ":r12i:": "phone",
  ":r12c:": "name",      // English name
  ":r12e:": "name_ar",   // Arabic name (backend doesn't yet return this)
};

const state = { badgeTimer: null };

async function getSettings() {
  return chrome.storage.sync.get({
    enabled: true,
    backend: DEFAULT_BACKEND,
    fieldMap: DEFAULT_FIELD_MAP,
  });
}

async function setLastResult(result) {
  await chrome.storage.local.set({ lastResult: { ...result, ts: Date.now() } });
}

// ---- Offscreen document for clipboard access (Manifest V3 quirk) ----------
async function ensureOffscreen() {
  const existing = await chrome.offscreen.hasDocument?.();
  if (existing) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["CLIPBOARD"],
    justification: "Read Google Maps URLs from and write coordinates to the clipboard",
  });
}

async function clipboardRead() {
  await ensureOffscreen();
  return chrome.runtime.sendMessage({ target: "offscreen", type: "read" });
}

async function clipboardWrite(text) {
  await ensureOffscreen();
  return chrome.runtime.sendMessage({ target: "offscreen", type: "write", text });
}

// ---- Status feedback ------------------------------------------------------
function setBadge(text, color = "#3b82f6", timeoutMs = BADGE_TIMEOUT) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  if (state.badgeTimer) clearTimeout(state.badgeTimer);
  if (timeoutMs > 0) {
    state.badgeTimer = setTimeout(() => chrome.action.setBadgeText({ text: "" }), timeoutMs);
  }
}

function osNotify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title,
    message,
  });
}

// Inject a polished bottom-right toast into the user's active tab. Falls back
// to a system notification on restricted pages (chrome://, web store, etc.).
async function inPageToast(payload) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:/.test(tab.url || "")) throw new Error("no http tab");
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: renderToast,
      args: [payload],
    });
  } catch {
    osNotify(payload.title, payload.subtitle || payload.coords || "");
  }
}

// Runs in the page context — must be self-contained, no closure refs.
function renderToast(p) {
  const ID = "__murl_toast__";
  document.getElementById(ID)?.remove();

  const wrap = document.createElement("div");
  wrap.id = ID;
  const icon = p.kind === "error" ? "✕" : "✓";
  const accent =
    p.kind === "error"
      ? "linear-gradient(135deg, #f85149, #d29922)"
      : "linear-gradient(135deg, #58a6ff, #c084fc)";
  const titleColor = p.kind === "error" ? "#f85149" : "#3fb950";

  wrap.innerHTML =
    '<div class="t-icon">' + icon + "</div>" +
    '<div class="t-body">' +
      '<div class="t-title"></div>' +
      (p.name ? '<div class="t-name"></div>' : "") +
      (p.coords ? '<div class="t-coords"></div>' : "") +
      (p.subtitle && !p.coords ? '<div class="t-coords"></div>' : "") +
    "</div>" +
    '<button class="t-close" aria-label="Close">×</button>';

  wrap.querySelector(".t-title").textContent = p.title;
  if (p.name) wrap.querySelector(".t-name").textContent = p.name;
  if (p.coords) wrap.querySelector(".t-coords").textContent = p.coords;
  if (p.subtitle && !p.coords) wrap.querySelector(".t-coords").textContent = p.subtitle;

  const styleId = ID + "-style";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent =
      "#" + ID + "{position:fixed;bottom:24px;right:24px;z-index:2147483647;" +
      "background:rgba(13,17,23,0.96);backdrop-filter:blur(14px);" +
      "color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" +
      "font-size:13px;line-height:1.4;padding:14px 16px;border-radius:12px;" +
      "box-shadow:0 12px 32px rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.08);" +
      "display:flex;align-items:flex-start;gap:12px;min-width:240px;max-width:360px;" +
      "animation:__murl_in .3s cubic-bezier(.16,1,.3,1)}" +
      "@keyframes __murl_in{from{opacity:0;transform:translateY(20px) scale(.96)}" +
      "to{opacity:1;transform:translateY(0) scale(1)}}" +
      "@keyframes __murl_out{to{opacity:0;transform:translateY(20px) scale(.96)}}" +
      "#" + ID + ".out{animation:__murl_out .25s ease forwards}" +
      "#" + ID + " .t-icon{width:28px;height:28px;border-radius:50%;display:flex;" +
      "align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:14px;flex-shrink:0;" +
      "background:__ACCENT__}" +
      "#" + ID + " .t-body{flex:1;min-width:0}" +
      "#" + ID + " .t-title{font-weight:600;font-size:12px;color:__TC__;margin-bottom:2px}" +
      "#" + ID + " .t-name{font-weight:500;color:#e6edf3;margin-bottom:2px;" +
      "white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
      "#" + ID + " .t-coords{color:#8b949e;font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11px;" +
      "white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
      "#" + ID + " .t-close{background:transparent;border:0;color:#8b949e;cursor:pointer;" +
      "font-size:18px;line-height:1;padding:0 0 0 4px;margin-top:-2px}" +
      "#" + ID + " .t-close:hover{color:#e6edf3}";
    style.textContent = style.textContent
      .replace("__ACCENT__", accent)
      .replace("__TC__", titleColor);
    document.head.appendChild(style);
  }

  document.body.appendChild(wrap);

  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    wrap.classList.add("out");
    setTimeout(() => wrap.remove(), 280);
  };
  wrap.querySelector(".t-close").addEventListener("click", dismiss);
  setTimeout(dismiss, p.kind === "error" ? 5000 : 3500);
}

// ---- Autofill -------------------------------------------------------------
async function tryAutofill(data, fieldMap) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !/^https?:/.test(tab.url || "")) return 0;
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: fillFormFields,
      args: [data, fieldMap],
    });
    return result || 0;
  } catch {
    return 0;
  }
}

// Runs in the active tab's page context. Sets values on inputs in a way that
// React notices (use the prototype's native setter, then dispatch input event).
function fillFormFields(data, fieldMap) {
  const setReactValue = (el, raw) => {
    if (raw == null || raw === "") return false;
    const value = String(raw);
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    if (setter) setter.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };
  let count = 0;
  for (const [id, key] of Object.entries(fieldMap)) {
    const value = data[key];
    if (value == null || value === "") continue;
    const el = document.querySelector(`[id="${CSS.escape(id)}"]`);
    if (el && setReactValue(el, value)) count++;
  }
  return count;
}

// ---- Core resolve flow ----------------------------------------------------
async function resolve({ url, source = "manual" } = {}) {
  const { enabled, backend, fieldMap } = await getSettings();
  if (!enabled) {
    if (source === "manual") {
      inPageToast({ kind: "error", title: "Resolver is off", subtitle: "Toggle it on from the popup." });
    }
    return null;
  }

  let data = null;

  // 1. If clipboard has a fresh Maps URL, resolve it via the backend.
  if (!url) {
    try { url = (await clipboardRead())?.trim(); }
    catch (e) {
      inPageToast({ kind: "error", title: "Clipboard error", subtitle: e.message || String(e) });
      return null;
    }
  }
  if (url && MAP_URL_RE.test(url)) {
    setBadge("…", "#3b82f6", 0);
    try {
      const apiUrl = `${backend.replace(/\/+$/, "")}/extract?url=${encodeURIComponent(url)}`;
      const r = await fetch(apiUrl);
      if (!r.ok) throw new Error(`API ${r.status}`);
      data = await r.json();
      if (data.lat == null || data.lng == null) {
        setBadge("!", "#ef4444");
        inPageToast({ kind: "error", title: "No coordinates", subtitle: "Backend returned no lat/lng." });
        return null;
      }
      await clipboardWrite(`${data.lat}, ${data.lng}`);
      await setLastResult(data);
    } catch (e) {
      setBadge("!", "#ef4444");
      inPageToast({ kind: "error", title: "Resolver error", subtitle: e.message || String(e) });
      return null;
    }
  } else {
    // 2. No fresh URL — fall back to the last cached result so autofill
    //    still works when the user just wants to fill the same place again.
    const local = await chrome.storage.local.get(["lastResult"]);
    data = local.lastResult || null;
    if (!data) {
      if (source === "manual") {
        inPageToast({
          kind: "error",
          title: "Nothing to fill",
          subtitle: "Copy a Google Maps URL first.",
        });
      }
      return null;
    }
  }

  // 3. Try autofilling form fields on the active tab.
  const filled = await tryAutofill(data, fieldMap);
  setBadge("✓", "#10b981");

  const coords = `${data.lat}, ${data.lng}`;
  if (filled > 0) {
    inPageToast({
      kind: "success",
      title: `Autofilled ${filled} field${filled > 1 ? "s" : ""}`,
      name: data.name || undefined,
      coords,
    });
  } else {
    inPageToast({
      kind: "success",
      title: "Copied — ready to paste",
      name: data.name || undefined,
      coords,
    });
  }
  return data;
}

// ---- Triggers -------------------------------------------------------------
chrome.commands.onCommand.addListener((cmd) => {
  if (cmd === "resolve-clipboard") resolve({ source: "hotkey" });
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "resolve") {
    resolve({ source: "popup" }).then((d) => sendResponse({ ok: !!d, data: d }));
    return true;
  }
  if (msg?.type === "autoResolve" && msg.url) {
    // Triggered from content script when user copies a URL on a Maps page.
    resolve({ url: msg.url, source: "auto" });
    return false;
  }
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ enabled: true, backend: DEFAULT_BACKEND }, () => {});
});

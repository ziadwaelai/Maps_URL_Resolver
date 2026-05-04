const $ = (id) => document.getElementById(id);
const els = {
  enabled:      $("enabled"),
  backend:      $("backend"),
  hotkey:       $("hotkey"),
  hotkeyFoot:   $("hotkey-foot"),
  changeHotkey: $("change-hotkey"),
  statusDot:    $("status-dot"),
  lastSection:  $("last-section"),
  lastCoords:   $("last-coords"),
  lastMeta:     $("last-meta"),
  copyCoords:   $("copy-coords"),
  resolveNow:   $("resolve-now"),
  fieldMap:     $("field-map"),
  mapStatus:    $("map-status"),
  resetMap:     $("reset-map"),
};

const DEFAULT_FIELD_MAP = {
  ":r12q:": "lat",
  ":r12s:": "lng",
  ":r12i:": "phone",
  ":r12c:": "name",
  ":r12e:": "name_ar",
};

async function load() {
  const sync = await chrome.storage.sync.get({
    enabled: true,
    backend: "http://localhost:8001",
    fieldMap: DEFAULT_FIELD_MAP,
  });
  const local = await chrome.storage.local.get(["lastResult"]);

  els.enabled.checked = sync.enabled;
  els.backend.value = sync.backend;
  els.fieldMap.value = JSON.stringify(sync.fieldMap, null, 2);
  els.statusDot.classList.toggle("off", !sync.enabled);

  const r = local.lastResult;
  if (r && r.lat != null) {
    els.lastSection.hidden = false;
    els.lastCoords.textContent = `${r.lat}, ${r.lng}`;
    const meta = [r.name, r.category].filter(Boolean).join(" · ");
    els.lastMeta.textContent = meta;
  }

  const cmds = await chrome.commands.getAll();
  const cmd = cmds.find((c) => c.name === "resolve-clipboard");
  const shortcut = (cmd?.shortcut || "Alt + Shift + M").replace(/(\w)/g, (m) => m);
  els.hotkey.textContent = shortcut || "(unset)";
  els.hotkeyFoot.textContent = (cmd?.shortcut || "Alt+Shift+M").replace(/\s/g, "");
}

els.enabled.addEventListener("change", async (e) => {
  await chrome.storage.sync.set({ enabled: e.target.checked });
  els.statusDot.classList.toggle("off", !e.target.checked);
});

els.backend.addEventListener("change", (e) => {
  chrome.storage.sync.set({ backend: e.target.value.trim() });
});

function showMapStatus(text, kind = "") {
  els.mapStatus.textContent = text;
  els.mapStatus.className = "map-meta " + kind;
}

els.fieldMap.addEventListener("input", () => {
  try {
    const parsed = JSON.parse(els.fieldMap.value);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      chrome.storage.sync.set({ fieldMap: parsed });
      showMapStatus("Saved.", "ok");
    } else {
      showMapStatus("Must be a JSON object.", "error");
    }
  } catch {
    showMapStatus("Invalid JSON.", "error");
  }
});

els.resetMap.addEventListener("click", async () => {
  await chrome.storage.sync.set({ fieldMap: DEFAULT_FIELD_MAP });
  els.fieldMap.value = JSON.stringify(DEFAULT_FIELD_MAP, null, 2);
  showMapStatus("Reset to defaults.", "ok");
});

els.changeHotkey.addEventListener("click", (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "chrome://extensions/shortcuts" });
});

els.copyCoords.addEventListener("click", async () => {
  const text = els.lastCoords.textContent;
  try {
    await navigator.clipboard.writeText(text);
    els.copyCoords.classList.add("copied");
    setTimeout(() => els.copyCoords.classList.remove("copied"), 1200);
  } catch {}
});

els.resolveNow.addEventListener("click", async () => {
  els.resolveNow.disabled = true;
  els.resolveNow.textContent = "Resolving…";
  try {
    await chrome.runtime.sendMessage({ type: "resolve" });
  } finally {
    setTimeout(() => {
      els.resolveNow.disabled = false;
      els.resolveNow.textContent = "Resolve clipboard now";
      load();
    }, 1500);
  }
});

load();

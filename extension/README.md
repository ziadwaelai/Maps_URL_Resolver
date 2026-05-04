# Maps URL Resolver — Chrome Extension

Companion extension for the [Maps URL Resolver](../README.md) backend. Copy a Google Maps URL and the extension swaps it in your clipboard for `lat, lng` so your next paste is the coordinates.

## How it works

| Trigger | Where | What happens |
|---|---|---|
| **Copy on a Google Maps page** | `google.com/maps`, `maps.app.goo.gl`, `goo.gl/maps` | Auto-detected by the content script — backend is called immediately. |
| **Hotkey** (default `Alt+Shift+M`) | Anywhere — Slack, mobile share copy, terminal, your portal, etc. | Reads clipboard, calls backend, writes `lat, lng` back to clipboard, **and tries to autofill** form fields on the active tab. |
| **"Resolve clipboard now" button** | Extension popup | Same as the hotkey, but with a click. |

After a successful resolve:
1. The clipboard is overwritten with `lat, lng` (e.g. `24.7628448, 46.6238678`).
2. **Form fields on the active tab are autofilled** if their IDs match the field map (configurable in the popup).
3. A bottom-right toast on the active tab confirms the action — text changes between *"Copied — ready to paste"* and *"Autofilled N fields"* depending on whether any inputs matched.

If the clipboard isn't a Maps URL, the hotkey falls back to the **last cached result** so you can re-fill the same place on multiple portal pages without re-copying.

## Autofill

The popup's **Autofill field map** is a small JSON object: `{ "<input id>": "<response key>" }`. Default mapping:

| Field id            | Response key | Notes |
|---------------------|--------------|-------|
| `:r12q:`             | `lat`        | Latitude |
| `:r12s:`             | `lng`        | Longitude |
| `:r12i:`             | `phone`      | Phone with country code |
| `:r12c:`             | `name`       | English place name |
| `:r12e:`             | `name_ar`    | *Backend doesn't return this yet — see below* |

These IDs come from React's `useId()` and may regenerate when the portal updates. If autofill stops matching, open the portal page in DevTools, copy the new IDs from the inputs, and paste them into the popup's textarea — changes save automatically.

The setter uses the native `HTMLInputElement.prototype.value` setter and dispatches `input` + `change` events so React/Material UI / etc. notice the new value (the usual React form trick).

> ⚠️ **Arabic name (`name_ar`) isn't returned by the backend yet.** Adding it requires a second headless render with `hl=ar`. Tell me if you want it and I'll wire it up — it'll add ~5 s per resolve unless we do the two renders in parallel.

## Install (developer mode)

1. Run the backend somewhere reachable (e.g. `docker compose up -d --build` from the project root).
2. Open `chrome://extensions/` → enable **Developer mode**.
3. Click **Load unpacked** → select this `extension/` folder.
4. Click the puzzle icon → pin the extension for easy access.
5. Open the popup → set **Backend URL** to wherever your API is reachable from your machine (default `http://localhost:8001`).

## Settings (popup)

- **Enable toggle** — pause the extension without removing it.
- **Backend URL** — points at the API. Persists across sessions.
- **Hotkey** — click "Change hotkey" to remap it via Chrome's shortcut UI.

## Files

```
extension/
├── manifest.json    # MV3 manifest, permissions, hotkey, content-script matches
├── background.js    # Service worker — orchestrates clipboard + API calls
├── offscreen.html   # Required wrapper for clipboard access in MV3
├── offscreen.js     # Reads/writes the clipboard via execCommand
├── content.js       # Auto-trigger when a Maps URL is copied on Maps domains
├── popup.html       # Dark-mode UI
├── popup.css
├── popup.js
└── icons/           # 16×16, 48×48, 128×128 PNGs (add your own)
```

## Adding icons

Drop `icon16.png`, `icon48.png`, and `icon128.png` into `extension/icons/`, then add to `manifest.json`:

```json
"icons": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" },
"action": { "default_icon": { "16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png" }, "default_popup": "popup.html" }
```

(Without icons Chrome falls back to a default puzzle-piece silhouette — fine for local testing.)

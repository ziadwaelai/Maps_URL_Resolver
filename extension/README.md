# Maps URL Resolver — Chrome Extension

Companion extension for the [Maps URL Resolver](../README.md) backend. Copy a Google Maps URL and the extension swaps it in your clipboard for `lat, lng` so your next paste is the coordinates.

## How it works

| Trigger | Where | What happens |
|---|---|---|
| **Copy on a Google Maps page** | `google.com/maps`, `maps.app.goo.gl`, `goo.gl/maps` | Auto-detected by the content script — backend is called immediately. |
| **Hotkey** (default `Alt+Shift+M`) | Anywhere — Slack, mobile share copy, terminal, etc. | Reads the clipboard, validates it's a Maps URL, calls the backend. |
| **"Resolve clipboard now" button** | Extension popup | Same as the hotkey, but with a click. |

After a successful resolve:
1. The clipboard is overwritten with `lat, lng` (e.g. `24.7628448, 46.6238678`).
2. A system notification confirms the value.
3. The popup remembers the last result with name + category.

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

"""Google Maps URL → full place details, exposed as a FastAPI endpoint."""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

# Coord patterns ordered by accuracy: pin, viewport, query string.
URL_PATTERNS = (
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
    r"/@(-?\d+\.\d+),(-?\d+\.\d+)",
    r"[?&](?:q|ll)=(-?\d+\.\d+),(-?\d+\.\d+)",
)


class PlaceInfo(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    hours: Optional[Dict[str, str]] = None


# Single JS pass that pulls every field from the rendered place panel.
# Uses aria-label / data-item-id which are the most stable identifiers Google exposes.
EXTRACT_JS = r"""() => {
    const text = (sel, root = document) => {
        const el = root.querySelector(sel);
        return el ? el.textContent.trim() : null;
    };
    const attr = (sel, a, root = document) => {
        const el = root.querySelector(sel);
        return el ? el.getAttribute(a) : null;
    };
    const stripPrefix = (s, p) => (s && s.startsWith(p)) ? s.slice(p.length).replace(/^[\s,]+/, '').trim() : s;

    const name = text('h1');

    const addrRaw = attr('[data-item-id="address"]', 'aria-label');
    const address = stripPrefix(addrRaw, 'Address:');

    const phoneId = attr('button[data-item-id^="phone:tel:"]', 'data-item-id');
    const phone = phoneId ? phoneId.replace('phone:tel:', '').trim() : null;

    const website = attr('a[data-item-id="authority"]', 'href');

    const category = text('button[jsaction*="category"]');

    let rating = null, reviews = null;
    const ratingEl = document.querySelector('[role="img"][aria-label*=" stars"]');
    if (ratingEl) {
        const lbl = ratingEl.getAttribute('aria-label') || '';
        const m = lbl.match(/([\d.]+)\s*stars/);
        if (m) rating = parseFloat(m[1]);
    }
    const reviewBtn = document.querySelector('button[aria-label*="reviews"], button[jsaction*="reviewChart"]');
    if (reviewBtn) {
        const t = (reviewBtn.getAttribute('aria-label') || reviewBtn.textContent || '').replace(/[,()\s]/g, '');
        const rm = t.match(/(\d{1,7})/);
        if (rm) reviews = parseInt(rm[1], 10);
    }

    // Hours: try specific selectors first, then scan every table for one whose
    // first column looks like weekday names (Monday/Tuesday/… or Mon/Tue/…).
    let hours = {};
    const dayRe = /^(Sun|Mon|Tue|Wed|Thu|Fri|Sat)/i;
    const collectFromTable = (t) => {
        const out = {};
        for (const row of t.querySelectorAll('tr')) {
            const cells = row.querySelectorAll('td, th');
            if (cells.length >= 2) {
                const day = cells[0].textContent.trim();
                const time = cells[1].textContent.trim().replace(/\s+/g, ' ');
                if (day && time && day.length < 20 && dayRe.test(day)) out[day] = time;
            }
        }
        return out;
    };
    const targeted = document.querySelector(
        '[aria-label*="Hours"] table, [data-item-id="oh"] table, table.eK4R0e'
    );
    if (targeted) hours = collectFromTable(targeted);
    if (!Object.keys(hours).length) {
        for (const t of document.querySelectorAll('table')) {
            const candidate = collectFromTable(t);
            if (Object.keys(candidate).length >= 5) { hours = candidate; break; }
        }
    }

    return {
        name, address, phone, website, category, rating, reviews,
        hours: Object.keys(hours).length ? hours : null,
    };
}"""


def _match_coords(text: str) -> tuple[Optional[float], Optional[float]]:
    for pat in URL_PATTERNS:
        m = re.search(pat, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


async def _expand_short_link(url: str) -> str:
    """Resolve goo.gl / maps.app.goo.gl to their long form via a quick HTTP redirect."""
    if "goo.gl" not in url and "maps.app" not in url:
        return url
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            r = await client.get(url)
            return str(r.url)
    except httpx.HTTPError:
        return url


async def _resolve_with_browser(url: str) -> PlaceInfo:
    page = await app.state.context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Wait until Google rewrites the URL with @lat,lng so coords are settled.
        await page.wait_for_function(
            "() => /@-?\\d+\\.\\d+,-?\\d+\\.\\d+/.test(location.href)"
            " || /!3d-?\\d+\\.\\d+!4d-?\\d+\\.\\d+/.test(location.href)",
            timeout=15000,
        )
        # Best-effort: wait briefly for the place panel so the side details are populated.
        try:
            await page.wait_for_selector('[data-item-id="address"], h1', timeout=8000)
        except Exception:
            pass
        data = await page.evaluate(EXTRACT_JS) or {}
        lat, lng = _match_coords(page.url)
        return PlaceInfo(lat=lat, lng=lng, **{k: v for k, v in data.items() if v is not None})
    except Exception as e:
        print(f"[browser] FAILED: {type(e).__name__}: {e}", flush=True)
        return PlaceInfo()
    finally:
        await page.close()


async def extract(url: str) -> PlaceInfo:
    """Resolve a Google Maps URL into full place details. Any field may be None."""
    url = await _expand_short_link(url)
    # Force English UI so DOM labels (Address:, X stars, …) are predictable.
    if "hl=" not in url:
        url += ("&" if "?" in url else "?") + "hl=en"
    return await _resolve_with_browser(url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    playwright = await async_playwright().start()
    app.state.browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    # Pre-set Google consent cookies so EU/server geos skip the consent.google.com wall.
    app.state.context = await app.state.browser.new_context(
        user_agent=USER_AGENT,
        locale="en-US",
        timezone_id="Asia/Riyadh",
    )
    await app.state.context.add_cookies([
        {"name": "CONSENT", "value": "YES+cb.20210720-07-p0.en+FX+410",
         "domain": ".google.com", "path": "/"},
        {"name": "SOCS", "value": "CAISHAgBEhIaAB",
         "domain": ".google.com", "path": "/"},
    ])
    try:
        yield
    finally:
        await app.state.context.close()
        await app.state.browser.close()
        await playwright.stop()


app = FastAPI(title="Maps URL Resolver", lifespan=lifespan)


@app.get("/extract", response_model=PlaceInfo)
async def extract_endpoint(url: str = Query(..., description="Google Maps URL")):
    return await extract(url)


INDEX_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

"""Google Maps URL → coordinates and phone, exposed as a FastAPI endpoint."""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, Query
from playwright.async_api import async_playwright
from pydantic import BaseModel

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

# Ordered by accuracy: pin (!3d!4d), viewport (@), then ?q=/?ll= query.
URL_PATTERNS = (
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
    r"/@(-?\d+\.\d+),(-?\d+\.\d+)",
    r"[?&](?:q|ll)=(-?\d+\.\d+),(-?\d+\.\d+)",
)
HTML_PATTERNS = (
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
    r'"latitude"\s*:\s*(-?\d+\.\d+)\s*,\s*"longitude"\s*:\s*(-?\d+\.\d+)',
    r"/@(-?\d+\.\d+),(-?\d+\.\d+)",
)


class PlaceInfo(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None
    phone: Optional[str] = None


def _match(text: str, patterns) -> tuple[Optional[float], Optional[float]]:
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


async def _resolve_with_browser(url: str) -> PlaceInfo:
    page = await app.state.browser.new_page(user_agent=USER_AGENT)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Wait until Google rewrites the URL with @lat,lng or !3d!4d.
        await page.wait_for_function(
            "() => /@-?\\d+\\.\\d+,-?\\d+\\.\\d+/.test(location.href)"
            " || /!3d-?\\d+\\.\\d+!4d-?\\d+\\.\\d+/.test(location.href)",
            timeout=15000,
        )
        lat, lng = _match(page.url, URL_PATTERNS)
        phone = await _extract_phone(page)
        return PlaceInfo(lat=lat, lng=lng, phone=phone)
    except Exception:
        return PlaceInfo()
    finally:
        await page.close()


async def _extract_phone(page) -> Optional[str]:
    el = await page.query_selector('button[data-item-id^="phone:tel:"]')
    if not el:
        return None
    value = (await el.get_attribute("data-item-id")) or ""
    return value.replace("phone:tel:", "").strip() or None


async def extract(url: str) -> PlaceInfo:
    """Resolve a Google Maps URL into lat / lng / phone. Any field may be None."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            if "goo.gl" in url or "maps.app" in url:
                r = await client.get(url)
                url = str(r.url)

            lat, lng = _match(url, URL_PATTERNS)
            if lat is not None:
                return PlaceInfo(lat=lat, lng=lng)

            if "place_id:" in url:
                return await _resolve_with_browser(url)

            r = await client.get(url)
            lat, lng = _match(str(r.url), URL_PATTERNS)
            if lat is None:
                lat, lng = _match(r.text, HTML_PATTERNS)
            return PlaceInfo(lat=lat, lng=lng)
    except httpx.HTTPError:
        return PlaceInfo()


@asynccontextmanager
async def lifespan(app: FastAPI):
    playwright = await async_playwright().start()
    app.state.browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    try:
        yield
    finally:
        await app.state.browser.close()
        await playwright.stop()


app = FastAPI(title="Maps URL Resolver", lifespan=lifespan)


@app.get("/extract", response_model=PlaceInfo)
async def extract_endpoint(url: str = Query(..., description="Google Maps URL")):
    return await extract(url)

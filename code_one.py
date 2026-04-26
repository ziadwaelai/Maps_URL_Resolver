import atexit
import re
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Patterns ordered by accuracy: pin coords first, then viewport, then query params.
URL_PATTERNS = [
    r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',          # actual pin
    r'/@(-?\d+\.\d+),(-?\d+\.\d+)',              # viewport center
    r'[?&](?:q|ll)=(-?\d+\.\d+),(-?\d+\.\d+)',  # ?q=lat,lng or ?ll=lat,lng
]

# Patterns for the HTML body returned when a URL has no coords (e.g. place_id).
HTML_PATTERNS = [
    r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',
    r'"latitude"\s*:\s*(-?\d+\.\d+)\s*,\s*"longitude"\s*:\s*(-?\d+\.\d+)',
    r'/@(-?\d+\.\d+),(-?\d+\.\d+)',
]


_browser = None
_playwright = None


def _get_browser():
    global _browser, _playwright
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=True)
        atexit.register(_shutdown_browser)
    return _browser


def _shutdown_browser():
    global _browser, _playwright
    if _browser is not None:
        try:
            _browser.close()
        finally:
            _browser = None
    if _playwright is not None:
        try:
            _playwright.stop()
        finally:
            _playwright = None


def _resolve_with_browser(url):
    page = _get_browser().new_page(user_agent=HEADERS["User-Agent"])
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Wait until Google rewrites the URL to include @lat,lng or !3d!4d.
        page.wait_for_function(
            "() => /@-?\\d+\\.\\d+,-?\\d+\\.\\d+/.test(location.href)"
            " || /!3d-?\\d+\\.\\d+!4d-?\\d+\\.\\d+/.test(location.href)",
            timeout=15000,
        )
        lat, lng = _search(page.url, URL_PATTERNS)
        phone = _extract_phone(page)
        return lat, lng, phone
    except Exception:
        return None, None, None
    finally:
        page.close()


def _extract_phone(page):
    # Google Maps stores the phone in a button attribute: data-item-id="phone:tel:+966..."
    try:
        el = page.query_selector('button[data-item-id^="phone:tel:"]')
        if el:
            value = el.get_attribute("data-item-id") or ""
            return value.replace("phone:tel:", "").strip() or None
    except Exception:
        pass
    return None


def _search(text, patterns):
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def extract_coords(url):
    try:
        # Follow short links to reveal the underlying long URL.
        if "goo.gl" in url or "maps.app" in url:
            url = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=10).url

        # Fast path: coords are already in the URL (no phone available without rendering).
        lat, lng = _search(url, URL_PATTERNS)
        if lat is not None:
            return lat, lng, None

        # place_id URLs need a real browser — Google loads coords + phone via JS.
        if "place_id:" in url:
            return _resolve_with_browser(url)

        # Generic HTTP fallback for anything else without coords in the link.
        r = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=15)
        lat, lng = _search(r.url, URL_PATTERNS)
        if lat is not None:
            return lat, lng, None
        lat, lng = _search(r.text, HTML_PATTERNS)
        return lat, lng, None
    except requests.RequestException:
        return None, None, None
 
 
# Mock input
test_urls = [
    # Starbucks - Hittin, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJUaiqmuLjLj4Rx6TNGPXTVls",
    # Starbucks - Al Manar, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJ1UlEkK2J6RUR-ZY1KyXMXMc",
    # Al Baik - Quwaizah, Jeddah
    "https://www.google.com/maps/place/?q=place_id:ChIJ71UHe73NwxUR4J9sjMlvy_0",
    # ALBAIK - Al Salamah, Jeddah
    "https://www.google.com/maps/place/?q=place_id:ChIJe6NG7AnawxURLFlNvd6h_Gk",
    # Herfy - As Sahafah, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJQQpwcgDjLj4RTSjA5XDqlSc",
    # Herfy - King Fahd, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJ_waSIv4DLz4RVXtAjrKLPws",
    # Kudu - Riyadh Park
    "https://www.google.com/maps/place/?q=place_id:ChIJvdWSZ0_jLj4RDRioTj85CK4",
    # Kudu - Al Aarid, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJxYub_J_lLj4RW9EZYDYxRpE",
    # Tamimi Markets - As Sulimaniyah, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJ2ViJ2AwDLz4RFs4iT6Tbfl8",
    # Tamimi Markets - Al Olaya, Riyadh
    "https://www.google.com/maps/place/?q=place_id:ChIJS5Y3ZjgDLz4RqsqTHpLikMY",
]
urls = test_urls    
 
for url in urls:
    lat, lng, phone = extract_coords(url)
    print(f"{lat}, {lng}, {phone}")
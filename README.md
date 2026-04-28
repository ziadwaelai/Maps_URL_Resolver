# Maps URL Resolver

A small FastAPI service that takes any Google Maps URL and returns the place's coordinates, name, address, phone, website, category, rating, and weekly hours — plus a clean dark-mode web UI with a satellite map preview.

No Google API key required.

## What it extracts

| Field      | Notes |
|------------|-------|
| `lat`, `lng` | 7-decimal precision (~1 cm) — the value Google stores in the URL pin |
| `name`       | Place name (`h1`) |
| `address`    | Full street address |
| `phone`      | Formatted with country code |
| `website`    | Official website URL when listed |
| `category`   | E.g. `Coffee shop`, `Supermarket` |
| `rating`     | 1.0 – 5.0 |
| `reviews`    | Total review count when available |
| `hours`      | `{ "Monday": "8 AM–10 PM", … }` |

Any field may be `null` if Google doesn't expose it for that place.

## Supported URL formats

- Long share links with `!3d!4d` pin coordinates
- `@lat,lng` viewport URLs
- `?q=lat,lng` / `?ll=lat,lng` query params
- `goo.gl/maps` and `maps.app.goo.gl` short links
- `place_id:…` URLs (resolved via headless Chromium)

## API

```
GET /extract?url=<google-maps-url>
```

Example response:

```json
{
  "lat": 24.8468784,
  "lng": 46.6044022,
  "name": "Tamimi Markets",
  "address": "King Fahd Rd, Al Olaya, Riyadh, Saudi Arabia",
  "phone": "+966 11 …",
  "website": "https://tamimimarkets.com/…",
  "category": "Supermarket",
  "rating": 4.3,
  "reviews": 1234,
  "hours": { "Monday": "8 AM–11 PM", "Tuesday": "8 AM–11 PM", "…": "…" }
}
```

Interactive Swagger docs live at `/docs`.

## Web UI

Open the root URL (`/`) in a browser for a one-page dark-mode UI: paste a Google Maps URL, get the extracted fields, see the location on a satellite-view map (Esri World Imagery), and copy the coordinates with one click.

## Run with Docker (recommended)

```bash
docker compose up -d --build
```

Service listens on `http://localhost:8001`.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn server:app --host 0.0.0.0 --port 8000
```

## How it works

1. Short links are resolved with a quick HTTP redirect.
2. The URL is opened in a headless Chromium (Playwright) instance with English locale and pre-set Google consent cookies — so EU-hosted servers don't get blocked by `consent.google.com`.
3. Once the URL stabilises with `@lat,lng`, a single JS pass reads every place-panel field via stable `aria-label` and `data-item-id` selectors.
4. Coordinates also come from the URL string for accuracy.

The browser is launched once at startup and reused across requests via Playwright's `lifespan`.

## Notes

- **Coordinate precision.** 7 decimals = ~1 cm, which is the maximum useful precision (and what Google's own paid Geocoding API returns). The 14-decimal numbers shown when right-clicking on a Google Map are floating-point artifacts of pixel-to-coordinate math, not measurement precision — so this service does not attempt to reproduce them.
- **Hours.** Google sometimes serves a stripped-down place panel to headless sessions, in which case only today's hours may be available even though the place has a full weekly schedule.
- **Geo redirects.** When run from a server outside the place's country, Google may load the panel in the server's locale; the service forces `hl=en` to keep DOM labels predictable.

## Tech stack

- **FastAPI** + **Uvicorn** — HTTP server
- **Playwright (async, Chromium)** — page rendering for `place_id:` URLs and DOM extraction
- **httpx** — short-link redirect expansion
- **Leaflet** + **Esri World Imagery** — satellite map in the web UI

## License

MIT

# Maps URL Resolver

A FastAPI service that extracts coordinates and phone numbers from Google Maps URLs.

## Supported URL formats

- Long share links with `!3d!4d` pin coordinates
- `@lat,lng` viewport URLs
- `?q=lat,lng` / `?ll=lat,lng` query params
- `goo.gl/maps` and `maps.app.goo.gl` short links
- `place_id:...` URLs (resolved via headless Chromium)

## API

`GET /extract?url=<google-maps-url>`

```json
{
  "lat": 24.8468784,
  "lng": 46.6044022,
  "phone": "+966 ..."
}
```

Any field may be `null` if not found. Interactive docs at `/docs`.

## Run locally

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Run with Docker

```bash
docker compose up -d --build
```

Service listens on port `8000`.

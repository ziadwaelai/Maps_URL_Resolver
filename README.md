---
title: Maps URL Resolver
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# Maps URL Resolver

FastAPI service that resolves Google Maps URLs into `lat`, `lng`, and `phone`.

## Endpoint

`GET /extract?url=<google-maps-url>`

Response:

```json
{ "lat": 24.8468784, "lng": 46.6044022, "phone": "+966 ..." }
```
# TLS 1.3 at the reverse proxy (Step 70)

Care Plus Django/uvicorn speaks **plain HTTP** inside the private network.
TLS 1.3 is terminated at Nginx, Caddy, or a cloud load balancer in front of
the API and WebSocket endpoints.

## Required proxy behaviour

1. Listen on `443` with a certificate that supports **TLS 1.3** (disable TLS 1.0/1.1).
2. Proxy to the app: `http://backend:8000` (compose service name).
3. Forward scheme so Django can set secure cookies / HSTS correctly:

   ```nginx
   proxy_set_header Host $host;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   ```

4. WebSockets (`/ws/…`):

   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```

5. Do **not** expose uvicorn `:8000` on the public internet.

## Django settings (already wired)

With `DJANGO_SETTINGS_MODULE=careplus.settings.prod`:

- `SECURE_SSL_REDIRECT=True`
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- HSTS (1 year, includeSubDomains, preload)
- Secure session/CSRF cookies

## CORS / CSRF

Set explicit origins in production:

```bash
CORS_ALLOWED_ORIGINS=https://app.careplus.lk
CSRF_TRUSTED_ORIGINS=https://app.careplus.lk
FRONTEND_BASE_URL=https://app.careplus.lk
```

If `CORS_ALLOWED_ORIGINS` is empty in prod, Django falls back to `FRONTEND_BASE_URL`
as the single allowed origin (never `CORS_ALLOW_ALL_ORIGINS`).

## Rate limits

DRF throttles (Redis-backed cache) protect auth / match / voice scopes. Tune via:

```bash
DRF_THROTTLE_ANON=60/min
DRF_THROTTLE_USER=300/min
DRF_THROTTLE_AUTH=20/min
DRF_THROTTLE_MATCH=30/min
DRF_THROTTLE_VOICE=60/min
```

Full VM + certbot/Caddy wiring: [deploy.md](deploy.md) (Step 73).

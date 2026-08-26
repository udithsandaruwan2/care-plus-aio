# Launch checklist (Step 75)

Research / staging launch — **not** Play Store or App Store (see
[mobile-expo.md](mobile-expo.md)). Tick these before calling the stack “live”
on a VM.

## People & contact

- [ ] Support mailbox monitored: `support@careplus.lk` (override with `VITE_SUPPORT_EMAIL` / `SUPPORT_EMAIL`)
- [ ] Hours stated on the public site (Mon–Sat, 08:00–20:00 Asia/Colombo)
- [ ] Contact form (`/contact`) reaches a human (lead email / inbox)

## PDPA / privacy

- [ ] Public notice at `/privacy` (what we collect, consent, export, erasure)
- [ ] Account holders can export JSON/PDF and erase at `/settings/privacy`
- [ ] Voice / match pipelines still **consent-gated** (`ai_processing`)
- [ ] `FIELD_ENCRYPTION_KEY` set in production (not the derived dev key)
- [ ] `DJANGO_DEBUG=false`, CORS/CSRF origins locked to the real HTTPS origin

## Infra

- [ ] DNS A record → VM; Caddy `CADDY_SITE` is the hostname
- [ ] `./infra/scripts/deploy.sh` health-check green
- [ ] `GET /api/v1/health/` → `status=ok` (and `sentry=on` if DSN set)
- [ ] Daily Postgres dump scheduled ([backups.md](backups.md))
- [ ] Off-box copy of dumps exists
- [ ] `MIGRATE_ON_START=0` in production

## Observability

- [ ] Sentry DSN on API + worker (or accepted as off for a closed trial)
- [ ] `METRICS_TOKEN` set; scrape `127.0.0.1:8000/api/v1/metrics/`
- [ ] JSON logs: `docker compose logs -f backend`

## Mobile (Expo)

- [ ] Testers use **Expo Go SDK 54** + LAN/HTTPS API URL
- [ ] Optional: EAS `preview` APK for testers without Metro
- [ ] Store listings **deferred** until developer accounts exist

## Payments & OTP (production gate)

- [ ] Demo bar green per [e2e-acceptance.md](../e2e-acceptance.md)
- [ ] `OTP_DUMMY=false` and working Django email backend (`EMAIL_HOST` / SES / etc.)
- [ ] Primary LK payments: `PAYMENT_PROVIDER=payhere` with merchant id/secret, notify URL HTTPS, return/cancel URLs
- [ ] Or keep `PAYMENT_PROVIDER=mock` + Stripe demo **only** for closed trials
- [ ] Load smoke on `/voice/turn/` and care-request accept ([load-concurrency.md](load-concurrency.md))
- [ ] Role-gated admin routes verified (patients redirected from `/admin/*`)

## Runbooks

| Topic | Doc |
|-------|-----|
| E2E acceptance (demo) | [e2e-acceptance.md](../e2e-acceptance.md) |
| Deploy / TLS / Sentry | [deploy.md](deploy.md), [tls-proxy.md](tls-proxy.md) |
| CI/CD / GHCR | [ci-cd.md](ci-cd.md) |
| Backups | [backups.md](backups.md) |
| Load | [load-concurrency.md](load-concurrency.md) |
| Mobile | [mobile-expo.md](mobile-expo.md) |

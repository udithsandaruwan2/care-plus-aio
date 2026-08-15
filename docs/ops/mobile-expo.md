# Mobile: Expo Go (current) + optional APK (Step 74 deferred)

Care Plus is **not** submitting to the Play Store or App Store yet (no developer
accounts). Day-to-day mobile work uses **Expo Go** against the LAN API.

## Expo Go (recommended now)

Project SDK: **54** (matches Play Store Expo Go).

1. Phone and PC on the **same Wi‑Fi**.
2. Backend up (`docker compose -f infra/docker-compose.yml up -d`).
3. Start Metro:

```bash
cd apps/mobile
EXPO_PUBLIC_API_URL="http://<PC-LAN-IP>:8000/api/v1" pnpm start -- --lan --port 8081
```

4. In Expo Go, connect to `exp://<PC-LAN-IP>:8081`.

If the LAN IP changes, update `EXPO_PUBLIC_API_URL` and `DJANGO_ALLOWED_HOSTS`.

Do **not** use an old SDK 52 Expo Go APK — it will blue-screen on this project.

## Sideload APK later (no store)

`eas.json` already has a **preview** profile that builds an Android **APK**
(internal distribution). This does **not** need Play Console.

When you have an Expo account and want a file you can install without Metro:

```bash
cd apps/mobile
npx eas-cli login
npx eas-cli build -p android --profile preview
```

EAS hosts the artifact; install via the build page QR / download link
(“Install unknown apps” on the phone).

A **production** AAB/IPA for stores is the `production` profile — leave that
until Step 74 is actually needed.

Local `npx expo run:android` needs Android SDK / `ANDROID_HOME` (not required
for Expo Go).

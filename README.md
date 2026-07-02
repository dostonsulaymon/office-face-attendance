# Office Face-Recognition Attendance System

Two Android phones running as fixed kiosks — one at the entrance (**CHECK-IN**),
one at the exit (**CHECK-OUT**) — capture faces, a backend verifies liveness and
identity server-side, and a real-time dashboard shows who's in, who's out, when,
and the current in-office headcount.

> **Status:** under active construction, built in verifiable slices (see
> [Build progress](#build-progress)). Not all services run yet.

## Architecture

```
[Phone A - CHECK-IN]              [Phone B - CHECK-OUT]
  PWA, front cam, kiosk            PWA, front cam, kiosk
        |                                |
        |   HTTPS POST image + device_id + role
        v                                v
   ┌───────────────────────────────────────────────┐
   │              Backend API (FastAPI)             │
   │  1. liveness check (server-side, anti-spoof)   │
   │  2. if live -> CompreFace recognition          │
   │  3. match vs enrolled employees + confidence   │
   │  4. business rules (dedup, cooldown, sessions) │
   │  5. persist event + audit log                  │
   │  6. push event over WebSocket to dashboards    │
   └───────────────────────────────────────────────┘
       |                |                 |
       v                v                 v
 ┌───────────┐   ┌────────────┐   ┌──────────────┐
 │ CompreFace │   │ Liveness   │   │ PostgreSQL   │
 │ (recognize)│   │(anti-spoof)│   │ + Redis      │
 └───────────┘   └────────────┘   └──────────────┘
                                          |
                                          v
                              ┌────────────────────────┐
                              │ React dashboard (live)  │
                              │ who's in / out / when   │
                              └────────────────────────┘
```

## Components

| Service      | Tech                              | Role |
|--------------|-----------------------------------|------|
| `compreface` | Exadel CompreFace 1.2.0 (Docker)  | Face recognition / verification engine |
| `liveness`   | FastAPI + Silent-Face-Anti-Spoofing | Server-side anti-spoof check (runs before recognition) |
| `api`        | FastAPI + SQLAlchemy + asyncpg    | Business logic, sessions, auth, WebSocket |
| `postgres`   | Postgres 16                       | Attendance, employees, audit log |
| `redis`      | Redis 7                           | Cooldown/dedup keys, WS pub-sub |
| `dashboard`  | React + Vite + TS + Tailwind      | Real-time ops dashboard |
| `kiosk`      | PWA (getUserMedia + face-api.js)  | Entrance/exit capture devices |

## Repository layout

```
backend/     FastAPI application (models, api, services, tests)
liveness/    Silent-Face-Anti-Spoofing FastAPI wrapper
dashboard/   Live ops dashboard (vanilla PWA, nginx-served)
kiosk/       Kiosk Progressive Web App for the phones
compreface/  Vendored CompreFace 1.2.0 compose stack (its own Postgres/JVM)
docs/        Architecture notes, setup guides
scripts/     Helper scripts (recognize.sh, e2e_backend.sh, device-keys.txt)
```

## Ports

| Service     | Host port | Notes |
|-------------|-----------|-------|
| CompreFace UI | 8900    | admin UI (login is buggy headlessly — see notes) |
| API         | 8901      | FastAPI backend |
| Liveness    | 8902      | anti-spoof microservice |
| Kiosk PWA   | 8904      | phones load this via `adb reverse` |
| Dashboard   | 8905      | open in your laptop browser |
| App Postgres| 5433      | (CompreFace has its own internal DB) |

> Ports live in the 89xx block because 8000–8012/8080/8081 were taken by other
> local dev servers. Adjust in the compose files if needed.

## Quick start

```bash
cp .env.example .env      # set JWT_SECRET, admin creds, COMPREFACE_RECOGNITION_API_KEY

# 1. CompreFace stack (heavy: multi-GB images, several GB RAM)
cd compreface && docker compose up -d && cd ..
#    First run: open http://localhost:8900, create an account + a "Recognition"
#    service, copy its API key into .env (COMPREFACE_RECOGNITION_API_KEY).
#    (For headless dev the built-in demo key 0000...0002 also works.)

# 2. The whole application stack (api, liveness, postgres, redis, kiosk, dashboard)
docker compose up -d
```

Default admin login: `admin@example.com` / the `BOOTSTRAP_ADMIN_PASSWORD` in `.env`.

## Testing on Android phones (via adb)

The kiosk uses the camera, which browsers only allow on a secure context.
`adb reverse` maps the phone's `localhost` to your host, and `localhost` counts
as secure — so the camera works over plain HTTP, no certs needed.

```bash
# 1. Register the two kiosk devices (once) and note their API keys:
TOKEN=$(curl -s -X POST http://localhost:8901/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"<admin-pass>"}' | jq -r .access_token)
curl -s -X POST http://localhost:8901/api/devices -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"entrance-01","role":"CHECK_IN","label":"Entrance"}'   # returns api_key
curl -s -X POST http://localhost:8901/api/devices -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_id":"exit-01","role":"CHECK_OUT","label":"Exit"}'          # returns api_key

# 2. For each phone, forward the kiosk + api ports:
for d in $(adb devices | awk 'NR>1 && $2=="device"{print $1}'); do
  adb -s "$d" reverse tcp:8904 tcp:8904
  adb -s "$d" reverse tcp:8901 tcp:8901
done

# 3. Open the kiosk on a phone (Chrome), passing its role/key once — it persists:
#    Entrance phone:
adb -s <serial> shell "am start -a android.intent.action.VIEW -d \
 'http://localhost:8904/?device_id=entrance-01&key=<CHECKIN_KEY>&api=http://localhost:8901&label=Entrance'"
#    Exit phone: same with exit-01 / its key / label=Exit
```

Then: open the **dashboard** at `http://localhost:8905` on your laptop, go to
**Enroll**, add yourself (webcam capture or upload 1–3 photos), and walk up to the
entrance phone — you'll see the check-in appear live on the dashboard, and the
headcount tick up. Walk to the exit phone to check out.

Kiosk config is stored per-device (localStorage); tap ⚙️ to reconfigure. For a
locked-down kiosk, enable Android **Screen Pinning** (Settings → Security → App
pinning) and "Add to Home screen" for a fullscreen app-like launch.

## Helpers

- `scripts/e2e_backend.sh` — drives the full backend business-rule flow end-to-end.
- `scripts/recognize.sh <img>` — throw an image at the recognition engine.
- `cd backend && pip install -r requirements-dev.txt && pytest` — business-rule tests.

## Build progress

- [x] **Slice 1** — repo scaffold, configs, compose skeleton
- [x] **Slice 2** — CompreFace running + API verified end-to-end
- [x] **Slice 3** — liveness microservice (Silent-Face-Anti-Spoofing wrapped, verified)
- [x] **Slice 4** — FastAPI backend (auth, employees+CompreFace, attendance event flow, today/history/export, WS) — verified end-to-end
- [x] **Slice 5** — kiosk PWA (front camera, auto-capture, offline queue, heartbeat)
- [x] **Slice 6** — dashboard (live floor view + WS, today, employees, enroll, review, devices)
- [x] **Slice 7** — full-stack compose (all services incl. nginx-served kiosk + dashboard)
- [x] **Slice 8** — business-rule tests (6 passing)

## ⚠️ Data handling & privacy (read before deploying)

Captured face images and face embeddings are **sensitive biometric data**. In
many jurisdictions (EU GDPR Art. 9, Illinois BIPA, and similar) processing them
carries specific legal obligations. This system is built with the following
safeguards — but **compliance is your responsibility**, not the software's:

- **Server-side liveness only.** A client can never assert "liveness passed";
  the check runs on the backend and cannot be bypassed by a modified app.
- **Consent & notice.** You must inform employees and obtain lawful basis /
  consent before enrolling anyone. This repo does not do that for you.
- **Retention.** Captured audit images auto-delete after
  `IMAGE_RETENTION_DAYS` (default 14). Reference photos persist until the
  employee is deleted.
- **Right to erasure.** Deleting an employee purges their DB record **and** their
  CompreFace embeddings — not just a soft flag.
- **Access control.** All admin/dashboard endpoints require auth; kiosks use
  scoped per-device API keys that can only submit attendance events.
- **Encryption at rest.** Set `IMAGE_ENCRYPTION_KEY` to encrypt stored captures.
- **Transport.** Run everything behind HTTPS in production. Never expose the
  attendance endpoint over plain HTTP.

## License / third-party notes

- CompreFace — Apache-2.0 (Exadel).
- Silent-Face-Anti-Spoofing — verify the model + code license before commercial
  use; the pretrained models ship in-repo and may carry their own terms.

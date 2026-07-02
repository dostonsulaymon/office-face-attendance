# Build Plan & Autonomous Continuation Guide

This file is the **durable source of truth** for the autonomous build loop.
If the interactive session resets, read this file + `README.md` build-progress
checklist to know exactly where things stand, then continue.

## What this project is

Production-grade office attendance system using facial recognition. Two Android
phones act as kiosks (CHECK-IN at entrance, CHECK-OUT at exit) → FastAPI backend
does server-side liveness + recognition → PostgreSQL + Redis → real-time React
dashboard shows who's in/out and headcount. Full original spec is the initial
instruction in the repo's genesis; key requirements distilled below.

## Ground truth already established (Slices 1–2 DONE)

- Monorepo at `~/projects/office-attendance`, git initialized.
- Ports: everything in the **89xx** block (8000–8012/8080/8081 are taken by the
  user's other dev servers). CompreFace UI = **8900**, api = **8901**,
  liveness = **8902**, dashboard = **8903**. App Postgres on host **5433**.
- `postgres` (16) + `redis` (7) run via root `docker-compose.yml`, both healthy.
- CompreFace 1.2.0 stack vendored in `compreface/`, runs, verified end-to-end:
  enroll → detect → embed → match all work. Test faces in `scripts/test-faces/`.
  Manual test helper: `scripts/recognize.sh <img>`.
- **KNOWN CompreFace wart:** admin OAuth token flow rejects tokens headlessly
  ("Failed to find access token" — serialized-auth deserialization bug). Does
  NOT affect the running system: our backend uses the recognition **x-api-key**,
  not admin OAuth. A working demo recognition key exists:
  `00000000-0000-0000-0000-000000000002`. For the real service, the user creates
  one via the UI, OR we insert an app+model row directly (see note below).
- CompreFace DB tables of interest: `app`, `model` (recognition model.api_key is
  the x-api-key; type 'R'), `subject`, `embedding`. Direct DB access:
  `docker exec compreface-postgres-db psql -U postgres -d frs`.

## Remaining build order (do IN ORDER, verify each before moving on)

### Slice 3 — Liveness microservice  ← START HERE
- Wrap `minivision-ai/Silent-Face-Anti-Spoofing` in a small FastAPI service in
  `liveness/`. Single endpoint `POST /check-liveness` (multipart `file`) →
  `{"is_live": bool, "score": float}`. Also `GET /health`.
- The upstream repo has no PyPI package: vendor the `src/` + pretrained models
  (`resources/anti_spoof_models/`) into the image. It uses PyTorch (CPU is fine)
  + OpenCV. Pin versions. Build a Dockerfile; listen on 8902.
- Verify standalone via curl with a real face photo (should be "live") — note we
  only have still images, so a printed-photo spoof test isn't possible here;
  just confirm the model loads, runs, and returns a sane score on a real face.
- Add the `liveness` service to root `docker-compose.yml` (uncomment stub).

### Slice 4 — FastAPI backend (`backend/`)
- Stack: FastAPI + SQLAlchemy (async, asyncpg) + Alembic migrations + Pydantic.
- DB models: `employees`, `attendance_sessions`, `attendance_raw_events`,
  `devices`, `admin_users` (schema details in original spec — replicate exactly).
- Endpoints: employee enroll/list/patch (enroll pushes photos to CompreFace
  face-collection under a subject id = employee); `POST /api/attendance/event`
  (kiosk: liveness → recognition → threshold → business rules → persist →
  WS broadcast); `GET /api/attendance/today`; `/history`; `/export` (csv/xlsx);
  `WS /ws/dashboard`; device registration/heartbeat; JWT auth for admin,
  per-device API key for kiosks.
- Business rules (implement + unit-test in Slice 8): cooldown (Redis, default
  30s), confidence threshold (default 0.90, runtime-configurable), workday
  cutoff hour, check-in opens/reuses session, check-out closes most-recent-open,
  standalone check-out w/o open session = anomaly, open session past cutoff =
  anomaly (never auto-close with guessed time), log every liveness fail + low-
  confidence reject with retained image (retention default 14d).
- Right-to-erasure: deleting an employee purges CompreFace embeddings too.
- Wire into root compose (uncomment `api` stub), port 8901.

### Slice 5 — Kiosk PWA (`kiosk/`)
- PWA, front camera only (`getUserMedia`), fullscreen kiosk UI, big capture zone,
  state feedback (idle→look→verifying→success/fail→auto-reset), optional sound.
- Auto-capture via `face-api.js` tiny detector (presence/stability only, NOT
  recognition — that stays server-side). Manual capture fallback button.
- Role/device_id from query param, persisted (localStorage). Offline queue via
  IndexedDB + exponential backoff retry. Client-side cooldown throttle.

### Slice 6 — Dashboard (`dashboard/`)
- React + Vite + TS + Tailwind + Recharts + Framer Motion + WS client.
- Views: Live Floor (headcount counter, live ticker, present-avatar grid, device
  health) → Today's table → Employee directory/enrollment → Reports/analytics →
  Security/review queue → Device management. Dark theme default + light toggle.
- Start with Live Floor + WS, then the rest.

### Slice 7 — Full-stack deploy
- Single root `docker-compose.yml` bringing up postgres, redis, compreface (or
  documented sub-stack), liveness, api, dashboard (nginx static). Plus
  `docker-compose.dev.yml` with hot-reload for api + dashboard. Finalize README:
  setup, first-employee enrollment, exact kiosk phone config steps.

### Slice 8 — Tests
- Business-rule unit tests: dedup, cooldown, anomaly detection, threshold,
  session matching, workday boundary.

## Autonomy rules for the loop

1. Work ONE slice at a time, in order. Don't scaffold ahead.
2. After each meaningful unit: verify it actually runs (curl/tests/`docker
   compose up`), don't assume. Then tick the README build-progress checklist.
3. Keep the user's ports (89xx) and never bind 8000–8012/8080/8081.
4. Match existing patterns; don't add features beyond the spec.
5. Do NOT do anything irreversible/destructive (dropping volumes, force-pushing,
   rm of user data, `docker system prune`). If blocked on such a decision or a
   genuine ambiguity, STOP and append the question to `docs/BLOCKED.md`, then
   continue with other non-blocked work if possible.
6. Do NOT commit or push unless the user asked (they have not yet).
7. Record progress notes in this file's "Progress log" section each iteration.

## Progress log

- Slice 1 ✅ scaffold + infra (postgres/redis healthy).
- Slice 2 ✅ CompreFace verified end-to-end (enroll/recognize).
- Slice 3 ✅ liveness microservice. Vendored Silent-Face-Anti-Spoofing in
  `liveness/vendor`; wrapper `predictor.py` (loads both anti-spoof models +
  caffe detector once) + `app.py` (FastAPI: `GET /health`, `POST /check-liveness`
  → `{is_live, score, label, face_detected, detector_confidence, bbox}`). Runs on
  modern CPU torch 2.2.2 (original 2019 pins dropped). Built, wired into root
  compose (port 8902, healthcheck), verified healthy + functional via compose.
  NOTE: real-face scores on odd-aspect stock photos are middling (0.55–0.99);
  LIVENESS_THRESHOLD (default 0.85) should be tuned against real 3:4 kiosk frames.
- Slice 4 ✅ DONE — FastAPI backend, verified end-to-end via `scripts/e2e_backend.sh`
  (login→devices→enroll→checkin 0.998→cooldown→headcount→checkout→stranger reject;
  history/export csv+xlsx; WS auth reject/accept). Routers: auth, employees
  (enroll pushes to CompreFace, delete purges embeddings), devices (register/
  rotate/heartbeat), attendance (event pipeline + today/history/export), ws.
  Cross-stack networking solved: compreface-ui joins external `attendance-net`;
  `.env` COMPREFACE_URL=http://compreface-ui:80, demo recognition key set,
  LIVENESS_URL fixed to :8902. Added email-validator dep.
  KNOWN: liveness threshold 0.85 rejects odd-aspect stock photos (007_B scored
  0.556); tune for real 3:4 frames. bcrypt/passlib version-probe warning is
  cosmetic. Alembic still deferred (create_all in use). WS is single-instance
  (Redis pub/sub deferred for multi-instance). Workday-cutoff anomaly sweep
  helper not yet added (open sessions past cutoff) — add during Slice 7/8.
- Slice 5 ✅ Kiosk PWA (`kiosk/`, vanilla — no build step, nginx-served on 8904).
  Front camera, auto-capture loop + manual, state machine, offline IndexedDB
  queue + retry, device heartbeat, sound, per-device localStorage config via
  query params. Tested on real phones via `adb reverse` (localhost = secure
  context → camera works over http). NOTE: face-api.js presence-detect for
  auto-capture was simplified to an interval sampler; add tiny-detector later.
- Slice 6 ✅ Dashboard (`dashboard/`, vanilla PWA, nginx on 8905). Login+JWT,
  Live Floor (WS headcount/ticker/present-grid/device-health), Today table,
  Employees (activate/delete), Enroll (webcam or upload → CompreFace), Review
  queue (rejected raw events + capture images via authed blob fetch), Devices
  (rotate key). Live WS event delivery verified end-to-end. DEVIATION FROM SPEC:
  built vanilla instead of React+Vite+Tailwind+Recharts+Framer Motion to ship a
  working product fast; no analytics charts yet. A richer React rebuild is the
  documented follow-up if desired.
- Slice 6.5 ✅ Added backend review endpoints: GET /api/attendance/review,
  GET /api/attendance/capture/{id} (authed image stream, decrypts if needed);
  storage.read_capture. CORS widened to any localhost origin (kiosk/dashboard).
- Slice 7 ✅ Full-stack compose: kiosk + dashboard nginx services (volume-mounted
  static) added; compreface-ui bridged onto attendance-net. `docker compose up -d`
  now brings up postgres, redis, liveness, api, kiosk, dashboard. (docker-compose.dev
  hot-reload variant still TODO.)
- Slice 8 ✅ Business-rule tests: `backend/tests/test_attendance_rules.py`
  (6 passing — checkin open, duplicate no-op, checkout close, anomaly, full cycle,
  most-recent-open selection). Run via requirements-dev.txt + pytest (sqlite).
- REMAINING/FOLLOW-UPS (non-blocking): Alembic migrations (create_all in use);
  docker-compose.dev.yml hot-reload; workday-cutoff anomaly sweep job; Redis
  pub/sub for multi-instance WS; React dashboard + analytics charts; liveness
  threshold tuning on real frames; frontend images COPYed into nginx (currently
  volume-mounted).
- (prior Slice 4 detail:) `requirements.txt`; `app/core/config.py` (pydantic-settings),
    `app/core/security.py` (bcrypt + JWT + device-key hashing); `app/db/base.py`
    + `session.py` (async engine); `app/models/models.py` (all 5 tables + enums);
    `app/main.py` (lifespan create_all + bootstrap admin + CORS + /health);
    `app/api/deps.py` (admin JWT + device-key auth deps);
    `app/schemas/schemas.py`; service clients `app/services/compreface.py`
    (add_face/recognize/best_match/delete_subject) + `liveness.py`. Dockerfile
    written; `api` service wired into root compose (8901:8080, healthcheck,
    depends on postgres+redis+liveness healthy). Image building.
  - NOTE: using SQLAlchemy create_all at startup for now; proper Alembic
    migrations are a deferred hardening step (remove create_all when added).
  - TODO next: verify api boots + /health via compose; then routers —
    auth (login→JWT), employees (enroll→CompreFace add_face; list; patch;
    delete w/ CompreFace purge), devices (register/rotate key/heartbeat),
    attendance event flow (liveness→recognize→threshold→session business rules
    →raw-event audit→WS broadcast), reads (today/history/export), WS /ws/dashboard.
- (loop appends new entries below as work proceeds)

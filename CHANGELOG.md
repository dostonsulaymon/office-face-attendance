# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- (nothing yet)

## [0.0.1] — 2026-07-02

First public release. Full working stack, verified end-to-end on real hardware.

### Added
- **Backend** (FastAPI + async SQLAlchemy + Postgres + Redis): JWT admin auth,
  per-device API keys, employee enrollment (pushes faces to CompreFace),
  attendance event pipeline (server-side liveness → recognition → cooldown →
  session rules → audit log → WebSocket broadcast), today/history/CSV+XLSX
  export, and a security review queue for rejected attempts.
- **Liveness microservice** wrapping Silent-Face-Anti-Spoofing (server-side
  anti-spoofing on modern CPU PyTorch).
- **CompreFace 1.2.0** recognition stack, vendored via docker-compose.
- **Kiosk PWA**: front-camera capture, auto-capture loop, offline IndexedDB
  queue with retry, device heartbeat, per-device config.
- **Dashboard**: real-time live floor view (WebSocket), today's attendance,
  employee directory, enrollment (webcam/upload), security review, device
  management; responsive with a mobile drawer.
- **Full docker-compose** stack + business-rule unit tests.

### Known limitations
- Dashboard is vanilla JS (a React + Tailwind rebuild is planned).
- Tables are created via `create_all`; Alembic migrations are planned.
- Kiosk auto-capture logs "no face" frames (audit-log noise; cleanup planned).
- Liveness threshold needs tuning against real 3:4 kiosk frames.

[Unreleased]: https://github.com/dostonsulaymon/office-face-attendance/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/dostonsulaymon/office-face-attendance/releases/tag/v0.0.1

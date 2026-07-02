# Contributing to Office Face-Recognition Attendance

First off — thanks for taking the time to contribute! 🎉 This project welcomes
issues, ideas, and pull requests.

## Table of contents
- [Code of conduct](#code-of-conduct)
- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Running the tests](#running-the-tests)
- [Project layout](#project-layout)
- [Coding style](#coding-style)
- [Commit & PR conventions](#commit--pr-conventions)
- [Reporting security issues](#reporting-security-issues)

## Code of conduct
This project follows the [Contributor Covenant](./CODE_OF_CONDUCT.md). By
participating you agree to uphold it.

## Ways to contribute
- 🐛 **Report bugs** via [issues](../../issues) (use the bug template).
- 💡 **Suggest features** via issues (use the feature template).
- 📖 **Improve docs** — README, setup guides, code comments.
- 🧑‍💻 **Send pull requests** — pick up an open issue or propose something.

Good first areas (see the roadmap in `docs/BUILD_PLAN.md` follow-ups):
- React + Tailwind dashboard rebuild (the current one is intentionally vanilla).
- `face-api.js` presence detection for smarter kiosk auto-capture.
- Alembic migrations (the app currently bootstraps tables via `create_all`).
- Skip logging "no face" frames to keep the audit log clean.

## Development setup

**Prerequisites:** Docker + Docker Compose, and Python 3.11 (for running tests).

```bash
git clone https://github.com/dostonsulaymon/office-face-attendance.git
cd office-face-attendance
cp .env.example .env                       # then set your secrets
cp compreface/.env.example compreface/.env # CompreFace stack config

# 1. CompreFace recognition stack (heavy: multi-GB, several GB RAM)
cd compreface && docker compose up -d && cd ..

# 2. The application stack
docker compose up -d
```

See the [README](./README.md) for ports, first-employee enrollment, and how to
point kiosk phones at the backend over `adb`.

## Running the tests

Business-rule unit tests run without any external services (SQLite in-memory):

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

CI runs these on every push and pull request (see `.github/workflows/ci.yml`).
Please make sure they pass and add tests for new business logic.

## Project layout

```
backend/     FastAPI app (models, api, services, tests)
liveness/    Silent-Face-Anti-Spoofing FastAPI wrapper
compreface/  Vendored CompreFace 1.2.0 stack
kiosk/       Kiosk PWA (phones)
dashboard/   Ops dashboard
docs/        Architecture + build plan
```

## Coding style
- **Python:** PEP 8, 4-space indent, type hints where they help. Keep functions
  small and readable; match the style of the surrounding code.
- **JS/CSS:** vanilla, no build step for kiosk/dashboard — keep it dependency-light.
- Don't add abstractions or dependencies you don't need.
- Comment only non-obvious logic (the attendance session rules are the main
  place comments earn their keep).

## Commit & PR conventions
- Keep commits focused; write a clear imperative subject line
  (e.g. `Add cooldown override per device`).
- One logical change per PR. Describe **what** and **why**, link related issues.
- Ensure `pytest` passes and no secrets (`.env`, device keys, tokens) are staged.
- Fill in the pull request template.

## Reporting security issues
**Do not open a public issue for vulnerabilities.** This project handles
biometric data — see [SECURITY.md](./SECURITY.md) for private disclosure.

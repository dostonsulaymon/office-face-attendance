# Security Policy

## Supported versions

This project is in early development. Security fixes target the latest `main`
and the most recent tagged release.

| Version | Supported |
|---------|-----------|
| 0.0.x   | ✅        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately to **dostonibnsulaymon@gmail.com** (or via GitHub's
"Report a vulnerability" under the Security tab). Include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected component (backend, liveness, kiosk, dashboard, deployment).

You can expect an initial response within a few days. Please give us reasonable
time to investigate and release a fix before any public disclosure.

## Handling biometric data (important)

This system processes **face images and face embeddings** — sensitive biometric
data subject to laws such as the EU GDPR (Art. 9) and Illinois BIPA. If you
deploy it:

- Obtain lawful basis / informed consent before enrolling anyone.
- Keep everything behind **HTTPS** in production; never expose the attendance
  endpoint over plain HTTP.
- Liveness detection **must** run server-side (it does) — never trust a
  client-supplied "liveness passed" flag.
- Use per-device API keys (rotatable) for kiosks; never bake long-lived secrets
  into client code.
- Set `IMAGE_ENCRYPTION_KEY` to encrypt captured frames at rest, and honor the
  `IMAGE_RETENTION_DAYS` auto-deletion policy.
- Support right-to-erasure: deleting an employee purges their CompreFace
  embeddings, not just the database row.

Compliance is the responsibility of the deployer, not the software.

## Notes for local/demo setups

- `.env` (JWT secret, admin password, DB password) is git-ignored — keep it that
  way. Only `.env.example` (placeholders) is committed.
- `compreface/.env.example` ships CompreFace's default localhost credentials.
  **Change them before any non-local deployment.**
- Kiosk device API keys live in `scripts/device-keys.txt`, which is git-ignored.

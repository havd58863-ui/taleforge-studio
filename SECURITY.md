# Security Policy

This is a private commercial project. Treat every credential and every generated
asset as confidential.

## Never commit
- `.env` (only `.env.example` belongs in the repo)
- `kaggle.json` or any `KAGGLE_*` value
- database dumps, `*.db`, `instance/`
- anything under `secure_data/`, `vector_store/`, `output/`
- customer data or sales reports

## Reporting
Report vulnerabilities privately to the repository owner. Do not open a public
issue describing an exploitable flaw.

## Operational baseline
| Area | Requirement |
|---|---|
| Secrets | GitHub Secrets / server-side env vars, never in code |
| Transport | HTTPS only, secure cookies enabled (`APP_ENV=production`) |
| Access | Put the app behind auth (reverse proxy or Flask-Login + RBAC) before exposing it |
| Uploads | `MAX_CONTENT_LENGTH` is capped at 64 MB; validate MIME types before saving |
| Backups | Postgres volume + object storage must be backed up off-host |
| Rotation | Rotate any key that ever appeared in chat, a screenshot or a commit |

## Known limitations of this foundation
- No authentication layer is implemented yet.
- No rate limiting on the API.
- The JSON API is unauthenticated: do not expose it publicly as-is.

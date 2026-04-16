# Security

## Supported setup

This repository is intended for local, self-hosted use. It automates Facebook Marketplace browsing, can store browser-adjacent data on disk, and can send listing data to third-party AI and notification providers. Treat the local environment as sensitive.

## Secrets and local state

- Keep `.env` local. Only `.env.example` should ever be committed.
- Do not commit API keys, bot tokens, SMTP credentials, browser session state, or private config overlays.
- Review `personal.toml` (repo root, gitignored) and `dev_documents/` before pushing. Both are ignored on purpose.
- If you persist Marketplace login state locally, treat that storage like a secret and rotate it if you suspect leakage.

## Reporting an issue

If you find a security issue, do not open a public issue with the secret or exploit details. Share a minimal private report with:

- what is affected
- how it can be reproduced
- what data or privilege boundary is involved
- any suggested mitigation

If a real secret is ever committed, remove it from the repository history and rotate it immediately.

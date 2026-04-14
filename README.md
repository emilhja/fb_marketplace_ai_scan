# Facebook Marketplace Scan

`facebook_marketplace_scan` is a personal fork of `ai-marketplace-monitor` with a PostgreSQL-backed cache, a small FastAPI + React dashboard, and extra workflow support for rerunning or reviewing listings locally.

The repository is now structured to be shareable on GitHub:

- public docs stay in the repo
- private notes belong in `dev_documents/` and are ignored
- local secrets belong in `.env`, never in tracked files
- CI validates Python style/tests and the frontend build

## What It Does

- Scans Facebook Marketplace searches using the vendored `ai_marketplace_monitor` package.
- Caches listing observations and AI evaluations in PostgreSQL to reduce duplicate work.
- Exposes a read-only dashboard API plus a React UI for listings, price history, and notifications.
- Supports notification workflows and rerun queue processing for listings that need another pass.

## Tech Stack

- Python 3.11+ for the scanner, scripts, tests, and backend services
- Playwright for Marketplace browser automation
- PostgreSQL with `psycopg` and SQLAlchemy for cache and dashboard data
- FastAPI and Pydantic for the dashboard API
- React, TypeScript, Vite, and ESLint for the frontend
- Ruff, Black, pytest, and GitHub Actions for code quality and CI

## Repository Layout

- `ai_marketplace_monitor/`: vendored scanner logic and Marketplace-specific parsing.
- `backend/`: FastAPI API, SQLAlchemy models, and rerun queue support.
- `frontend/`: React + Vite dashboard UI.
- `scripts/`: operational helper scripts.
- `tests/`: hermetic unit tests.
- `docs/`: public reference notes.

## Quick Start

### Python and frontend dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

```bash
cd frontend
npm install
```

### Environment

Copy `.env.example` to `.env` and set the values you need locally.

Important settings:

- `OPENROUTER_API_KEY`: AI scoring backend.
- `AIMM_DATABASE_URL`: PostgreSQL connection string for scanner and dashboard data.
- `AIMM_PG_CACHE_ENABLED=1`: enable the PostgreSQL cache layer.
- `AIMM_REEVAL_ON_PRICE_CHANGE=1`: rerun AI when price changes.
- `AIMM_REEVAL_ON_CONTENT_CHANGE=1`: rerun AI when listing content changes.
- `AIMM_PROMPT_VERSION=v1`: bump when prompt semantics change.

### Scanner

`scraping_run.sh` is the canonical scanner entrypoint. It loads `.env`, ensures the local package is importable, bootstraps the PostgreSQL cache schema, and starts the CLI:

```bash
./scraping_run.sh
```

The main runtime config still lives outside the repo in `~/.ai-marketplace-monitor/config.toml`. This fork also supports an optional gitignored local overlay in `ai_marketplace_monitor/personal_config/personal.toml`; start from [ai_marketplace_monitor/personal_config/personal.toml.example](/home/emiloanna/privata_projekt/facebook_marketplace_scan/ai_marketplace_monitor/personal_config/personal.toml.example).

Use `~/.ai-marketplace-monitor/config.toml` for your normal long-lived searches and defaults across machines or repos. Use `ai_marketplace_monitor/personal_config/personal.toml` for repo-specific local overrides that should stay private, such as experimental prompts, temporary model changes, local notification routing, or Facebook credentials during development.

### Dashboard

Start both backend and frontend:

```bash
./start.sh
```

Or start them separately:

```bash
cd backend
./start.sh
```

```bash
cd frontend
npm run dev
```

Default local URLs:

- API: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Development Workflow

Quality checks:

```bash
ruff check .
black --check .
pytest
python scripts/check_repo_hygiene.py
cd frontend && npm run lint && npm run build
```

What CI enforces:

- Python import/lint correctness via Ruff
- Python formatting via Black
- unit tests via pytest
- repo hygiene checks for tracked secrets
- frontend lint and production build

## Safety Notes Before Publishing

- Keep `.env` untracked.
- Do not commit browser session state, API keys, DB dumps, or private troubleshooting notes.
- Review any changes under `ai_marketplace_monitor/config.toml` before publishing to ensure it contains only safe defaults.
- If a secret is ever committed, rotate it and clean the repository history.

## Public Docs

- [Documentation index](docs/README.md)
- [Reference notes](docs/reference/README.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Known Constraints

- Facebook page structure is unstable, so parser code and tests need periodic maintenance.
- Most tests are unit-level and do not validate a live Facebook or PostgreSQL environment.
- This repo contains active local development work; review the current diff before publishing a release branch or tag.

## License

[MIT](LICENSE)

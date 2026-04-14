# Contributing

## Local setup

1. Create a Python virtual environment in the repo root.
2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Copy `.env.example` to `.env` and fill in only the values you need for local development.
4. For frontend work:
   ```bash
   cd frontend
   npm install
   ```

## Quality gates

Run these before pushing:

```bash
ruff check .
black --check .
pytest
python scripts/check_repo_hygiene.py
cd frontend && npm run lint && npm run build
```

## Style

- Use Black for Python formatting.
- Keep docstrings on public or high-complexity modules, classes, and functions.
- Prefer hermetic unit tests over tests that require Facebook, Playwright, or a live database.
- Keep private notes in `dev_documents/`, not in tracked docs.

## Pull requests

- Explain the user-visible change and any operational impact.
- Mention schema or env var changes explicitly.
- Do not commit `.env`, credentials, session artifacts, or local database files.

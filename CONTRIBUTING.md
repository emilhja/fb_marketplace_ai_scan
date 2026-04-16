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
./scripts/pre_push_check.sh
```

To enable the same check automatically on every push:

```bash
./scripts/install_git_hooks.sh
```

Blocking checks in the helper:
- secret scanning and repo hygiene
- YAML/TOML validation
- `pip-audit`
- `pytest`
- frontend production build
- `npm audit --audit-level=high`

Advisory checks in the helper:
- `trailing-whitespace`
- `end-of-file-fixer`
- frontend lint

Direct pushes from `main` are blocked by default. Override intentionally with:

```bash
ALLOW_PUSH_TO_MAIN=1 ./scripts/pre_push_check.sh
ALLOW_PUSH_TO_MAIN=1 git push
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

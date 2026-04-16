# OpenRouter model choice

## Use one fixed model id

Do **not** use `openrouter/free` for listing evaluation. That slug is a **router**: each request can land on a different free model, so `response_model` in PostgreSQL changes every time and scores are **not comparable** across listings or runs.

Set a **single** OpenRouter model slug in config (for this repo, typically `personal.toml` in the repo root under `[ai.openrouter]` → `model`).

## Current default in this workspace

We use **`openai/gpt-oss-120b:free`** as the pinned free model: stronger adherence to a written rubric (e.g. VRAM rules) than the 20B variant, at the cost of **higher latency** and often **tighter free-tier rate limits**.

If you see timeouts or HTTP 429 from OpenRouter:

- Increase spacing between AI calls (e.g. `.env` → `AIMM_AI_DELAY_SECONDS`), or
- Temporarily switch to **`openai/gpt-oss-20b:free`** in `personal.toml`, or
- Move to a **paid** fixed slug with its own limits.

## Cache note

PostgreSQL AI cache keys include the configured **`model`** string. Changing `model` invalidates prior cached rows for that model; new evaluations use the new judge consistently.

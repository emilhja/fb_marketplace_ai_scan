# Rating / AI evaluation improvements

Notes for tightening how listings are scored (e.g. RTX 5060 **16 GB** desktop GPU hunt on Facebook Marketplace).

## Context

- Default AI rubric in `ai_marketplace_monitor/ai.py` (`get_prompt`) is generic (“4 = good match”), so models may overweight “right chip name” and underweight **hard** constraints like VRAM unless you spell them out.
- `personal.toml` already adds a stricter **`description`** and **`extra_prompt`** on `[item.rtx5060]` (VRAM from title + description, caps for wrong/unknown VRAM, 4–5 only when 16 GB is explicit). Changing those fields changes config/prompt hashes, so cached AI scores are not reused for old prompt text.

## Suggested improvements

### 1. Stronger, stable model for scoring

`openrouter/free` swaps models and is a common source of inconsistent scores for the same kind of listing. For predictable behavior, pin a small fixed model (e.g. a cheap GPT‑4–class or a specific OpenRouter model id) so `extra_prompt` is interpreted the same way run to run.

### 2. `rating` when you add alerts

With `# rating = 3` left commented, behavior depends on defaults. When `notify_with` includes Telegram (or similar), set **`rating = 4`** (or `5`) so only listings the model is very confident about trigger pushes. Terminal `[found]` output may still show lower scores unless the app filters them separately.

### 3. Broader `search_phrases` (recall)

Facebook search is crude. Adding e.g. `'5060 ti'` and maybe `'5060ti'` as **additional** `search_phrases` can surface listings that do not match the first phrase, **without** tightening `keywords`. Requiring `16` inside `keywords` is **not** recommended: many valid 16 GB ads only mention VRAM in the body, not the title.

### 4. Optional `antikeywords` for obvious non-GPU noise

If the feed is dominated by full PCs, test Swedish phrases **one at a time** (watch false negatives), e.g. `gamingdator`, `speldator`, `komplett`. `extra_prompt` already downgrades vague prebuilds; antikeywords are a blunt pre-AI filter.

### 5. Further `extra_prompt` tweaks (if drift remains)

- Treat **stock / press photos only** and **no VRAM in text** like unknown VRAM (same caps as today).
- Mention **Swedish** variants explicitly (`GB`, `Gbyte`, `grafikkort`, VRAM in seller text).
- Ask the model to output the **`Rating` line first**, then the summary, to align with the parser in `ai.py`.

### 6. Marketplace `category`

If your Facebook flow supports it reliably, restrict to the right Marketplace category (e.g. electronics / computer parts per docs) to reduce irrelevant listings before AI runs.

### 7. Operational

- After prompt or item changes, expect **more API calls** until PG/disk cache repopulates for new hashes.
- **`search_interval`**: shorter intervals mean more browser + API churn; lengthen if you do not need that cadence.

## Principle

Prefer **wide search + strict AI gate** for VRAM; do not require `16` in `keywords` unless you accept missing listings whose titles omit VRAM.

For stricter “never false good” vs “never miss a 16 GB deal,” tune `extra_prompt`: harsher caps on unknown VRAM vs slightly higher ceiling when text is thin but still plausible.

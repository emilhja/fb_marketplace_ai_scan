# AI rating and threshold (`ai-marketplace-monitor`)

After each listing is evaluated (e.g. via OpenRouter), the monitor gets a **numeric score 1–5** and a short comment. Whether you get notified / the listing counts as a **hit** depends on comparing that score to a **minimum acceptable rating** (the log line calls this the **threshold**).

## Score → label

| Score | Conclusion       |
|------:|------------------|
| 1     | No match         |
| 2     | Potential match  |
| 3     | Poor match       |
| 4     | Good match       |
| 5     | Great deal       |

## Default threshold is 3

If **neither** the marketplace item **nor** the Facebook marketplace block sets `rating` in `~/.ai-marketplace-monitor/config.toml`, the code uses **`acceptable_rating = 3`**.

A listing is **skipped** (no notification for that listing) when:

```text
AI score < acceptable_rating
```

So with the default:

- **1** and **2** → skipped (“below threshold 3”).
- **3**, **4**, **5** → can proceed (subject to other filters).

Example log: `Rating No match (1) for … is below threshold 3` means the model returned score **1**, and **1 < 3**, so the monitor drops it.

## Configuring the threshold

Set `rating` on the **item** or on the **marketplace** section in `config.toml`. It can be a single integer or a list of integers between **1** and **5** (the monitor may use the first or last entry depending on search count—see `monitor.py` in the installed package).

Examples:

- `rating = 4` — only “Good match” and “Great deal” pass.
- `rating = 2` — “Potential match” and above pass.

## Not the same as keyword rules

Messages like **“Exclude … without required keywords in title and description”** come from **keyword** / text filters, not from the AI score. A listing can fail one rule, both, or neither.

## Where this lives in code

Installed with the app (e.g. venv): `ai_marketplace_monitor/monitor.py` (`acceptable_rating`, `if res.score < acceptable_rating`) and `ai_marketplace_monitor/ai.py` (`AIResponse.conclusion` mapping).

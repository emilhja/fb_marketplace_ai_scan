#!/usr/bin/env python3
"""Re-apply local patches to the installed ai-marketplace-monitor package.

Run from run.sh after venv activate. Safe to run every time (idempotent).

Patches:
 1. monitor.py — sleep AIMM_AI_DELAY_SECONDS after each evaluate_by_ai (OpenRouter pacing).
 2. ai.py — reject empty api_key; fix NameError when all retries fail (response unset).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SENTINEL_MONITOR = "facebook_marketplace_scan_patch: ai_delay"
SENTINEL_AI = "facebook_marketplace_scan_patch: ai_retry"


def package_dir() -> Path:
    spec = importlib.util.find_spec("ai_marketplace_monitor")
    if not spec or not spec.origin:
        print("apply_ai_marketplace_monitor_patches: ai_marketplace_monitor not found", file=sys.stderr)
        sys.exit(1)
    return Path(spec.origin).parent


def patch_monitor(monitor_py: Path) -> bool:
    text = monitor_py.read_text(encoding="utf-8")
    original = text

    # Two call sites each carry this substring in the inserted comment line.
    if text.count(SENTINEL_MONITOR) >= 2:
        print("monitor.py: already patched")
        return True

    block_res = f"""            # {SENTINEL_MONITOR} (AIMM_AI_DELAY_SECONDS in .env)
            _ai_delay = float(__import__("os").environ.get("AIMM_AI_DELAY_SECONDS", "0") or "0")
            if _ai_delay > 0:
                time.sleep(_ai_delay)
"""

    block_rating = f"""                # {SENTINEL_MONITOR} (AIMM_AI_DELAY_SECONDS in .env)
                _ai_delay = float(__import__("os").environ.get("AIMM_AI_DELAY_SECONDS", "0") or "0")
                if _ai_delay > 0:
                    time.sleep(_ai_delay)
"""

    res_needle = """            res = self.evaluate_by_ai(
                listing, item_config=item_config, marketplace_config=marketplace_config
            )
            if self.logger:"""

    rating_needle = """                rating = self.evaluate_by_ai(
                    listing, item_config=item_config, marketplace_config=marketplace_config
                )
                if self.logger:"""

    # Older manual throttle: tag comment so we skip re-applying the main block
    if "_ai_delay" in text and "time.sleep(_ai_delay)" in text:
        text = text.replace(
            "# Optional throttle between OpenRouter/OpenAI calls",
            f"# {SENTINEL_MONITOR}",
            1,
        )

    if res_needle in text:
        text = text.replace(
            res_needle,
            res_needle.replace("            if self.logger:", block_res + "            if self.logger:", 1),
            1,
        )

    if rating_needle in text:
        text = text.replace(
            rating_needle,
            rating_needle.replace("                if self.logger:", block_rating + "                if self.logger:", 1),
            1,
        )

    if text == original:
        print(
            "monitor.py: no changes (needles not found); "
            "upgrade ai-marketplace-monitor and update scripts/apply_ai_marketplace_monitor_patches.py",
            file=sys.stderr,
        )
        return False

    monitor_py.write_text(text, encoding="utf-8")
    print("monitor.py: applied ai_delay patch(es)")
    return True


# Vanilla 0.9.11 OpenAIConfig.handle_api_key (must match upstream exactly).
_OLD_OPENAI_KEY = """@dataclass
class OpenAIConfig(AIConfig):
    def handle_api_key(self: "OpenAIConfig") -> None:
        if self.api_key is None:
            raise ValueError("OpenAI requires a string api_key.")
"""


def _new_openai_key() -> str:
    return f"""@dataclass
class OpenAIConfig(AIConfig):
    def handle_api_key(self: "OpenAIConfig") -> None:
        # {SENTINEL_AI} (empty key → OpenRouter 401 Missing Authentication header)
        if self.api_key is None:
            raise ValueError("OpenAI requires a string api_key.")
        if not isinstance(self.api_key, str):
            raise ValueError("OpenAI requires a string api_key.")
        self.api_key = self.api_key.strip()
        if not self.api_key:
            raise ValueError(
                "api_key is empty (often OPENROUTER_API_KEY missing or blank in the process "
                "environment). Put sk-or-v1-... in .env and start with ./run.sh, or set the key "
                "directly in config.toml without ${{...}}."
            )
"""


# Vanilla 0.9.11 OpenAIBackend.evaluate loop (single-quoted fragments avoid nested """ issues).
def _old_evaluate_loop() -> str:
    return (
        "        self.connect()\n"
        "\n"
        "        retries = 0\n"
        "        while retries < self.config.max_retries:\n"
        "            self.connect()\n"
        "            assert self.client is not None\n"
        "            try:\n"
        "                response = self.client.chat.completions.create(\n"
        "                    model=self.config.model or self.default_model,\n"
        "                    messages=[\n"
        "                        {\n"
        '                            "role": "system",\n'
        '                            "content": "You are a helpful assistant that can confirm if a user\'s search criteria matches the item he is interested in.",\n'
        "                        },\n"
        '                        {"role": "user", "content": prompt},\n'
        "                    ],\n"
        "                    stream=False,\n"
        "                )\n"
        "                break\n"
        "            except KeyboardInterrupt:\n"
        "                raise\n"
        "            except Exception as e:\n"
        "                if self.logger:\n"
        "                    self.logger.error(\n"
        '                        f"""{hilight("[AI-Error]", "fail")} {self.config.name} failed to evaluate {hilight(listing.title)}: {e}"""\n'
        "                    )\n"
        "                retries += 1\n"
        "                # try to initiate a connection\n"
        "                self.client = None\n"
        "                time.sleep(5)\n"
        "\n"
        "        # check if the response is yes\n"
        "        if self.logger:\n"
        '            self.logger.debug(f"""{hilight("[AI-Response]", "info")} {pretty_repr(response)}""")\n'
    )


def _new_evaluate_loop() -> str:
    return (
        "        self.connect()\n"
        "\n"
        "        retries = 0\n"
        "        response = None\n"
        "        last_error: Exception | None = None\n"
        f"        # {SENTINEL_AI}\n"
        "        while retries < self.config.max_retries:\n"
        "            self.connect()\n"
        "            assert self.client is not None\n"
        "            try:\n"
        "                response = self.client.chat.completions.create(\n"
        "                    model=self.config.model or self.default_model,\n"
        "                    messages=[\n"
        "                        {\n"
        '                            "role": "system",\n'
        '                            "content": "You are a helpful assistant that can confirm if a user\'s search criteria matches the item he is interested in.",\n'
        "                        },\n"
        '                        {"role": "user", "content": prompt},\n'
        "                    ],\n"
        "                    stream=False,\n"
        "                )\n"
        "                break\n"
        "            except KeyboardInterrupt:\n"
        "                raise\n"
        "            except Exception as e:\n"
        "                last_error = e\n"
        "                if self.logger:\n"
        "                    self.logger.error(\n"
        '                        f"""{hilight("[AI-Error]", "fail")} {self.config.name} failed to evaluate {hilight(listing.title)}: {e}"""\n'
        "                    )\n"
        "                retries += 1\n"
        "                # try to initiate a connection\n"
        "                self.client = None\n"
        "                time.sleep(5)\n"
        "\n"
        "        if response is None:\n"
        "            counter.increment(CounterItem.FAILED_AI_QUERY, item_config.name)\n"
        "            hint = (\n"
        '                " Check OPENROUTER_API_KEY is set and non-empty in the same environment as the monitor."\n'
        '                if last_error and "401" in str(last_error)\n'
        '                else ""\n'
        "            )\n"
        "            raise ValueError(\n"
        '                f"No response from {self.config.name} after {self.config.max_retries} attempts.{hint} Last error: {last_error!r}"\n'
        "            )\n"
        "\n"
        "        # check if the response is yes\n"
        "        if self.logger:\n"
        '            self.logger.debug(f"""{hilight("[AI-Response]", "info")} {pretty_repr(response)}""")\n'
    )


def patch_ai(ai_py: Path) -> bool:
    text = ai_py.read_text(encoding="utf-8")
    original = text

    if SENTINEL_AI in text:
        print("ai.py: already patched")
        return True

    # Prior manual patch: same behavior, no sentinel comment
    if (
        "if response is None:" in text
        and "last_error" in text
        and "api_key is empty (often OPENROUTER" in text
    ):
        text = text.replace(
            "        last_error: Exception | None = None\n",
            f"        # {SENTINEL_AI}\n        last_error: Exception | None = None\n",
            1,
        )
        if text != original:
            ai_py.write_text(text, encoding="utf-8")
            print("ai.py: tagged existing retry + empty-key fix")
        else:
            print("ai.py: retry + empty-key fix already present (could not insert sentinel)")
        return True

    old_openai_key = _OLD_OPENAI_KEY
    new_openai_key = _new_openai_key()
    old_loop = _old_evaluate_loop()
    new_loop = _new_evaluate_loop()

    changed = False
    if old_openai_key in text:
        text = text.replace(old_openai_key, new_openai_key, 1)
        changed = True
    else:
        print("ai.py: OpenAIConfig block not found; skip or update patch script", file=sys.stderr)

    if old_loop in text:
        text = text.replace(old_loop, new_loop, 1)
        changed = True
    elif "response = None" in text and "last_error" in text:
        print("ai.py: retry loop already patched")
    else:
        print("ai.py: evaluate loop not found; skip or update patch script", file=sys.stderr)

    if not changed and text == original:
        if ("response = None" in text and "if response is None:" in text) or (
            "api_key is empty (often OPENROUTER" in text
        ):
            print("ai.py: fixes already present (vanilla needles did not match)")
            return True
        return False

    if changed:
        ai_py.write_text(text, encoding="utf-8")
        print("ai.py: applied api_key + exhausted-retry patches")
    return True


def main() -> None:
    root = package_dir()
    if not patch_monitor(root / "monitor.py") or not patch_ai(root / "ai.py"):
        sys.exit(1)


if __name__ == "__main__":
    main()

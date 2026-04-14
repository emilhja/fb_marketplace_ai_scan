#!/usr/bin/env python3
"""Re-apply local patches to the installed ai-marketplace-monitor package.

Run from run.sh after venv activate. Safe to run every time (idempotent).

Patches:
 1. monitor.py — sleep AIMM_AI_DELAY_SECONDS after each evaluate_by_ai (OpenRouter pacing);
    compact “[found] …” lines on stderr (AIMM_PRINT_FOUND=0 to disable);
    PostgreSQL listing/notification event hooks.
 2. ai.py — reject empty api_key; fix NameError when all retries fail (response unset);
    PostgreSQL AI dedupe/cache hooks.
 3. facebook.py — log search failure only when no listings; optional manual-search fallback.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SENTINEL_MONITOR = "facebook_marketplace_scan_patch: ai_delay"
SENTINEL_TERMINAL_FOUND = "facebook_marketplace_scan_patch: terminal_found"
SENTINEL_AI = "facebook_marketplace_scan_patch: ai_retry"
SENTINEL_FACEBOOK = "facebook_marketplace_scan_patch: manual_search_fallback"
SENTINEL_PG_OBSERVE = "facebook_marketplace_scan_patch: pg_listing_observe"
SENTINEL_PG_AI = "facebook_marketplace_scan_patch: pg_ai_dedupe"
SENTINEL_PG_NOTIFY = "facebook_marketplace_scan_patch: pg_notify_event"


def package_dir() -> Path:
    spec = importlib.util.find_spec("ai_marketplace_monitor")
    if not spec or not spec.origin:
        print(
            "apply_ai_marketplace_monitor_patches: ai_marketplace_monitor not found",
            file=sys.stderr,
        )
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
            res_needle.replace(
                "            if self.logger:", block_res + "            if self.logger:", 1
            ),
            1,
        )

    if rating_needle in text:
        text = text.replace(
            rating_needle,
            rating_needle.replace(
                "                if self.logger:",
                block_rating + "                if self.logger:",
                1,
            ),
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


# Previous verbose terminal_found patch (replaced by compact lines when present).
_OLD_TERMINAL_FOUND_VERBOSE = """        if new_listings:
            # facebook_marketplace_scan_patch: terminal_found Plain summary on stderr. Set AIMM_PRINT_FOUND=0 to disable.
            _aimm_pf = __import__("os").environ.get("AIMM_PRINT_FOUND", "1").strip().lower()
            if _aimm_pf not in ("0", "false", "no", "off"):
                _aimm_sys = __import__("sys")
                _aimm_parts = [
                    "",
                    f"=== Found {len(new_listings)} listing(s) for {item_config.name!r} ===",
                ]
                for _aimm_li, _aimm_rt in zip(new_listings, listing_ratings):
                    _aimm_url = _aimm_li.post_url.split("?")[0]
                    _aimm_parts.extend(
                        [
                            f"  • {_aimm_li.title}",
                            f"    {_aimm_li.price}, {_aimm_li.location}",
                            f"    {_aimm_url}",
                        ]
                    )
                    if _aimm_rt.comment != AIResponse.NOT_EVALUATED:
                        _aimm_parts.append(
                            f"    AI: {_aimm_rt.conclusion} ({_aimm_rt.score}) — {_aimm_rt.comment}"
                        )
                print("\\n".join(_aimm_parts), file=_aimm_sys.stderr, flush=True)
            counter.increment(
                CounterItem.NEW_VALIDATED_LISTING, item_config.name, len(new_listings)
            )
"""


def _terminal_found_compact_block() -> str:
    return f"""        if new_listings:
            # {SENTINEL_TERMINAL_FOUND} stderr: [found] + one line per hit (title | price | url). AIMM_PRINT_FOUND=0 off.
            _aimm_pf = __import__("os").environ.get("AIMM_PRINT_FOUND", "1").strip().lower()
            if _aimm_pf not in ("0", "false", "no", "off"):
                _aimm_sys = __import__("sys")
                _aimm_lines = [f"[found] {{item_config.name}}: {{len(new_listings)}} listing(s)"]
                for _aimm_li, _aimm_rt in zip(new_listings, listing_ratings):
                    _aimm_u = _aimm_li.post_url.split("?")[0]
                    _aimm_tail = ""
                    if _aimm_rt.comment != AIResponse.NOT_EVALUATED:
                        _aimm_tail = f" | {{_aimm_rt.conclusion}} ({{_aimm_rt.score}})"
                    _aimm_lines.append(
                        f"  {{_aimm_li.title}} | {{_aimm_li.price}} | {{_aimm_u}}{{_aimm_tail}}"
                    )
                print("\\n".join(_aimm_lines), file=_aimm_sys.stderr, flush=True)
            counter.increment(
                CounterItem.NEW_VALIDATED_LISTING, item_config.name, len(new_listings)
            )
"""


def patch_terminal_found(monitor_py: Path) -> bool:
    """Print compact stderr lines when matches pass the AI threshold."""
    text = monitor_py.read_text(encoding="utf-8")
    compact = _terminal_found_compact_block()
    vanilla = """        if new_listings:
            counter.increment(
                CounterItem.NEW_VALIDATED_LISTING, item_config.name, len(new_listings)
            )"""

    if SENTINEL_TERMINAL_FOUND in text and "_aimm_lines" in text:
        print("monitor.py: terminal_found already patched")
        return True

    if _OLD_TERMINAL_FOUND_VERBOSE in text:
        monitor_py.write_text(
            text.replace(_OLD_TERMINAL_FOUND_VERBOSE, compact, 1), encoding="utf-8"
        )
        print("monitor.py: upgraded terminal_found to compact stderr lines")
        return True

    if vanilla not in text:
        print(
            "monitor.py: terminal_found needle not found; upgrade ai-marketplace-monitor and "
            "update scripts/apply_ai_marketplace_monitor_patches.py",
            file=sys.stderr,
        )
        return False

    monitor_py.write_text(text.replace(vanilla, compact, 1), encoding="utf-8")
    print("monitor.py: applied terminal_found (compact stderr) patch")
    return True


def patch_monitor_db(monitor_py: Path) -> bool:
    """Add listing-observe + notification-event hooks."""
    text = monitor_py.read_text(encoding="utf-8")
    original = text

    observe_needle = "            # if everyone has been notified"
    observe_block = f"""            # {SENTINEL_PG_OBSERVE} observe listing identity/price in PostgreSQL (best effort).
            try:
                __import__("fbm_pg_cache").observe_listing(listing, logger=self.logger)
            except Exception:
                pass
{observe_needle}"""

    notify_vanilla = """            for user in users_to_notify:
                User(self.config.user[user], logger=self.logger).notify(
                    new_listings, listing_ratings, item_config
                )"""
    notify_new = f"""            for user in users_to_notify:
                _u = User(self.config.user[user], logger=self.logger)
                try:
                    _u.notify(new_listings, listing_ratings, item_config)
                    try:
                        for _li in new_listings:
                            __import__("fbm_pg_cache").record_notification_event(
                                listing=_li,
                                user_name=user,
                                channel=_u.config.notify_with[0] if _u.config.notify_with else "unknown",
                                status="sent",
                                details={{"count": len(new_listings), "item": item_config.name}},
                                logger=self.logger,
                            )
                    except Exception:
                        pass
                except Exception:
                    try:
                        for _li in new_listings:
                            __import__("fbm_pg_cache").record_notification_event(
                                listing=_li,
                                user_name=user,
                                channel=_u.config.notify_with[0] if _u.config.notify_with else "unknown",
                                status="failed",
                                details={{"count": len(new_listings), "item": item_config.name}},
                                logger=self.logger,
                            )
                    except Exception:
                        pass
                    raise
            # {SENTINEL_PG_NOTIFY}
"""

    if SENTINEL_PG_OBSERVE not in text and observe_needle in text:
        text = text.replace(observe_needle, observe_block, 1)

    if SENTINEL_PG_NOTIFY not in text and notify_vanilla in text:
        text = text.replace(notify_vanilla, notify_new, 1)

    if text == original:
        if SENTINEL_PG_OBSERVE in text and SENTINEL_PG_NOTIFY in text:
            print("monitor.py: postgres hooks already patched")
            return True
        print(
            "monitor.py: postgres hook needle not found; upgrade ai-marketplace-monitor and "
            "update scripts/apply_ai_marketplace_monitor_patches.py",
            file=sys.stderr,
        )
        return False

    monitor_py.write_text(text, encoding="utf-8")
    print("monitor.py: applied postgres observe/notify hooks")
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


def patch_ai_pg(ai_py: Path) -> bool:
    """Add PostgreSQL-backed AI dedupe gate and persistence."""
    text = ai_py.read_text(encoding="utf-8")
    original = text

    cache_needle = """        prompt = self.get_prompt(listing, item_config, marketplace_config)
        res: AIResponse | None = AIResponse.from_cache(listing, item_config, marketplace_config)"""
    cache_new = f"""        prompt = self.get_prompt(listing, item_config, marketplace_config)
        # {SENTINEL_PG_AI} check PostgreSQL cache first (best effort).
        _pg_cached = None
        try:
            _pg_cached = __import__("fbm_pg_cache").get_cached_ai_response(
                listing=listing,
                model=self.config.model or self.default_model,
                prompt=prompt,
                logger=self.logger,
            )
        except Exception:
            _pg_cached = None
        if _pg_cached is not None:
            return AIResponse(
                name=str(_pg_cached.get("name") or self.config.name),
                score=int(_pg_cached["score"]),
                comment=str(_pg_cached.get("comment", "")),
            )
        res: AIResponse | None = AIResponse.from_cache(listing, item_config, marketplace_config)"""

    save_needle = """        res = AIResponse(name=self.config.name, score=score, comment=comment)
        res.to_cache(listing, item_config, marketplace_config)
        counter.increment(CounterItem.NEW_AI_QUERY, item_config.name)
        return res"""
    save_new = """        res = AIResponse(name=self.config.name, score=score, comment=comment)
        res.to_cache(listing, item_config, marketplace_config)
        try:
            __import__("fbm_pg_cache").store_ai_evaluation(
                listing=listing,
                model=self.config.model or self.default_model,
                prompt=prompt,
                score=res.score,
                conclusion=res.conclusion,
                comment=res.comment,
                logger=self.logger,
            )
        except Exception:
            pass
        counter.increment(CounterItem.NEW_AI_QUERY, item_config.name)
        return res"""

    if SENTINEL_PG_AI not in text and cache_needle in text:
        text = text.replace(cache_needle, cache_new, 1)

    if SENTINEL_PG_AI not in text and save_needle in text:
        text = text.replace(save_needle, save_new, 1)

    if text == original:
        if SENTINEL_PG_AI in text:
            print("ai.py: postgres AI dedupe already patched")
            return True
        print(
            "ai.py: postgres AI dedupe needles not found; upgrade ai-marketplace-monitor and "
            "update scripts/apply_ai_marketplace_monitor_patches.py",
            file=sys.stderr,
        )
        return False

    ai_py.write_text(text, encoding="utf-8")
    print("ai.py: applied postgres AI dedupe/persist hooks")
    return True


# Vanilla ai-marketplace-monitor facebook.py search loop fragment (0.9.x).
_FACEBOOK_SEARCH_BLOCK_OLD = (
    "                found_listings = FacebookSearchResultPage(\n"
    "                    self.page, self.translator, self.logger\n"
    "                ).get_listings()\n"
    "                time.sleep(5)\n"
    "                if self.logger:\n"
    "                    self.logger.error(\n"
    '                        f"""{hilight("[Search]", "fail")} Failed to get search results for {search_phrase} from {city}"""\n'
    "                    )\n"
    "\n"
    "                counter.increment(CounterItem.SEARCH_PERFORMED, item_config.name)"
)


def _facebook_search_block_new() -> str:
    return (
        "                found_listings = FacebookSearchResultPage(\n"
        "                    self.page, self.translator, self.logger\n"
        "                ).get_listings()\n"
        "                time.sleep(5)\n"
        f"                # {SENTINEL_FACEBOOK} (set AIMM_MANUAL_SEARCH_FALLBACK=1 to prompt when zero listings)\n"
        "                _manual_fb = (\n"
        '                    __import__("os")\n'
        '                    .environ.get("AIMM_MANUAL_SEARCH_FALLBACK", "")\n'
        "                    .strip()\n"
        "                    .lower()\n"
        '                    in ("1", "true", "yes")\n'
        "                )\n"
        "                if not found_listings and _manual_fb:\n"
        '                    _sys_fb = __import__("sys")\n'
        "                    _fb_msg = (\n"
        '                        "[Search] Parsed zero listings from the automated Marketplace URL. "\n'
        '                        f"phrase={search_phrase!r} city={city!r}. "\n'
        '                        "In the Playwright browser, run the search manually until result cards show, "\n'
        '                        "then press Enter here to re-parse the current page."\n'
        "                    )\n"
        "                    if self.logger:\n"
        "                        self.logger.warning(_fb_msg)\n"
        "                    elif _sys_fb.stdout.isatty():\n"
        '                        print("\\n" + _fb_msg + "\\n", file=_sys_fb.stderr)\n'
        "                    try:\n"
        "                        if _sys_fb.stdin.isatty():\n"
        '                            input("Press Enter after results are visible... ")\n'
        "                    except EOFError:\n"
        "                        pass\n"
        "                    found_listings = FacebookSearchResultPage(\n"
        "                        self.page, self.translator, self.logger\n"
        "                    ).get_listings()\n"
        "                    time.sleep(5)\n"
        "                if not found_listings:\n"
        "                    if self.logger:\n"
        "                        self.logger.error(\n"
        '                            f"""{hilight("[Search]", "fail")} Failed to get search results for {search_phrase} from {city}"""\n'
        "                        )\n"
        "                elif self.logger:\n"
        "                    self.logger.info(\n"
        '                        f"""{hilight("[Search]", "succ")} Got {len(found_listings)} search result(s) for {search_phrase} from {city}"""\n'
        "                    )\n"
        "\n"
        "                counter.increment(CounterItem.SEARCH_PERFORMED, item_config.name)"
    )


def patch_facebook(facebook_py: Path) -> bool:
    text = facebook_py.read_text(encoding="utf-8")
    if SENTINEL_FACEBOOK in text:
        print("facebook.py: already patched")
        return True

    old = _FACEBOOK_SEARCH_BLOCK_OLD
    new = _facebook_search_block_new()
    if old not in text:
        print(
            "facebook.py: search block not found; upgrade ai-marketplace-monitor and "
            "update scripts/apply_ai_marketplace_monitor_patches.py",
            file=sys.stderr,
        )
        return False

    facebook_py.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("facebook.py: applied manual-search + conditional search-error log")
    return True


def verify_patch_targets(root: Path) -> bool:
    """Fail fast if upstream signatures drift too far for safe patching."""
    monitor = (root / "monitor.py").read_text(encoding="utf-8")
    ai = (root / "ai.py").read_text(encoding="utf-8")
    facebook = (root / "facebook.py").read_text(encoding="utf-8")

    checks: list[tuple[bool, str]] = [
        (
            SENTINEL_MONITOR in monitor
            or "res = self.evaluate_by_ai(" in monitor
            or "rating = self.evaluate_by_ai(" in monitor,
            "monitor.py evaluate_by_ai call sites",
        ),
        (
            SENTINEL_TERMINAL_FOUND in monitor
            or "CounterItem.NEW_VALIDATED_LISTING, item_config.name, len(new_listings)" in monitor,
            "monitor.py new_listings counter block",
        ),
        (
            SENTINEL_PG_OBSERVE in monitor or "# if everyone has been notified" in monitor,
            "monitor.py listing observation insertion point",
        ),
        (
            SENTINEL_AI in ai
            or "class OpenAIConfig(AIConfig):" in ai
            or "response = self.client.chat.completions.create(" in ai,
            "ai.py OpenAI config/retry blocks",
        ),
        (
            SENTINEL_PG_AI in ai
            or "res: AIResponse | None = AIResponse.from_cache(listing, item_config, marketplace_config)"
            in ai,
            "ai.py AI cache insertion point",
        ),
        (
            SENTINEL_FACEBOOK in facebook
            or "Failed to get search results for {search_phrase} from {city}" in facebook,
            "facebook.py search parser block",
        ),
    ]
    failed = [name for ok, name in checks if not ok]
    if failed:
        print(
            "Patch verification failed. Upstream signatures changed for: "
            + ", ".join(failed)
            + ". Pin ai-marketplace-monitor to a known version or update patch script needles.",
            file=sys.stderr,
        )
        return False
    return True


def main() -> None:
    root = package_dir()
    monitor = root / "monitor.py"
    if not verify_patch_targets(root):
        sys.exit(1)
    if (
        not patch_monitor(monitor)
        or not patch_terminal_found(monitor)
        or not patch_monitor_db(monitor)
        or not patch_ai(root / "ai.py")
        or not patch_ai_pg(root / "ai.py")
        or not patch_facebook(root / "facebook.py")
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()

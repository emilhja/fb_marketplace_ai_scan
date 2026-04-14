"""Shared pytest bootstrap for local package imports and stable unit-test behavior."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DISABLE_PYNPUT", "1")
os.environ.setdefault("AIMM_DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/test_db")


class _FakeCache:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self._store: dict[object, object] = {}

    def get(self, key: object, default: object | None = None) -> object | None:
        return self._store.get(key, default)

    def set(self, key: object, value: object, tag: str | None = None) -> None:
        self._store[key] = value

    def incr(self, key: object, by: int, default: object | None = None) -> None:
        current = self._store.get(key, default)
        if current is None:
            raise KeyError(key)
        self._store[key] = int(current) + by

    def iterkeys(self):
        return iter(self._store.keys())

    def clear(self) -> None:
        self._store.clear()

    def evict(self, tag: str | None = None) -> None:
        self._store.clear()


def _install_module(name: str, module: types.SimpleNamespace) -> None:
    sys.modules.setdefault(name, module)


_install_module("diskcache", types.SimpleNamespace(Cache=_FakeCache))
_install_module("parsedatetime", types.SimpleNamespace())
_install_module("humanize", types.SimpleNamespace(naturaltime=lambda value: str(value)))
_install_module("currency_converter", types.SimpleNamespace(CurrencyConverter=object))
_install_module("openai", types.SimpleNamespace(OpenAI=object))
_install_module("rich", types.SimpleNamespace(print=print))
_install_module("rich.pretty", types.SimpleNamespace(pretty_repr=repr))
_install_module("rich.prompt", types.SimpleNamespace(Prompt=object))
_install_module("watchdog", types.SimpleNamespace())
_install_module(
    "inflect",
    types.SimpleNamespace(
        engine=lambda: types.SimpleNamespace(
            plural_noun=lambda word, count=2: word if count == 1 else f"{word}s",
            plural_verb=lambda word, count=2: word if count == 1 else "are",
        )
    ),
)
_install_module(
    "schedule",
    types.SimpleNamespace(
        Job=object,
        jobs=[],
        every=lambda *args, **kwargs: types.SimpleNamespace(
            minute=types.SimpleNamespace(
                at=lambda *_a, **_k: types.SimpleNamespace(tag=lambda *_x: None)
            ),
            hour=types.SimpleNamespace(
                at=lambda *_a, **_k: types.SimpleNamespace(tag=lambda *_x: None)
            ),
            day=types.SimpleNamespace(
                at=lambda *_a, **_k: types.SimpleNamespace(tag=lambda *_x: None)
            ),
            to=lambda *_a, **_k: types.SimpleNamespace(
                seconds=types.SimpleNamespace(tag=lambda *_x: None)
            ),
            hours=types.SimpleNamespace(
                do=lambda *_a, **_k: types.SimpleNamespace(tag=lambda *_x: None)
            ),
        ),
        get_jobs=lambda: [],
        clear=lambda: None,
        idle_seconds=lambda: 0,
        run_pending=lambda: None,
    ),
)
_install_module(
    "jinja2",
    types.SimpleNamespace(
        Environment=object,
        FileSystemLoader=object,
        select_autoescape=lambda *args, **kwargs: None,
    ),
)
_install_module("pushbullet", types.SimpleNamespace(Pushbullet=object))
_install_module(
    "watchdog.events",
    types.SimpleNamespace(FileSystemEvent=object, FileSystemEventHandler=object),
)
_install_module("watchdog.observers", types.SimpleNamespace(Observer=object))
_install_module(
    "playwright.sync_api",
    types.SimpleNamespace(
        Browser=object,
        ElementHandle=object,
        Locator=object,
        Page=object,
        Playwright=object,
        ProxySettings=object,
        sync_playwright=lambda: None,
    ),
)
_install_module("playwright", types.SimpleNamespace(sync_api=sys.modules["playwright.sync_api"]))

from __future__ import annotations

import re

from ..schemas import LatestAIEval

GPU_HINT_RE = re.compile(
    r"\b("
    r"rtx|gtx|rx\s?\d|radeon|geforce|nvidia|amd|arc|intel\s+arc|gpu|grafikkort|graphics card|video card"
    r")\b",
    re.IGNORECASE,
)
GB_RE = re.compile(
    r"\b(\d{1,2})\s*(?:gb|g(?:b)?|gig(?:abyte)?s?)\b",
    re.IGNORECASE,
)
VRAM_CONTEXT_RE = re.compile(
    r"\b(vram|video memory|graphics memory|gpu memory|grafikminne|minne på grafikkort)\b",
    re.IGNORECASE,
)


def infer_vram(title: str, description: str, ai: LatestAIEval | None) -> str | None:
    ai_text = " ".join(
        part for part in ((ai.comment if ai else None), (ai.conclusion if ai else None)) if part
    )
    texts = [
        ("title", title or ""),
        ("description", description or ""),
        ("ai", ai_text),
    ]

    exact_matches: list[int] = []
    tentative_matches: list[int] = []

    for source, text in texts:
        if not text:
            continue
        gpu_hint = bool(GPU_HINT_RE.search(text))
        for match in GB_RE.finditer(text):
            amount = int(match.group(1))
            if amount <= 1 or amount > 48:
                continue

            start = max(0, match.start() - 24)
            end = min(len(text), match.end() + 24)
            window = text[start:end]
            if VRAM_CONTEXT_RE.search(window):
                exact_matches.append(amount)
                continue

            if source in {"title", "ai"} and gpu_hint:
                tentative_matches.append(amount)

    if exact_matches:
        return f"{exact_matches[0]} GB"
    if tentative_matches:
        return f"{tentative_matches[0]} GB?"
    return None

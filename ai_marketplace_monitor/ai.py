"""AI response parsing and backend abstractions for listing evaluation."""

import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from logging import Logger
from typing import Any, ClassVar, Generic, Optional, Type, TypeVar

from diskcache import Cache  # type: ignore
from openai import OpenAI  # type: ignore
from rich.pretty import pretty_repr

from .listing import Listing
from .marketplace import TItemConfig, TMarketplaceConfig
from .pg_cache import get_cached_ai_response, store_ai_evaluation, store_ai_evaluation_if_absent
from .utils import BaseConfig, CacheType, CounterItem, cache, counter, hilight

# Parsed from model "Form:" line; persisted as ai_evaluations.listing_kind
_FORM_LINE_RE = re.compile(
    r"(?im)^\s*Form:\s*(complete_pc|gpu_only|other|unknown)\s*$",
)
# Remove any "Form: …" line from the body so invalid labels do not leak into the comment.
_FORM_ANY_LINE_RE = re.compile(r"(?im)^\s*Form:.*$")


def parse_listing_kind(answer: str) -> str:
    """Extract the optional `Form:` classification from a model completion."""
    m = _FORM_LINE_RE.search(answer or "")
    if not m:
        return "unknown"
    return m.group(1).lower()


def _strip_form_lines(text: str) -> str:
    """Remove `Form:` metadata lines before comment parsing."""
    return _FORM_ANY_LINE_RE.sub("", text).strip()


def parse_ai_rating_response(answer: str | None) -> Optional[tuple[int, str, str]]:
    """Extract score 0–5, comment, and listing_kind from a model completion. None if no valid Rating line."""
    if answer is None or not str(answer).strip():
        return None
    listing_kind = parse_listing_kind(answer)
    answer = _strip_form_lines(answer)
    if re.search(r"Rating[^0-5]*[0-5]", answer, re.DOTALL) is None:
        return None
    lines = answer.split("\n")
    score = 1
    comment = ""
    rating_line: int | None = None
    for idx, line in enumerate(lines):
        matched = re.match(r".*Rating[^0-5]*([0-5])[:\s]*(.*)", line)
        if matched:
            score = int(matched.group(1))
            comment = matched.group(2).strip()
            rating_line = idx
            continue
        if rating_line is not None:
            comment += " " + line
    if len(comment.strip()) < 5 and rating_line is not None and rating_line > 0:
        comment = lines[rating_line - 1]
    comment = " ".join([x for x in comment.split() if x.strip()]).strip()
    return score, comment, listing_kind


_SCORE_TO_CONCLUSION: dict[int, str] = {
    0: "Missing required data",
    1: "No match",
    2: "Potential match",
    3: "Poor match",
    4: "Good match",
    5: "Great deal",
}


class AIServiceProvider(Enum):
    OPENAI = "OpenAI"
    DEEPSEEK = "DeepSeek"
    OLLAMA = "Ollama"


@dataclass
class AIResponse:
    """Normalized AI evaluation returned by a configured backend."""

    score: int
    comment: str
    name: str = ""
    # Provider-reported model id for this completion (e.g. OpenRouter routed model for `openrouter/free`).
    response_model: str | None = None
    # complete_pc | gpu_only | other | unknown — from model "Form:" line when enabled by prompt
    listing_kind: str = "unknown"

    NOT_EVALUATED: ClassVar = "Not evaluated by AI"

    @property
    def conclusion(self: "AIResponse") -> str:
        """Map the numeric score to a stable human-readable verdict."""
        return _SCORE_TO_CONCLUSION.get(self.score, "Unknown rating")

    @property
    def style(self: "AIResponse") -> str:
        """Return the log/display style associated with the response score."""
        if self.comment == self.NOT_EVALUATED:
            return "dim"
        if self.score < 3:
            return "fail"
        if self.score > 3:
            return "succ"
        return "name"

    @property
    def stars(self: "AIResponse") -> str:
        """Render the score as five HTML stars for email notifications."""
        full_stars = self.score
        empty_stars = 5 - full_stars
        return (
            '<span style="color: #FFD700; font-size: 20px;">★</span>' * full_stars
            + '<span style="color: #D3D3D3; font-size: 20px;">☆</span>' * empty_stars
        )

    @classmethod
    def from_cache(
        cls: Type["AIResponse"],
        listing: Listing,
        item_config: TItemConfig,
        marketplace_config: TMarketplaceConfig,
        local_cache: Cache | None = None,
    ) -> Optional["AIResponse"]:
        res = (cache if local_cache is None else local_cache).get(
            (CacheType.AI_INQUIRY.value, item_config.hash, marketplace_config.hash, listing.hash)
        )
        if res is None:
            return None
        data = dict(res)
        data.setdefault("response_model", None)
        data.setdefault("listing_kind", "unknown")
        return AIResponse(**data)

    def to_cache(
        self: "AIResponse",
        listing: Listing,
        item_config: TItemConfig,
        marketplace_config: TMarketplaceConfig,
        local_cache: Cache | None = None,
    ) -> None:
        (cache if local_cache is None else local_cache).set(
            (CacheType.AI_INQUIRY.value, item_config.hash, marketplace_config.hash, listing.hash),
            asdict(self),
            tag=CacheType.AI_INQUIRY.value,
        )


@dataclass
class AIConfig(BaseConfig):
    """Base configuration shared by all AI providers."""

    # this argument is required

    api_key: str | None = None
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    max_retries: int = 10
    timeout: int | None = None

    def handle_provider(self: "AIConfig") -> None:
        if self.provider is None:
            return
        if self.provider.lower() not in [x.value.lower() for x in AIServiceProvider]:
            raise ValueError(
                f"""AIConfig requires a valid service provider. Valid providers are {hilight(", ".join([x.value for x in AIServiceProvider]))}"""
            )

    def handle_api_key(self: "AIConfig") -> None:
        if self.api_key is None:
            return
        if not isinstance(self.api_key, str):
            raise ValueError("AIConfig requires a string api_key.")
        self.api_key = self.api_key.strip()

    def handle_max_retries(self: "AIConfig") -> None:
        if not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise ValueError("AIConfig requires a positive integer max_retries.")

    def handle_timeout(self: "AIConfig") -> None:
        if self.timeout is None:
            return
        if not isinstance(self.timeout, int) or self.timeout < 0:
            raise ValueError("AIConfig requires a positive integer timeout.")


@dataclass
class OpenAIConfig(AIConfig):
    def handle_api_key(self: "OpenAIConfig") -> None:
        if self.api_key is None:
            raise ValueError("OpenAI requires a string api_key.")
        if not isinstance(self.api_key, str):
            raise ValueError("OpenAI requires a string api_key.")
        self.api_key = self.api_key.strip()
        if not self.api_key:
            raise ValueError(
                "api_key is empty (often OPENROUTER_API_KEY missing or blank in the process "
                "environment). Put sk-or-v1-... in .env and start with ./run.sh, or set the key "
                "directly in config.toml without ${...}."
            )


@dataclass
class DeekSeekConfig(OpenAIConfig):
    pass


@dataclass
class OllamaConfig(OpenAIConfig):
    api_key: str | None = field(default="ollama")  # required but not used.

    def handle_base_url(self: "OllamaConfig") -> None:
        if self.base_url is None:
            raise ValueError("Ollama requires a string base_url.")

    def handle_model(self: "OllamaConfig") -> None:
        if self.model is None:
            raise ValueError("Ollama requires a string model.")


TAIConfig = TypeVar("TAIConfig", bound=AIConfig)


class AIBackend(Generic[TAIConfig]):
    """Base AI backend interface used by the Marketplace monitor."""

    def __init__(self: "AIBackend", config: AIConfig, logger: Logger | None = None) -> None:
        self.config = config
        self.logger = logger
        self.client: OpenAI | None = None

    @classmethod
    def get_config(cls: Type["AIBackend"], **kwargs: Any) -> TAIConfig:
        raise NotImplementedError("get_config method must be implemented by subclasses.")

    def connect(self: "AIBackend") -> None:
        raise NotImplementedError("Connect method must be implemented by subclasses.")

    def get_prompt(
        self: "AIBackend",
        listing: Listing,
        item_config: TItemConfig,
        marketplace_config: TMarketplaceConfig,
    ) -> str:
        prompt = (
            f"""A user wants to buy a {item_config.name} from Facebook Marketplace. """
            f"""Search phrases: "{'" and "'.join(item_config.search_phrases)}", """
        )
        if item_config.description:
            prompt += f"""Description: "{item_config.description}", """
        #
        max_price = item_config.max_price or 0
        min_price = item_config.min_price or 0
        if max_price and min_price:
            prompt += f"""Price range: {min_price} to {max_price}. """
        elif max_price:
            prompt += f"""Max price {max_price}. """
        elif min_price:
            prompt += f"""Min price {min_price}. """
        #
        if item_config.antikeywords:
            prompt += f"""Exclude keywords "{'" and "'.join(item_config.antikeywords)}" in title or description."""
        #
        price_clause = (
            f"{listing.price} (originally listed at {listing.original_price})"
            if listing.original_price
            else listing.price
        )
        prompt += (
            f"""\n\nThe user found a listing titled "{listing.title}" in {listing.condition} condition, """
            f"""priced at {price_clause}, located in {listing.location}, """
            f"""posted at {listing.post_url} with description "{listing.description}"\n\n"""
        )
        # prompt
        if item_config.prompt is not None:
            prompt += item_config.prompt
        elif marketplace_config.prompt is not None:
            prompt += marketplace_config.prompt
        else:
            prompt += (
                "Evaluate how well this listing matches the user's criteria. Assess the description, MSRP, model year, "
                "condition, and seller's credibility."
            )
        # extra_prompt
        prompt += "\n"
        if item_config.extra_prompt is not None:
            prompt += f"\n{item_config.extra_prompt.strip()}\n"
        elif marketplace_config.extra_prompt is not None:
            prompt += f"\n{marketplace_config.extra_prompt.strip()}\n"
        # rating_prompt
        if item_config.rating_prompt is not None:
            prompt += f"\n{item_config.rating_prompt.strip()}\n"
        elif marketplace_config.rating_prompt is not None:
            prompt += f"\n{marketplace_config.rating_prompt.strip()}\n"
        else:
            prompt += (
                "\nRate from 0 to 5 based on the following: \n"
                "0 - Missing required data: Hard requirements from the user's criteria cannot be verified because "
                "they are absent from the title and description (e.g. VRAM in GB for a GPU listing). Do not guess; "
                "state clearly which required facts are missing.\n"
                "1 - No match: Wrong item/category/brand, suspicious activity (e.g. external links), or clearly excluded.\n"
                "2 - Potential match: Partial info; needs seller clarification but not a missing hard requirement.\n"
                "3 - Poor match: Some mismatches or weak details; acceptable but not ideal.\n"
                "4 - Good match: Mostly meets criteria with clear, relevant details.\n"
                "5 - Great deal: Fully matches criteria, with excellent condition or price.\n"
                "Conclude with:\n"
                '"Rating <0-5>: <summary>"\n'
                "where <0-5> is the rating and <summary> is a brief recommendation (max 30 words)."
            )
        prompt += (
            "\n\nAfter the Rating line, add one more line on its own (exact keyword Form, lowercase value):\n"
            "Form: complete_pc | gpu_only | other | unknown\n"
            "- complete_pc: full desktop / workstation / prebuilt / barebones sold as a working PC.\n"
            "- gpu_only: standalone desktop graphics card (GPU alone is the main item).\n"
            "- other: laptop, console, accessory-only lots, or none of the above fit.\n"
            "- unknown: not enough in the title/description to classify.\n"
        )
        if self.logger:
            self.logger.debug(f"""{hilight("[AI-Prompt]", "info")} {prompt}""")
        return prompt

    def evaluate(
        self: "AIBackend",
        listing: Listing,
        item_config: TItemConfig,
        marketplace_config: TMarketplaceConfig,
    ) -> AIResponse:
        raise NotImplementedError("Confirm method must be implemented by subclasses.")


class OpenAIBackend(AIBackend):
    default_model = "gpt-4o"
    # the default is f"https://api.openai.com/v1"
    base_url: str | None = None

    @classmethod
    def get_config(cls: Type["OpenAIBackend"], **kwargs: Any) -> OpenAIConfig:
        return OpenAIConfig(**kwargs)

    def connect(self: "OpenAIBackend") -> None:
        if self.client is None:
            self.client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or self.base_url,
                timeout=self.config.timeout,
                default_headers={
                    "X-Title": "AI Marketplace Monitor",
                    "HTTP-Referer": "https://github.com/BoPeng/ai-marketplace-monitor",
                },
            )
            if self.logger:
                self.logger.info(f"""{hilight("[AI]", "name")} {self.config.name} connected.""")

    def evaluate(
        self: "OpenAIBackend",
        listing: Listing,
        item_config: TItemConfig,
        marketplace_config: TMarketplaceConfig,
    ) -> AIResponse:
        # ask openai to confirm the item is correct
        counter.increment(CounterItem.AI_QUERY, item_config.name)
        prompt = self.get_prompt(listing, item_config, marketplace_config)
        pg_cached = get_cached_ai_response(
            listing=listing,
            model=self.config.model or self.default_model,
            prompt=prompt,
            item_config_hash=item_config.hash,
            marketplace_config_hash=marketplace_config.hash,
            logger=self.logger,
        )
        if pg_cached is not None:
            return AIResponse(
                name=self.config.name,
                score=pg_cached.score,
                comment=pg_cached.comment,
                response_model=pg_cached.response_model,
                listing_kind=pg_cached.listing_kind,
            )
        res: AIResponse | None = AIResponse.from_cache(listing, item_config, marketplace_config)
        if res is not None:
            if self.logger:
                self.logger.debug(
                    f"""{hilight("[AI]", res.style)} {self.config.name} previously concluded {hilight(f"{res.conclusion} ({res.score}): {res.comment}", res.style)} for listing {hilight(listing.title)}."""
                )
            # Disk cache hit skips the API branch below, so PostgreSQL would never get a row; backfill when enabled.
            store_ai_evaluation_if_absent(
                listing=listing,
                model=self.config.model or self.default_model,
                prompt=prompt,
                item_config_hash=item_config.hash,
                marketplace_config_hash=marketplace_config.hash,
                score=res.score,
                conclusion=res.conclusion,
                comment=res.comment,
                response_model=res.response_model,
                listing_kind=res.listing_kind,
                logger=self.logger,
            )
            return res

        self.connect()

        retries = 0
        response = None
        last_error: Exception | None = None
        while retries < self.config.max_retries:
            self.connect()
            assert self.client is not None
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model or self.default_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that can confirm if a user's search criteria matches the item he is interested in.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    stream=False,
                )
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:
                last_error = e
                if self.logger:
                    self.logger.error(
                        f"""{hilight("[AI-Error]", "fail")} {self.config.name} failed to evaluate {hilight(listing.title)}: {e}"""
                    )
                retries += 1
                # try to initiate a connection
                self.client = None
                time.sleep(5)

        if response is None:
            counter.increment(CounterItem.FAILED_AI_QUERY, item_config.name)
            hint = (
                " Check OPENROUTER_API_KEY is set and non-empty in the same environment as the monitor."
                if last_error and "401" in str(last_error)
                else ""
            )
            raise ValueError(
                f"No response from {self.config.name} after {self.config.max_retries} attempts.{hint} Last error: {last_error!r}"
            )

        # check if the response is yes
        if self.logger:
            self.logger.debug(f"""{hilight("[AI-Response]", "info")} {pretty_repr(response)}""")

        resolved_model = getattr(response, "model", None) or None
        if isinstance(resolved_model, str) and not resolved_model.strip():
            resolved_model = None

        answer = response.choices[0].message.content or ""
        parsed = parse_ai_rating_response(answer)
        if parsed is None:
            counter.increment(CounterItem.FAILED_AI_QUERY, item_config.name)
            raise ValueError(f"Empty or invalid response from {self.config.name}: {response}")

        score, comment, listing_kind = parsed
        res = AIResponse(
            name=self.config.name,
            score=score,
            comment=comment,
            response_model=resolved_model,
            listing_kind=listing_kind,
        )
        res.to_cache(listing, item_config, marketplace_config)
        store_ai_evaluation(
            listing=listing,
            model=self.config.model or self.default_model,
            prompt=prompt,
            item_config_hash=item_config.hash,
            marketplace_config_hash=marketplace_config.hash,
            score=res.score,
            conclusion=res.conclusion,
            comment=res.comment,
            response_model=resolved_model,
            listing_kind=res.listing_kind,
            logger=self.logger,
        )
        counter.increment(CounterItem.NEW_AI_QUERY, item_config.name)
        return res


class DeepSeekBackend(OpenAIBackend):
    default_model = "deepseek-chat"
    base_url = "https://api.deepseek.com"

    @classmethod
    def get_config(cls: Type["DeepSeekBackend"], **kwargs: Any) -> DeekSeekConfig:
        return DeekSeekConfig(**kwargs)


class OllamaBackend(OpenAIBackend):
    default_model = "deepseek-r1:14b"

    @classmethod
    def get_config(cls: Type["OllamaBackend"], **kwargs: Any) -> OllamaConfig:
        return OllamaConfig(**kwargs)

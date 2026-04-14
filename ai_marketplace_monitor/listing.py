"""Listing model and disk cache helpers used by the Marketplace scanner."""

from dataclasses import asdict, dataclass
from typing import Optional, Tuple, Type

from diskcache import Cache  # type: ignore

from .utils import CacheType, cache, hash_dict


@dataclass
class Listing:
    """Normalized representation of one Marketplace listing."""

    marketplace: str
    name: str
    # unique identification
    id: str
    title: str
    image: str
    price: str
    post_url: str
    location: str
    seller: str
    condition: str
    description: str
    availability: str = "Till Salu"
    is_tradera: bool = False
    # crossed-out / "was" price when the UI shows two amounts (normalized digits, same as price)
    original_price: str = ""

    @property
    def content(self: "Listing") -> Tuple[str, str, str]:
        """Return the text fields that drive AI evaluation and cache invalidation."""
        return (self.title, self.description, self.price)

    @property
    def hash(self: "Listing") -> str:
        """Return a stable listing hash that ignores image churn and URL query strings."""
        # we need to normalize post_url before hashing because post_url will be different
        # each time from a search page. We also does not count image
        return hash_dict(
            {
                x: (y.split("?")[0] if x == "post_url" else y)
                for x, y in asdict(self).items()
                if x != "image"
            }
        )

    @classmethod
    def from_cache(
        cls: Type["Listing"],
        post_url: str,
        local_cache: Cache | None = None,
    ) -> Optional["Listing"]:
        """Load a cached listing snapshot when present and structurally compatible."""
        try:
            # details could be a different datatype, miss some key etc.
            # and we have recently changed to save Listing as a dictionary
            return cls(
                **(cache if local_cache is None else local_cache).get(
                    (CacheType.LISTING_DETAILS.value, post_url.split("?")[0])
                )
            )
        except KeyboardInterrupt:
            raise
        except Exception:
            return None

    def to_cache(
        self: "Listing",
        post_url: str,
        local_cache: Cache | None = None,
    ) -> None:
        """Persist the normalized listing payload in the local disk cache."""
        (cache if local_cache is None else local_cache).set(
            (CacheType.LISTING_DETAILS.value, post_url.split("?")[0]),
            asdict(self),
            tag=CacheType.LISTING_DETAILS.value,
        )

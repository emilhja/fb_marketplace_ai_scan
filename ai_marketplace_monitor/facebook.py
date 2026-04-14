import datetime
import html
import os
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from itertools import repeat
from logging import Logger
from typing import Any, Generator, List, Tuple, Type, cast
from urllib.parse import quote

import humanize
from currency_converter import CurrencyConverter  # type: ignore
from playwright.sync_api import Browser, ElementHandle, Locator, Page  # type: ignore
from rich.pretty import pretty_repr

from .listing import Listing
from .marketplace import ItemConfig, Marketplace, MarketplaceConfig, WebPage
from .pg_cache import should_skip_stable_detail_fetch
from .utils import (
    BaseConfig,
    CounterItem,
    KeyboardMonitor,
    Translator,
    convert_to_seconds,
    counter,
    doze,
    hilight,
    parse_listing_prices,
    is_substring,
)


class Condition(Enum):
    NEW = "new"
    USED_LIKE_NEW = "used_like_new"
    USED_GOOD = "used_good"
    USED_FAIR = "used_fair"


class DateListed(Enum):
    ANYTIME = 0
    PAST_24_HOURS = 1
    PAST_WEEK = 7
    PAST_MONTH = 30


class DeliveryMethod(Enum):
    LOCAL_PICK_UP = "local_pick_up"
    SHIPPING = "shipping"
    ALL = "all"


class Availability(Enum):
    ALL = "all"
    INSTOCK = "in"
    OUTSTOCK = "out"


class Category(Enum):
    VEHICLES = "vehicles"
    PROPERTY_RENTALS = "propertyrentals"
    APPAREL = "apparel"
    ELECTRONICS = "electronics"
    ENTERTAINMENT = "entertainment"
    FAMILY = "family"
    FREE_STUFF = "freestuff"
    FREE = "free"
    GARDEN = "garden"
    HOBBIES = "hobbies"
    HOME_GOODS = "homegoods"
    HOME_IMPROVEMENT = "homeimprovement"
    HOME_SALES = "homesales"
    MUSICAL_INSTRUMENTS = "musicalinstruments"
    OFFICE_SUPPLIES = "officesupplies"
    PET_SUPPLIES = "petsupplies"
    SPORTING_GOODS = "sportinggoods"
    TICKETS = "tickets"
    TOYS = "toys"
    VIDEO_GAMES = "videogames"


@dataclass
class FacebookMarketItemCommonConfig(BaseConfig):
    """Item options that can be defined in marketplace

    This class defines and processes options that can be specified
    in both marketplace and item sections, specific to facebook marketplace
    """

    seller_locations: List[str] | None = None
    availability: List[str] | None = None
    condition: List[str] | None = None
    date_listed: List[int] | None = None
    delivery_method: List[str] | None = None
    category: str | None = None

    def handle_seller_locations(self: "FacebookMarketItemCommonConfig") -> None:
        if self.seller_locations is None:
            return

        if isinstance(self.seller_locations, str):
            self.seller_locations = [self.seller_locations]
        if not isinstance(self.seller_locations, list) or not all(
            isinstance(x, str) for x in self.seller_locations
        ):
            raise ValueError(f"Item {hilight(self.name)} seller_locations must be a list.")

    def handle_availability(self: "FacebookMarketItemCommonConfig") -> None:
        if self.availability is None:
            return

        if isinstance(self.availability, str):
            self.availability = [self.availability]
        if not all(val in [x.value for x in Availability] for val in self.availability):
            raise ValueError(
                f"Item {hilight(self.name)} availability must be one or two values of 'all', 'in', and 'out'."
            )
        if len(self.availability) > 2:
            raise ValueError(
                f"Item {hilight(self.name)} availability must be one or two values of 'all', 'in', and 'out'."
            )

    def handle_condition(self: "FacebookMarketItemCommonConfig") -> None:
        if self.condition is None:
            return
        if isinstance(self.condition, Condition):
            self.condition = [self.condition]
        if not isinstance(self.condition, list) or not all(
            isinstance(x, str) and x in [cond.value for cond in Condition] for x in self.condition
        ):
            raise ValueError(
                f"Item {hilight(self.name)} condition must be one or more of that can be one of 'new', 'used_like_new', 'used_good', 'used_fair'."
            )

    def handle_date_listed(self: "FacebookMarketItemCommonConfig") -> None:
        if self.date_listed is None:
            return
        if not isinstance(self.date_listed, list):
            self.date_listed = [self.date_listed]
        #
        new_values: List[int] = []
        for val in self.date_listed:
            if isinstance(val, str):
                if val.isdigit():
                    new_values.append(int(val))
                elif val.lower() == "all":
                    new_values.append(DateListed.ANYTIME.value)
                elif val.lower() == "last 24 hours":
                    new_values.append(DateListed.PAST_24_HOURS.value)
                elif val.lower() == "last 7 days":
                    new_values.append(DateListed.PAST_WEEK.value)
                elif val.lower() == "last 30 days":
                    new_values.append(DateListed.PAST_MONTH.value)
                else:
                    raise ValueError(
                        f"""Item {hilight(self.name)} date_listed must be one of 1, 7, and 30, or All, Last 24 hours, Last 7 days, Last 30 days.: {self.date_listed} provided."""
                    )
            elif isinstance(val, (int, float)):
                if int(val) not in [x.value for x in DateListed]:
                    raise ValueError(
                        f"""Item {hilight(self.name)} date_listed must be one of 1, 7, and 30, or All, Last 24 hours, Last 7 days, Last 30 days.: {self.date_listed} provided."""
                    )
                new_values.append(int(val))
            else:
                raise ValueError(
                    f"""Item {hilight(self.name)} date_listed must be one of 1, 7, and 30, or All, Last 24 hours, Last 7 days, Last 30 days.: {self.date_listed} provided."""
                )
        # new_values should have length 1 or 2
        if len(new_values) > 2:
            raise ValueError(
                f"""Item {hilight(self.name)} date_listed must have one or two values."""
            )
        self.date_listed = new_values

    def handle_delivery_method(self: "FacebookMarketItemCommonConfig") -> None:
        if self.delivery_method is None:
            return

        if isinstance(self.delivery_method, str):
            self.delivery_method = [self.delivery_method]

        if len(self.delivery_method) > 2:
            raise ValueError(
                f"Item {hilight(self.name)} delivery_method must be one or two values of 'local_pick_up' and 'shipping'."
            )

        if not isinstance(self.delivery_method, list) or not all(
            val in [x.value for x in DeliveryMethod] for val in self.delivery_method
        ):
            raise ValueError(
                f"Item {hilight(self.name)} delivery_method must be one of 'local_pick_up' and 'shipping'."
            )

    def handle_category(self: "FacebookMarketItemCommonConfig") -> None:
        if self.category is None:
            return

        if not isinstance(self.category, str) or self.category not in [x.value for x in Category]:
            raise ValueError(
                f"Item {hilight(self.name)} category must be one of {', '.join(x.value for x in Category)}."
            )


@dataclass
class FacebookMarketplaceConfig(MarketplaceConfig, FacebookMarketItemCommonConfig):
    """Options specific to facebook marketplace

    This class defines and processes options that can be specified
    in the marketplace.facebook section only. None of the options are required.
    """

    login_wait_time: int | None = None
    password: str | None = None
    username: str | None = None

    def handle_username(self: "FacebookMarketplaceConfig") -> None:
        if self.username is None:
            return

        if not isinstance(self.username, str):
            raise ValueError(f"Marketplace {self.name} username must be a string.")

    def handle_password(self: "FacebookMarketplaceConfig") -> None:
        if self.password is None:
            return

        if not isinstance(self.password, str):
            raise ValueError(f"Marketplace {self.name} password must be a string.")

    def handle_login_wait_time(self: "FacebookMarketplaceConfig") -> None:
        if self.login_wait_time is None:
            return
        if isinstance(self.login_wait_time, str):
            try:
                self.login_wait_time = convert_to_seconds(self.login_wait_time)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                raise ValueError(
                    f"Marketplace {self.name} login_wait_time {self.login_wait_time} is not recognized."
                ) from e
        if not isinstance(self.login_wait_time, int) or self.login_wait_time < 0:
            raise ValueError(
                f"Marketplace {self.name} login_wait_time should be a non-negative number."
            )


@dataclass
class FacebookItemConfig(ItemConfig, FacebookMarketItemCommonConfig):
    pass


class FacebookMarketplace(Marketplace):
    initial_url = "https://www.facebook.com/login/device-based/regular/login/"

    name = "facebook"

    def __init__(
        self: "FacebookMarketplace",
        name: str,
        browser: Browser | None,
        keyboard_monitor: KeyboardMonitor | None = None,
        logger: Logger | None = None,
    ) -> None:
        assert name == self.name
        super().__init__(name, browser, keyboard_monitor, logger)
        self.page: Page | None = None

    @classmethod
    def get_config(cls: Type["FacebookMarketplace"], **kwargs: Any) -> FacebookMarketplaceConfig:
        return FacebookMarketplaceConfig(**kwargs)

    @classmethod
    def get_item_config(cls: Type["FacebookMarketplace"], **kwargs: Any) -> FacebookItemConfig:
        return FacebookItemConfig(**kwargs)

    def login(self: "FacebookMarketplace") -> None:
        assert self.browser is not None

        self.page = self.create_page(swap_proxy=True)

        # Navigate to the URL, no timeout
        self.goto_url(self.initial_url)

        if self.logger:
            self.logger.debug("[Login] Checking for cookie consent pop-up...")
        try:
            allow_button_locator = self.page.get_by_role(
                "button",
                name=re.compile(r"Allow all cookies|Allow cookies|Accept All", re.IGNORECASE),
            )

            if allow_button_locator.is_visible():
                allow_button_locator.click()
                self.page.wait_for_timeout(2000)  # 2 seconds
                if self.logger:
                    self.logger.debug(
                        f"""{hilight("[Login]", "succ")} Allow all cookies' button clicked."""
                    )
            elif self.logger:
                self.logger.debug(
                    f"{hilight('[Login]', 'succ')} Cookie consent pop-up not found or not visible within timeout."
                )
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"{hilight('[Login]', 'fail')} Could not handle cookie pop-up (or it was not present): {e!s}"
                )

        self.config: FacebookMarketplaceConfig
        try:
            if self.config.username:
                time.sleep(2)
                selector = self.page.wait_for_selector('input[name="email"]')
                if selector is not None:
                    selector.type(self.config.username, delay=250)
            if self.config.password:
                time.sleep(2)
                selector = self.page.wait_for_selector('input[name="pass"]')
                if selector is not None:
                    selector.type(self.config.password, delay=250)
            if self.config.username and self.config.password:
                time.sleep(2)
                selector = self.page.wait_for_selector('button[name="login"]')
                if selector is not None:
                    selector.click()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(f"""{hilight("[Login]", "fail")} {e}""")

        # in case there is a need to enter additional information
        login_wait_time = 60 if self.config.login_wait_time is None else self.config.login_wait_time
        if login_wait_time > 0:
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Login]", "info")} Waiting {humanize.naturaldelta(login_wait_time)}"""
                    + (
                        f""" or press {hilight("Esc")} when you are ready."""
                        if self.keyboard_monitor is not None
                        else ""
                    )
                )
            doze(login_wait_time, keyboard_monitor=self.keyboard_monitor)

    def search(
        self: "FacebookMarketplace", item_config: FacebookItemConfig
    ) -> Generator[Listing, None, None]:
        if not self.page:
            self.login()
            assert self.page is not None

        options = []

        condition = item_config.condition or self.config.condition
        if condition:
            options.append(f"itemCondition={'%2C'.join(condition)}")

        # availability can take values from item_config, or marketplace config and will
        # use the first or second value depending on how many times the item has been searched.
        if item_config.date_listed:
            date_listed = item_config.date_listed[0 if item_config.searched_count == 0 else -1]
        elif self.config.date_listed:
            date_listed = self.config.date_listed[0 if item_config.searched_count == 0 else -1]
        else:
            date_listed = DateListed.ANYTIME.value
        if date_listed is not None and date_listed != DateListed.ANYTIME.value:
            options.append(f"daysSinceListed={date_listed}")

        # delivery_method can take values from item_config, or marketplace config and will
        # use the first or second value depending on how many times the item has been searched.
        if item_config.delivery_method:
            delivery_method = item_config.delivery_method[
                0 if item_config.searched_count == 0 else -1
            ]
        elif self.config.delivery_method:
            delivery_method = self.config.delivery_method[
                0 if item_config.searched_count == 0 else -1
            ]
        else:
            delivery_method = DeliveryMethod.ALL.value
        if delivery_method is not None and delivery_method != DeliveryMethod.ALL.value:
            options.append(f"deliveryMethod={delivery_method}")

        # availability can take values from item_config, or marketplace config and will
        # use the first or second value depending on how many times the item has been searched.
        if item_config.availability:
            availability = item_config.availability[0 if item_config.searched_count == 0 else -1]
        elif self.config.availability:
            availability = self.config.availability[0 if item_config.searched_count == 0 else -1]
        else:
            availability = Availability.ALL.value
        if availability is not None and availability != Availability.ALL.value:
            options.append(f"availability={availability}")

        # search multiple keywords and cities
        # there is a small chance that search by different keywords and city will return the same items.
        found = {}
        search_city = item_config.search_city or self.config.search_city or []
        city_name = item_config.city_name or self.config.city_name or []
        radiuses = item_config.radius or self.config.radius
        currencies = item_config.currency or self.config.currency

        # this should not happen because `Config.validate_items` has checked this
        if not search_city:
            if self.logger:
                self.logger.error(
                    f"""{hilight("[Search]", "fail")} No search city provided for {item_config.name}"""
                )
        # increase the searched_count to differentiate first and subsequent searches
        item_config.searched_count += 1
        for city, cname, radius, currency in zip(
            search_city,
            repeat(None) if city_name is None else city_name,
            repeat(None) if radiuses is None else radiuses,
            repeat(None) if currencies is None else currencies,
        ):
            marketplace_url = f"https://www.facebook.com/marketplace/{city}/search?"

            if radius:
                # avoid specifying radius more than once
                if options and options[-1].startswith("radius"):
                    options.pop()
                options.append(f"radius={radius}")

            max_price = item_config.max_price or self.config.max_price
            if max_price:
                if max_price.isdigit():
                    options.append(f"maxPrice={max_price}")
                else:
                    price, cur = max_price.split(" ", 1)
                    if currency and cur != currency:
                        c = CurrencyConverter()
                        price = str(int(c.convert(int(price), cur, currency)))
                        if self.logger:
                            self.logger.debug(
                                f"""{hilight("[Search]", "info")} Converting price {max_price} {cur} to {price} {currency}"""
                            )
                    options.append(f"maxPrice={price}")

            min_price = item_config.min_price or self.config.min_price
            if min_price:
                if min_price.isdigit():
                    options.append(f"minPrice={min_price}")
                else:
                    price, cur = min_price.split(" ", 1)
                    if currency and cur != currency:
                        c = CurrencyConverter()
                        price = str(int(c.convert(int(price), cur, currency)))
                        if self.logger:
                            self.logger.debug(
                                f"""{hilight("[Search]", "info")} Converting price {max_price} {cur} to {price} {currency}"""
                            )
                    options.append(f"minPrice={price}")

            category = item_config.category or self.config.category
            if category:
                options.append(f"category={category}")
                if category == Category.FREE_STUFF.value or category == Category.FREE.value:
                    # find min_price= and max_price= in options and remove them
                    options = [
                        x
                        for x in options
                        if not x.startswith("minPrice=") and not x.startswith("maxPrice=")
                    ]

            for search_phrase in item_config.search_phrases:
                if self.logger:
                    self.logger.info(
                        f"""{hilight("[Search]", "info")} Searching {item_config.marketplace} for """
                        f"""{hilight(item_config.name)} from {hilight(cname or city)}"""
                        + (f" with radius={radius}" if radius else " with default radius")
                    )

                self.goto_url(
                    marketplace_url + "&".join([f"query={quote(search_phrase)}", *options])
                )

                found_listings = FacebookSearchResultPage(
                    self.page, self.translator, self.logger
                ).get_listings()
                time.sleep(5)
                _manual_fb = os.environ.get("AIMM_MANUAL_SEARCH_FALLBACK", "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if not found_listings and _manual_fb:
                    _fb_msg = (
                        "[Search] Parsed zero listings from the automated Marketplace URL. "
                        f"phrase={search_phrase!r} city={city!r}. "
                        "In the Playwright browser, run the search manually until result cards show, "
                        "then press Enter here to re-parse the current page."
                    )
                    if self.logger:
                        self.logger.warning(_fb_msg)
                    elif sys.stdout.isatty():
                        print("\n" + _fb_msg + "\n", file=sys.stderr)
                    try:
                        if sys.stdin.isatty():
                            input("Press Enter after results are visible... ")
                    except EOFError:
                        pass
                    found_listings = FacebookSearchResultPage(
                        self.page, self.translator, self.logger
                    ).get_listings()
                    time.sleep(5)
                if not found_listings:
                    if self.logger:
                        self.logger.error(
                            f"""{hilight("[Search]", "fail")} Failed to get search results for {search_phrase} from {city}"""
                        )
                elif self.logger:
                    self.logger.info(
                        f"""{hilight("[Search]", "succ")} Got {len(found_listings)} search result(s) for {search_phrase} from {city}"""
                    )

                counter.increment(CounterItem.SEARCH_PERFORMED, item_config.name)

                _shallow_skip_enabled = os.environ.get(
                    "AIMM_SHALLOW_STABLE_SKIP", ""
                ).strip().lower() in ("1", "true", "yes")

                # go to each item and get the description
                # if we have not done that before
                _serp_count = 0
                _detail_fetched = 0
                _stable_skipped = 0
                _serp_total_cards = len(found_listings)
                _search_progress_every = max(
                    0,
                    int((os.environ.get("AIMM_SEARCH_PROGRESS_EVERY", "25") or "25").strip()),
                )
                _serp_slot_idx = 0
                for listing in found_listings:
                    try:
                        if listing.post_url.split("?")[0] in found:
                            continue
                        if self.keyboard_monitor is not None and self.keyboard_monitor.is_paused():
                            return
                        counter.increment(CounterItem.LISTING_EXAMINED, item_config.name)
                        found[listing.post_url.split("?")[0]] = True
                        _serp_count += 1
                        # filter by title and location; skip keyword filtering since we do not have description yet.
                        if not self.check_listing(
                            listing, item_config, description_available=False
                        ):
                            counter.increment(CounterItem.EXCLUDED_LISTING, item_config.name)
                            continue
                        # Shallow stable-skip: if PG confirms same price + prior AI eval, the
                        # monitor's price gate would discard this listing anyway — skip Playwright.
                        if _shallow_skip_enabled and should_skip_stable_detail_fetch(
                            listing, logger=self.logger
                        ):
                            _stable_skipped += 1
                            continue
                        try:
                            details, from_cache = self.get_listing_details(
                                listing.post_url,
                                item_config,
                                price=listing.price,
                                title=listing.title,
                            )
                            if not from_cache:
                                time.sleep(5)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            if self.logger:
                                self.logger.error(
                                    f"""{hilight("[Retrieve]", "fail")} Failed to get item details: {e}"""
                                )
                            continue
                        _detail_fetched += 1
                        # currently we trust the other items from summary page a bit better
                        # so we do not copy title, description etc from the detailed result
                        for attr in ("condition", "seller", "description"):
                            # other attributes should be consistent
                            setattr(listing, attr, getattr(details, attr))
                        listing.original_price = details.original_price or listing.original_price
                        listing.name = item_config.name
                        if self.logger:
                            self.logger.debug(
                                f"""{hilight("[Retrieve]", "succ")} New item "{listing.title}" from {listing.post_url} is sold by "{listing.seller}" and with description "{listing.description[:100]}..." """
                            )

                        # Warn if we never managed to extract a description for keyword-based filtering
                        if (
                            (not listing.description or len(listing.description.strip()) == 0)
                            and item_config.keywords
                            and len(item_config.keywords) > 0
                            and self.logger
                        ):
                            self.logger.debug(
                                f"""{hilight("[Error]", "fail")} Failed to extract description for {hilight(listing.title)} at {listing.post_url}. Keyword filtering will only apply to title."""
                            )

                        if self.check_listing(listing, item_config):
                            yield listing
                        else:
                            counter.increment(CounterItem.EXCLUDED_LISTING, item_config.name)
                    finally:
                        _serp_slot_idx += 1
                        if (
                            self.logger
                            and _serp_total_cards > 0
                            and _search_progress_every > 0
                            and _serp_slot_idx % _search_progress_every == 0
                        ):
                            self.logger.info(
                                f"""{hilight("[Search]", "info")} {_serp_slot_idx} of """
                                f"""{_serp_total_cards} SERP result(s) completed for """
                                f"""{hilight(search_phrase)} from {hilight(cname or city)}"""
                            )

                if self.logger and _shallow_skip_enabled:
                    self.logger.info(
                        f"""{hilight("[SERP]", "info")} {_serp_count} cards"""
                        f""" | detail_fetch={_detail_fetched} | stable_skip={_stable_skipped}"""
                    )

    def get_listing_details(
        self: "FacebookMarketplace",
        post_url: str,
        item_config: ItemConfig,
        price: str | None = None,
        title: str | None = None,
    ) -> Tuple[Listing, bool]:
        assert post_url.startswith("https://www.facebook.com")
        details = Listing.from_cache(post_url)
        if (
            details is not None
            and (price is None or details.price == price)
            and (title is None or details.title == title)
        ):
            # if the price and title are the same, we assume everything else is unchanged.
            return details, True

        if not self.page:
            self.login()

        assert self.page is not None
        self.goto_url(post_url)
        counter.increment(CounterItem.LISTING_QUERY, item_config.name)
        details = parse_listing(self.page, post_url, self.translator, self.logger)
        if details is None:
            raise ValueError(
                f"Failed to get item details of listing {post_url}. "
                "The listing might be missing key information (e.g. seller) or not in English."
                "Please add option language to your marketplace configuration is the latter is the case. See https://github.com/BoPeng/ai-marketplace-monitor?tab=readme-ov-file#support-for-non-english-languages for details."
            )
        details.to_cache(post_url)
        return details, False

    def check_listing(
        self: "FacebookMarketplace",
        item: Listing,
        item_config: FacebookItemConfig,
        description_available: bool = True,
    ) -> bool:
        # get antikeywords from both item_config or config
        antikeywords = item_config.antikeywords
        if antikeywords and (
            is_substring(antikeywords, item.title + " " + item.description, logger=self.logger)
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} due to {hilight("excluded keywords", "fail")}: {", ".join(antikeywords)}"""
                )
            return False

        _serp_strict_title = os.environ.get("SEARCH_STRICTLY_IN_TITLE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        serp_keywords = item_config.serp_keywords if _serp_strict_title else None
        if (
            not description_available
            and serp_keywords
            and not is_substring(
                serp_keywords,
                item.title,
                logger=self.logger,
                digit_token_boundary=True,
            )
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} {hilight("without SERP title keywords", "fail")} (item.serp_keywords; enable SEARCH_STRICTLY_IN_TITLE)."""
                )
            return False

        # if the return description does not contain any of the search keywords
        keywords = item_config.keywords
        if (
            description_available
            and keywords
            and not (
                is_substring(keywords, item.title + "  " + item.description, logger=self.logger)
            )
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} {hilight("without required keywords", "fail")} in title and description."""
                )
            return False

        # get locations from either marketplace config or item config
        if item_config.seller_locations is not None:
            allowed_locations = item_config.seller_locations
        else:
            allowed_locations = self.config.seller_locations or []
        if allowed_locations and not is_substring(
            allowed_locations, item.location, logger=self.logger
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight("out of area", "fail")} item {hilight(item.title)} from location {hilight(item.location)}"""
                )
            return False

        # get exclude_sellers from both item_config or config
        if item_config.exclude_sellers is not None:
            exclude_sellers = item_config.exclude_sellers
        else:
            exclude_sellers = self.config.exclude_sellers or []
        if (
            item.seller
            and exclude_sellers
            and is_substring(exclude_sellers, item.seller, logger=self.logger)
        ):
            if self.logger:
                self.logger.info(
                    f"""{hilight("[Skip]", "fail")} Exclude {hilight(item.title)} sold by {hilight("banned seller", "failed")} {hilight(item.seller)}"""
                )
            return False

        return True


class FacebookSearchResultPage(WebPage):
    def _serp_collection_heading(self: "FacebookSearchResultPage") -> Locator:
        return self.page.locator(
            f'[aria-label="{self.translator("Collection of Marketplace items")}"]'
        )

    def _serp_scroll_step(self: "FacebookSearchResultPage") -> None:
        """Nudge Facebook's SERP: inner overflow pane, window, and mouse wheel (one combined step)."""
        heading = self._serp_collection_heading()
        if heading.count() > 0:
            try:
                heading.first.evaluate("""(heading) => {
                        let n = heading;
                        for (let p = heading; p; p = p.parentElement) {
                            if (!p.parentElement) break;
                            const st = window.getComputedStyle(p);
                            const oy = st.overflowY;
                            if ((oy === "auto" || oy === "scroll" || oy === "overlay") &&
                                p.scrollHeight > p.clientHeight + 1) {
                                n = p;
                                break;
                            }
                        }
                        n.scrollTop = n.scrollHeight;
                    }""")
            except Exception as e:
                if self.logger:
                    self.logger.debug(
                        f"{hilight('[Retrieve]', 'dim')} SERP inner scroll failed: {e}"
                    )
        try:
            self.page.evaluate("window.scrollBy(0, Math.floor((window.innerHeight || 800) * 0.9))")
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'dim')} SERP window scroll failed: {e}")
        try:
            vp = self.page.viewport_size
            if vp:
                self.page.mouse.move(
                    max(50, vp["width"] // 2),
                    max(50, min(vp["height"] // 2, 500)),
                )
                self.page.mouse.wheel(0, 2800)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'dim')} SERP mouse wheel failed: {e}")

    @staticmethod
    def _normalize_serp_text_lines(text: str) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if lines and lines[-1] == line:
                continue
            lines.append(line)
        return lines

    @staticmethod
    def _is_serp_price_line(line: str) -> bool:
        normalized = re.sub(r"\s+", " ", line).strip()
        low = normalized.lower()
        has_currency_marker = any(
            token in low
            for token in (" kr", "kr ", "sek", "usd", "eur", "€", "$", "£", "gratis", "free")
        )
        numeric_only = (
            re.fullmatch(r"\d[\d\s.,]*(?:\s*[-–—]\s*\d[\d\s.,]*)?", normalized) is not None
        )
        if not has_currency_marker and not numeric_only:
            return False

        current, original = parse_listing_prices(line)
        if current == "**unspecified**":
            return True
        if original:
            return True
        return current.isdigit() and current != line.strip()

    @classmethod
    def _extract_serp_text_fields(cls, text: str) -> tuple[str, str, str]:
        lines = cls._normalize_serp_text_lines(text)
        if not lines:
            return "", "", ""

        price_idx = next(
            (idx for idx, line in enumerate(lines) if cls._is_serp_price_line(line)), -1
        )
        raw_price = lines[price_idx] if price_idx >= 0 else ""

        title_idx = -1
        for idx in range(price_idx + 1 if price_idx >= 0 else 0, len(lines)):
            if cls._is_serp_price_line(lines[idx]):
                continue
            title_idx = idx
            break

        title = lines[title_idx] if title_idx >= 0 else ""

        location = ""
        if title_idx >= 0:
            for idx in range(title_idx + 1, len(lines)):
                if cls._is_serp_price_line(lines[idx]):
                    continue
                location = lines[idx]
                break

        return raw_price, title, location

    def _extract_serp_card_fields(
        self: "FacebookSearchResultPage", listing: ElementHandle, atag: ElementHandle
    ) -> tuple[str, str, str]:
        raw_price = ""
        title = ""
        location = ""

        try:
            details_divs = atag.query_selector_all(":scope > :first-child > div")
            if len(details_divs) > 1:
                details = details_divs[1]
                divs = details.query_selector_all(":scope > div")
                raw_price = "" if len(divs) < 1 else divs[0].text_content() or ""
                title = "" if len(divs) < 2 else divs[1].text_content() or ""
                location = "" if len(divs) < 3 else (divs[2].text_content() or "")
        except Exception as e:
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'dim')} SERP structured card parse fallback: {e}"
                )

        if raw_price and title:
            return raw_price, title, location

        fallback_price, fallback_title, fallback_location = self._extract_serp_text_fields(
            listing.text_content() or atag.text_content() or ""
        )
        return (
            raw_price or fallback_price,
            title or fallback_title,
            location or fallback_location,
        )

    def _handles_to_listings(
        self: "FacebookSearchResultPage", valid_listings: List[ElementHandle]
    ) -> List[Listing]:
        """Parse Marketplace card element handles into Listing rows (same rules as legacy get_listings)."""
        listings: List[Listing] = []
        for idx, listing in enumerate(valid_listings):
            try:
                atag = listing.query_selector("a[href*='/marketplace/item/']")
                if not atag:
                    atag = listing.query_selector(
                        ":scope > :first-child > :first-child > :first-child > :first-child > :first-child > :first-child > :first-child > :first-child"
                    )
                if not atag:
                    continue
                post_url = atag.get_attribute("href") or ""
                if "/marketplace/item/" not in post_url:
                    continue
                raw_price, title, location = self._extract_serp_card_fields(listing, atag)

                img = listing.query_selector("img")
                image = img.get_attribute("src") if img else ""
                price, original_price = parse_listing_prices(raw_price)

                if post_url.startswith("/"):
                    post_url = f"https://www.facebook.com{post_url}"

                if image.startswith("/"):
                    image = f"https://www.facebook.com{image}"

                listings.append(
                    Listing(
                        marketplace="facebook",
                        name="",
                        id=post_url.split("?")[0].rstrip("/").split("/")[-1],
                        title=title,
                        image=image,
                        price=price,
                        original_price=original_price,
                        post_url=post_url,
                        location=location,
                        condition="",
                        seller="",
                        description="",
                    )
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"{hilight('[Retrieve]', 'fail')} Failed to parse search results {idx + 1} listing: {e}"
                    )
                continue
        return listings

    def _get_listings_elements_by_children_counts(self: "FacebookSearchResultPage"):
        parent: ElementHandle | None = self.page.locator("img").first.element_handle()
        # look for parent of parent until it has more than 10 children
        children = []
        while parent:
            children = parent.query_selector_all(":scope > *")
            if len(children) > 10:
                break
            parent = parent.query_selector("xpath=..")
        # find each listing
        valid_listings = []
        try:
            for listing in children:
                if not listing.text_content():
                    continue
                valid_listings.append(listing)
        except Exception as e:
            # this error should be tolerated
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'fail')} Some grid item cannot be read: {e}"
                )
        return valid_listings

    def _get_listing_elements_by_traversing_header(self: "FacebookSearchResultPage"):
        heading = self._serp_collection_heading()
        if heading.count() == 0:
            return []

        grid_items = heading.locator(
            ":scope > :first-child > :first-child > :nth-child(3) > :first-child > :nth-child(2) > div"
        )
        # find each listing
        valid_listings = []
        try:
            for listing in grid_items.all():
                if not listing.text_content():
                    continue
                valid_listings.append(listing.element_handle())
        except Exception as e:
            # this error should be tolerated
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'fail')} Some grid item cannot be read: {e}"
                )
        return valid_listings

    def get_listings(self: "FacebookSearchResultPage") -> List[Listing]:
        # if no result is found
        btn = self.page.locator(f"""span:has-text('{self.translator("Browse Marketplace")}')""")
        if btn.count() > 0:
            if self.logger:
                msg = self._parent_with_cond(
                    btn.first,
                    lambda x: len(x) == 3
                    and self.translator("Browse Marketplace") in (x[-1].text_content() or ""),
                    1,
                )
                self.logger.info(f"{hilight('[Retrieve]', 'dim')} {msg}")
            return []

        _scroll_on = os.environ.get("AIMM_FB_SERP_SCROLL", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        )
        max_rounds = int((os.environ.get("AIMM_FB_SERP_SCROLL_MAX_ROUNDS", "150") or "150").strip())
        idle_need = int((os.environ.get("AIMM_FB_SERP_SCROLL_IDLE", "6") or "6").strip())
        pause = float((os.environ.get("AIMM_FB_SERP_SCROLL_PAUSE", "0.55") or "0.55").strip())
        log_every = max(1, int((os.environ.get("AIMM_FB_SERP_LOG_EVERY", "8") or "8").strip()))

        if _scroll_on:
            try:
                self._serp_collection_heading().first.wait_for(state="visible", timeout=20000)
            except Exception:
                pass

        by_url: dict[str, Listing] = {}
        idle = 0
        rounds = max(1, max_rounds) if _scroll_on else 1

        if self.logger and _scroll_on:
            self.logger.info(
                f"{hilight('[SERP]', 'info')} "
                f"Loading more results (max {max_rounds} scroll rounds, "
                f"stop after {idle_need} passes with no new listing URLs, "
                f"progress every {log_every} rounds)…"
            )

        for round_idx in range(rounds):
            try:
                valid_listings = (
                    self._get_listing_elements_by_traversing_header()
                    or self._get_listings_elements_by_children_counts()
                )
            except KeyboardInterrupt:
                raise
            except Exception as e:
                filename = datetime.datetime.now().strftime("debug_%Y%m%d_%H%M%S.html")
                if self.logger:
                    self.logger.error(
                        f"{hilight('[Retrieve]', 'fail')} failed to parse searching result. Page saved to {filename}: {e}"
                    )
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                return []

            before = len(by_url)
            for L in self._handles_to_listings(valid_listings):
                key = (L.post_url or "").split("?")[0].strip()
                if not key or "/marketplace/item/" not in key:
                    continue
                by_url[key] = L

            added = len(by_url) - before
            if self.logger and _scroll_on:
                if added > 0 and (round_idx == 0 or (round_idx + 1) % log_every == 0):
                    self.logger.info(
                        f"{hilight('[SERP]', 'info')} "
                        f"scroll round {round_idx + 1}/{rounds}: "
                        f"{len(by_url)} unique URLs (+{added} this pass)"
                    )

            if not _scroll_on:
                break

            if len(by_url) == before:
                idle += 1
                if self.logger and _scroll_on:
                    self.logger.info(
                        f"{hilight('[SERP]', 'info')} "
                        f"No new listing URLs this pass — reached end of loaded batch, "
                        f"nudging scroll again (idle {idle}/{idle_need}, "
                        f"{len(by_url)} unique so far)"
                    )
                if idle >= idle_need:
                    if self.logger and _scroll_on:
                        self.logger.info(
                            f"{hilight('[SERP]', 'info')} "
                            f"No new URLs in {idle_need} consecutive passes; "
                            f"finished loading search page."
                        )
                    break
            else:
                idle = 0

            self._serp_scroll_step()
            time.sleep(pause)

        listings = list(by_url.values())
        if self.logger and _scroll_on and len(listings) > 0:
            self.logger.info(
                f"{hilight('[SERP]', 'info')} "
                f"Merged {len(listings)} unique listing URL(s) after scrolling."
            )
        return listings


class FacebookItemPage(WebPage):
    def verify_layout(self: "FacebookItemPage") -> bool:
        return True

    def get_title(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_title is not implemented for this page")

    def get_price(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_price is not implemented for this page")

    def get_image_url(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_image_url is not implemented for this page")

    def get_seller(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_seller is not implemented for this page")

    def get_description(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_description is not implemented for this page")

    def get_location(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_location is not implemented for this page")

    def get_condition(self: "FacebookItemPage") -> str:
        raise NotImplementedError("get_condition is not implemented for this page")

    def get_availability(self: "FacebookItemPage") -> str:
        return "Till Salu"

    def check_is_tradera(self: "FacebookItemPage") -> bool:
        return False

    def parse(self: "FacebookItemPage", post_url: str) -> Listing:
        removed_listing = build_removed_listing(self.page, post_url, self.translator, self.logger)
        if removed_listing is not None:
            return removed_listing

        if not self.verify_layout():
            raise ValueError("Layout mismatch")

        # title
        title = self.get_title()
        price_raw = self.get_price()
        description = self.get_description()

        if not title or not price_raw or not description:
            raise ValueError(f"Failed to parse {post_url}")

        price, original_price = parse_listing_prices(price_raw)
        availability = self.get_availability()

        if self.logger:
            self.logger.info(
                f"{hilight('[Retrieve]', 'succ')} Parsing {hilight(title)} (Status: {availability})"
            )
        res = Listing(
            marketplace="facebook",
            name="",
            id=post_url.split("?")[0].rstrip("/").split("/")[-1],
            title=title,
            image=self.get_image_url(),
            price=price,
            original_price=original_price,
            post_url=post_url,
            location=self.get_location(),
            condition=self.get_condition(),
            description=description,
            seller=self.get_seller(),
            availability=availability,
            is_tradera=self.check_is_tradera(),
        )
        if self.logger:
            self.logger.debug(f"{hilight('[Retrieve]', 'succ')} {pretty_repr(res)}")
        return cast(Listing, res)


def build_removed_listing(
    page: Page,
    post_url: str,
    translator: Translator | None = None,
    logger: Logger | None = None,
) -> Listing | None:
    html = (page.content() or "").lower()
    missing_indicators = [
        "den här annonsen är inte längre tillgänglig",
        "det här inlägget finns inte längre",
        "annonsen är inte längre tillgänglig",
        "listing no longer available",
        "no longer available",
        "is not available right now",
        "content isn't available",
        "this content isn't available",
    ]
    if not any(ind in html for ind in missing_indicators):
        return None
    if logger:
        logger.info(f"{hilight('[Retrieve]', 'info')} Listing {post_url} is marked as Borttagen")
    translate = translator or (lambda text: text)
    return Listing(
        marketplace="facebook",
        name="",
        id=post_url.split("?")[0].rstrip("/").split("/")[-1],
        title=translate("Borttagen"),
        image="",
        price="",
        original_price="",
        post_url=post_url,
        location="",
        condition="",
        description=translate("Det här inlägget finns inte längre"),
        seller="",
        availability="Borttagen",
    )


class FacebookRegularItemPage(FacebookItemPage):
    def verify_layout(self: "FacebookRegularItemPage") -> bool:
        return any(
            self.translator("Condition") in (x.text_content() or "")
            for x in self.page.query_selector_all("li")
        )

    def get_title(self: "FacebookRegularItemPage") -> str:
        try:
            h1_element = self.page.query_selector_all("h1")[-1]
            title = h1_element.text_content() or self.translator("**unspecified**")

            # Normalize title to handle non-breaking spaces and different dot characters
            # Facebook often uses "Såld · " where the space is \xa0
            title_clean = title.replace("\xa0", " ").strip()
            title_lower = title_clean.lower()

            # Common prefixes in Swedish/English
            prefixes = ["såld ·", "sold ·", "såld", "sold"]
            for p in prefixes:
                if title_lower.startswith(p):
                    # Find where the prefix ends (usually after the dot or just the word)
                    if " · " in title_clean:
                        title = title_clean.split(" · ", 1)[1]
                    elif " ·" in title_clean:
                        title = title_clean.split(" ·", 1)[1]
                    else:
                        title = title_clean[len(p) :].strip()
                    break
            return title.strip()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_price(self: "FacebookRegularItemPage") -> str:
        try:
            price_element = self.page.locator("h1 + *")
            return price_element.text_content() or self.translator("**unspecified**")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_availability(self: "FacebookRegularItemPage") -> str:
        try:
            # 1. Check title for "Sold" prefix
            h1_element = self.page.query_selector_all("h1")[-1]
            title_header = (h1_element.text_content() or "").replace("\xa0", " ").lower()
            if title_header.startswith("såld") or title_header.startswith("sold"):
                return "Såld"

            # 2. Check for "Message" button (indicator of ACTIVE listing)
            # Most reliable way to know it's NOT sold is that you can still message the seller
            active_button_locators = [
                'div[aria-label="Skicka meddelande"]',
                'div[aria-label="Message"]',
                'div[role="button"]:has-text("Skicka meddelande")',
                'div[role="button"]:has-text("Message")',
                'div[role="button"]:has-text("Visa på Tradera")',
                'div[role="button"]:has-text("View on Tradera")',
                'a:has-text("Visa på Tradera")',
                'a:has-text("View on Tradera")',
            ]

            has_active_button = False
            for selector in active_button_locators:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=500):
                        has_active_button = True
                        break
                except:
                    continue

            if has_active_button:
                return "Till Salu"

            # 3. Check for specific "Sold" banner text in the main detail area
            # (avoid the whole page content to prevent false positives from suggestions)
            detail_pane = self.page.locator("h1").locator(".. >> .. >> ..")
            pane_text = (detail_pane.text_content() or "").lower()
            sold_banners = [
                "den här artikeln har sålts",
                "this item was sold",
                "artikeln har sålts",
            ]
            if any(b in pane_text for b in sold_banners):
                return "Såld"
        except Exception as e:
            if self.logger:
                self.logger.debug(f"[Availability Check] Error: {e}")
            pass

        # Default back to Till Salu if we saw an active button or found no strong sold signals
        return "Till Salu"

    def get_image_url(self: "FacebookRegularItemPage") -> str:
        try:
            image_url = self.page.locator("img").first.get_attribute("src") or ""
            return image_url
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    @staticmethod
    def _is_tradera_seller_noise(line: str, heading: str) -> bool:
        low = line.lower().strip()
        if not low:
            return True
        if low == "tradera":
            return True
        if heading.strip().lower() in low and len(low) <= len(heading) + 2:
            return True
        noise = (
            "recenserad",
            "gick med i tradera",
            "joined tradera",
            "läs mer",
            "mer information från tradera",
        )
        return any(p in low for p in noise)

    def check_is_tradera(self: "FacebookRegularItemPage") -> bool:
        try:
            # 1. Check seller name
            seller = self.get_seller().lower()
            if "tradera" in seller:
                return True

            # 2. Check for "Visa på Tradera" button
            tradera_buttons = [
                'div[role="button"]:has-text("Visa på Tradera")',
                'div[role="button"]:has-text("View on Tradera")',
                'a:has-text("Visa på Tradera")',
                'a:has-text("View on Tradera")',
            ]
            for selector in tradera_buttons:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=500):
                        return True
                except:
                    continue

            # 3. Check for specific text in description or seller info
            html = (self.page.content() or "").lower()
            if (
                "shoppa säljinlägg från tradera" in html
                or "information om säljaren tradera" in html
                or "mer information från tradera" in html
                or "more information from tradera" in html
            ):
                return True
        except Exception:
            pass
        return False

    def _seller_from_tradera_crosslist(self: "FacebookRegularItemPage") -> str:
        """Seller name on Marketplace listings mirrored from Tradera (no FB profile link)."""
        html = (self.page.content() or "").lower()
        if "tradera" not in html:
            return ""
        heading = self.translator("Information about the seller Tradera")
        if any(c in heading for c in ('"', "'", "<", ">")):
            return ""
        h = heading.strip()
        hlen = len(h)
        # XPath 1.0 literal: prefer single-quoted argument (heading must not contain ')
        if "'" in h:
            return ""
        label_el = self.page.query_selector(
            f"xpath=//*[contains(normalize-space(string(.)), '{h}') and "
            f"string-length(normalize-space(string(.))) <= {hlen + 40}]"
        )
        if label_el is None:
            return ""
        nxt = label_el.query_selector("xpath=following-sibling::*[1]")
        if nxt is not None:
            line = (nxt.text_content() or "").strip().split("\n")[0].strip()
            if line and not self._is_tradera_seller_noise(line, heading):
                return line
        parent = label_el.query_selector("xpath=..")
        if parent is None:
            return ""
        kids = parent.query_selector_all(":scope > *")
        found = False
        for k in kids:
            raw = (k.text_content() or "").strip()
            if not found:
                if heading in raw or raw == heading:
                    found = True
                continue
            first_line = raw.split("\n")[0].strip()
            if first_line and not self._is_tradera_seller_noise(first_line, heading):
                return first_line
        return ""

    def get_seller(self: "FacebookRegularItemPage") -> str:
        unspecified = self.translator("**unspecified**")
        try:
            # Locator.text_content() waits full default timeout when no node matches
            # (common when not logged in). query_selector_all returns immediately.
            for sel in (
                'a[href*="/marketplace/profile"]',
                'a[href*="marketplace/profile"]',
                'a[href*="profile.php?id="]',
            ):
                anchors = self.page.query_selector_all(sel)
                if not anchors:
                    continue
                text = (anchors[-1].text_content() or "").strip()
                if text:
                    return text
            tradera_seller = self._seller_from_tradera_crosslist()
            if tradera_seller:
                return tradera_seller
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'fail')} get_seller: no seller link in DOM"
                )
            return unspecified
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(
                    f"{hilight('[Retrieve]', 'fail')} get_seller failed: {type(e).__name__}: {e}"
                )
            return unspecified

    def _expand_see_more_in_scope(self: "FacebookRegularItemPage", scope: Locator) -> None:
        """Facebook collapses long attribute lists; DOM may only show truncated text + 'See more'."""
        labels = {self.translator("See more"), "See more"}
        labels = {x.strip() for x in labels if x and x.strip()}
        for label in labels:
            try:
                btn = scope.get_by_role("button", name=re.compile(re.escape(label), re.I))
                for i in range(min(btn.count(), 12)):
                    try:
                        loc = btn.nth(i)
                        if loc.is_visible(timeout=400):
                            loc.click(timeout=4000)
                            doze(0.2)
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                linkish = scope.get_by_text(label, exact=True)
                if linkish.count() == 0:
                    continue
                for i in range(min(linkish.count(), 12)):
                    try:
                        loc = linkish.nth(i)
                        if loc.is_visible(timeout=400):
                            loc.click(timeout=4000)
                            doze(0.2)
                    except Exception:
                        continue
            except Exception:
                pass

    @staticmethod
    def _normalize_text_line(line: str) -> str:
        return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip(" :\u200b\t\r\n")

    def _page_text_lines(self: "FacebookRegularItemPage") -> List[str]:
        texts: List[str] = []
        try:
            body_text = self.page.locator("body").text_content()
            if isinstance(body_text, str) and body_text.strip():
                texts.append(body_text)
        except Exception:
            pass
        try:
            page_html = self.page.content() or ""
            if page_html:
                text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", page_html)
                text = re.sub(r"(?i)<br\s*/?>", "\n", text)
                text = re.sub(
                    r"(?i)</?(div|p|li|ul|ol|h1|h2|h3|h4|h5|h6|section|article|span|a|button|label|dt|dd|tr|td|th)>",
                    "\n",
                    text,
                )
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                text = html.unescape(text)
                texts.append(text)
        except Exception:
            pass

        lines: List[str] = []
        seen: set[str] = set()
        for text in texts:
            for raw in text.splitlines():
                line = self._normalize_text_line(raw)
                if line and line not in seen:
                    lines.append(line)
                    seen.add(line)
        return lines

    def _tradera_text_lines(self: "FacebookRegularItemPage") -> List[str]:
        lines = self._page_text_lines()
        if not any("tradera" in line.lower() for line in lines):
            return []
        return lines

    def _extract_labeled_text_block(
        self: "FacebookRegularItemPage",
        labels: List[str],
        stop_labels: List[str],
    ) -> str:
        label_set = {self._normalize_text_line(label).lower() for label in labels if label}
        stop_set = {self._normalize_text_line(label).lower() for label in stop_labels if label}
        if not label_set:
            return ""

        lines = self._tradera_text_lines()
        for idx, line in enumerate(lines):
            normalized_line = self._normalize_text_line(line)
            normalized_low = normalized_line.lower()
            if normalized_low in label_set:
                values: List[str] = []
                for candidate in lines[idx + 1 :]:
                    normalized = self._normalize_text_line(candidate).lower()
                    if not normalized:
                        continue
                    if normalized in stop_set:
                        break
                    values.append(candidate)
                if values:
                    return "\n".join(values).strip()
                continue

            for label in label_set:
                prefix = f"{label} "
                if normalized_low.startswith(prefix):
                    inline_value = normalized_line[len(prefix) :].strip()
                    if inline_value and inline_value.lower() not in stop_set:
                        return inline_value
        return ""

    def _tradera_common_stop_labels(self: "FacebookRegularItemPage") -> List[str]:
        return [
            "Mer information från Tradera",
            "More information from Tradera",
            self.translator("Description"),
            "Beskrivning",
            self.translator("Details"),
            "Detaljer",
            self.translator("Condition"),
            "Skick",
            "Leverans",
            "Delivery",
            "Plats",
            "Location",
            self.translator("Information about the seller Tradera"),
            "Information om säljaren Tradera",
            self.translator("See more"),
            "See more",
            "Visa på Tradera",
            "View on Tradera",
        ]

    def _get_tradera_description_block(self: "FacebookRegularItemPage") -> str:
        return self._extract_labeled_text_block(
            labels=[self.translator("Description"), "Beskrivning"],
            stop_labels=self._tradera_common_stop_labels(),
        )

    def _get_tradera_condition(self: "FacebookRegularItemPage") -> str:
        return self._extract_labeled_text_block(
            labels=[self.translator("Condition"), "Skick"],
            stop_labels=self._tradera_common_stop_labels(),
        )

    def _get_tradera_delivery(self: "FacebookRegularItemPage") -> str:
        return self._extract_labeled_text_block(
            labels=["Leverans", "Delivery"],
            stop_labels=self._tradera_common_stop_labels(),
        )

    def _get_tradera_location(self: "FacebookRegularItemPage") -> str:
        location = self._extract_labeled_text_block(
            labels=["Plats", "Location"],
            stop_labels=self._tradera_common_stop_labels(),
        )
        if not location:
            return ""
        approx_labels = {label.lower() for label in self._location_labels()}
        approx_labels.update({"plats är ungefärlig", "location is approximate"})
        filtered = [
            line
            for line in location.splitlines()
            if self._normalize_text_line(line).lower() not in approx_labels
        ]
        return "\n".join(filtered).strip()

    def get_description(self: "FacebookRegularItemPage") -> str:
        if self.check_is_tradera():
            description = self._get_tradera_description_block()
            extras: List[str] = []
            condition = self._get_tradera_condition()
            if condition:
                extras.append(f'{self.translator("Condition")}\n{condition}')
            delivery = self._get_tradera_delivery()
            if delivery:
                extras.append(f"Leverans\n{delivery}")
            if description or extras:
                parts = [part for part in [description, *extras] if part]
                return "\n\n".join(parts).strip()
        try:
            # Find the span with text "condition", then parent, then next...
            description_element = self.page.locator(
                f'span:text("{self.translator("Condition")}") >> xpath=ancestor::ul[1] >> xpath=following-sibling::*[1]'
            )
            self._expand_see_more_in_scope(description_element)
            # Fallback: some layouts attach the control outside the following-sibling block
            self._expand_see_more_in_scope(
                self.page.locator(
                    f'span:text("{self.translator("Condition")}") >> xpath=ancestor::div[1]'
                )
            )
            return description_element.text_content() or self.translator("**unspecified**")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_condition(self: "FacebookRegularItemPage") -> str:
        tradera_condition = self._get_tradera_condition()
        if tradera_condition:
            return tradera_condition
        try:
            if self.logger:
                self.logger.debug(f"{hilight('[Debug]', 'info')} Getting condition info...")
            # Find the span with text "condition", then parent, then next...
            condition_text = self.translator("Condition")

            # Use .first property to avoid strict mode violation when multiple elements match
            # This handles cases where "Condition" appears in both the label and description text
            condition_locator = self.page.locator(f'span:text("{condition_text}")')
            condition_element = condition_locator.first

            result = self._parent_with_cond(
                condition_element,
                lambda x: len(x) >= 2
                and self.translator("Condition") in (x[0].text_content() or ""),
                1,
            )
            return result
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"{hilight('[Error]', 'fail')} get_condition failed: {type(e).__name__}: {e}"
                )
            return ""

    def _location_labels(self: "FacebookRegularItemPage") -> List[str]:
        labels = [
            self.translator("Location is approximate"),
            "Location is approximate",
            "Plats är ungefärlig",
        ]
        return [label.strip() for label in labels if isinstance(label, str) and label.strip()]

    def _extract_location_from_text_block(self: "FacebookRegularItemPage", text: str | None) -> str:
        if not text:
            return ""

        labels = self._location_labels()
        label_lows = {label.lower() for label in labels}
        noise = {
            *label_lows,
            self.translator("See more").strip().lower(),
            "see more",
        }
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]

        for idx, line in enumerate(lines):
            low = line.lower()
            matched_label = next((label for label in labels if label.lower() in low), None)
            if matched_label is None:
                continue

            before = line[: low.index(matched_label.lower())].strip(" ,.-")
            after = line[low.index(matched_label.lower()) + len(matched_label) :].strip(" ,.-")
            if before and before.lower() not in noise:
                return before
            for candidate in reversed(lines[:idx]):
                if candidate.lower() not in noise:
                    return candidate
            if after and after.lower() not in noise:
                return after
            for candidate in lines[idx + 1 :]:
                if candidate.lower() not in noise:
                    return candidate
        return ""

    def _extract_location_near_element(
        self: "FacebookRegularItemPage", element: Locator | ElementHandle | None
    ) -> str:
        if element is None:
            return ""

        parent: ElementHandle | None
        if hasattr(element, "element_handle"):
            parent = cast(Any, element).element_handle()
        else:
            parent = cast(Any, element)
        for _ in range(10):
            if parent is None:
                break
            location = self._extract_location_from_text_block(parent.text_content() or "")
            if location:
                return location
            parent = parent.query_selector("xpath=..")
        return ""

    def get_location(self: "FacebookRegularItemPage") -> str:
        tradera_location = self._get_tradera_location()
        if tradera_location:
            return tradera_location
        labels = self._location_labels()
        for label in labels:
            try:
                approximate_element = self.page.locator(f'span:text("{label}")')
                location = self._extract_location_near_element(approximate_element)
                if location:
                    return location
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
        return ""


class FacebookRentalItemPage(FacebookRegularItemPage):
    def verify_layout(self: "FacebookRentalItemPage") -> bool:
        # there is a header h2 with text Description
        return any(
            self.translator("Description") in (x.text_content() or "")
            for x in self.page.query_selector_all("h2")
        )

    def get_description(self: "FacebookRentalItemPage") -> str:
        # some pages do not have a condition box and appears to have a "Description" header
        # See https://github.com/BoPeng/ai-marketplace-monitor/issues/29 for details.
        try:
            description_header = self.page.query_selector(
                f'h2:has(span:text("{self.translator("Description")}"))'
            )
            return self._parent_with_cond(
                description_header,
                lambda x: len(x) > 1 and x[0].text_content() == self.translator("Description"),
                1,
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_condition(self: "FacebookRentalItemPage") -> str:
        # no condition information for rental items
        return self.translator("**unspecified**")


class FacebookAutoItemWithAboutAndDescriptionPage(FacebookRegularItemPage):
    def _has_about_this_vehicle(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> bool:
        return any(
            self.translator("About this vehicle") in (x.text_content() or "")
            for x in self.page.query_selector_all("h2")
        )

    def _has_seller_description(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> bool:
        return any(
            self.translator("Seller's description") in (x.text_content() or "")
            for x in self.page.query_selector_all("h2")
        )

    def _get_about_this_vehicle(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> str:
        try:
            about_element = self.page.locator(
                f'h2:has(span:text("{self.translator("About this vehicle")}"))'
            )
            return self._parent_with_cond(
                # start from About this vehicle
                about_element,
                # find an array of elements with the first one being "About this vehicle"
                lambda x: len(x) > 1
                and self.translator("About this vehicle") in (x[0].text_content() or ""),
                # Extract all texts from the elements
                lambda x: "\n".join([child.text_content() or "" for child in x]),
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def _get_seller_description(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> str:
        try:
            description_header = self.page.query_selector(
                f"""h2:has(span:text("{self.translator("Seller's description")}"))"""
            )

            return self._parent_with_cond(
                # start from the description header
                description_header,
                # find an array of elements with the first one being "Seller's description"
                lambda x: len(x) > 1
                and self.translator("Seller's description") in (x[0].text_content() or ""),
                # then, drill down from the second child
                lambda x: self._children_with_cond(
                    x[1],
                    # find the an array of elements
                    lambda y: len(y) > 1,
                    # and return the texts.
                    lambda y: f"""\n\n{self.translator("Seller's description")}\n\n{y[0].text_content() or self.translator("**unspecified**")}""",
                ),
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def verify_layout(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> bool:
        # there is a header h2 with text "About this vehicle"
        return self._has_about_this_vehicle() and self._has_seller_description()

    def get_description(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> str:
        return self._get_about_this_vehicle() + self._get_seller_description()

    def get_price(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> str:
        description = self.get_description()
        # using regular expression to find text that looks like price in the description
        price_pattern = r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?:,\d{2})?"
        match = re.search(price_pattern, description)
        return match.group(0) if match else self.translator("**unspecified**")

    def get_condition(self: "FacebookAutoItemWithAboutAndDescriptionPage") -> str:
        # no condition information for auto items
        return self.translator("**unspecified**")


class FacebookAutoItemWithDescriptionPage(FacebookAutoItemWithAboutAndDescriptionPage):
    def verify_layout(self: "FacebookAutoItemWithDescriptionPage") -> bool:
        return self._has_seller_description() and not self._has_about_this_vehicle()

    def get_description(self: "FacebookAutoItemWithDescriptionPage") -> str:
        try:
            description_header = self.page.query_selector(
                f"""h2:has(span:text("{self.translator("Seller's description")}"))"""
            )

            return self._parent_with_cond(
                # start from the description header
                description_header,
                # find an array of elements with the first one being "Seller's description"
                lambda x: len(x) > 1
                and self.translator("Seller's description") in (x[0].text_content() or ""),
                # then, drill down from the second child
                lambda x: self._children_with_cond(
                    x[1],
                    # find the an array of elements
                    lambda y: len(y) > 2,
                    # and return the texts.
                    lambda y: f"""\n\n{self.translator("Seller's description")}\n\n{y[1].text_content() or self.translator("**unspecified**")}""",
                ),
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_condition(self: "FacebookAutoItemWithDescriptionPage") -> str:
        try:
            description_header = self.page.query_selector(
                f"""h2:has(span:text("{self.translator("Seller's description")}"))"""
            )

            res = self._parent_with_cond(
                # start from the description header
                description_header,
                # find an array of elements with the first one being "Seller's description"
                lambda x: len(x) > 1
                and self.translator("Seller's description") in (x[0].text_content() or ""),
                # then, drill down from the second child
                lambda x: self._children_with_cond(
                    x[1],
                    # find the an array of elements
                    lambda y: len(y) > 2,
                    # and return the texts after seller's description.
                    lambda y: y[0].text_content() or self.translator("**unspecified**"),
                ),
            )
            if res.startswith(self.translator("Condition")):
                res = res[len(self.translator("Condition")) :]
            return res.strip()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""

    def get_price(self: "FacebookAutoItemWithDescriptionPage") -> str:
        # for this page, price is after header
        try:
            h1_element = self.page.query_selector_all("h1")[-1]
            header = h1_element.text_content()
            return self._parent_with_cond(
                # start from the header
                h1_element,
                # find an array of elements with the first one being "Seller's description"
                lambda x: len(x) > 1 and header in (x[0].text_content() or ""),
                # then, find the element after header
                1,
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if self.logger:
                self.logger.debug(f"{hilight('[Retrieve]', 'fail')} {e}")
            return ""


def parse_listing(
    page: Page, post_url: str, translator: Translator | None = None, logger: Logger | None = None
) -> Listing | None:
    supported_facebook_item_layouts = [
        FacebookRentalItemPage,
        FacebookAutoItemWithAboutAndDescriptionPage,
        FacebookAutoItemWithDescriptionPage,
        FacebookRegularItemPage,
    ]

    for page_model in supported_facebook_item_layouts:
        try:
            return page_model(page, translator, logger).parse(post_url)
        except KeyboardInterrupt:
            raise
        except Exception:
            # try next page ayout
            continue
    return build_removed_listing(page, post_url, translator, logger)

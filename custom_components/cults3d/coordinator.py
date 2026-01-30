"""DataUpdateCoordinator for Cults3D integration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TRACKED_CREATIONS,
    CULTS3D_GRAPHQL_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# GraphQL Queries - Corrected based on actual Cults3D schema
# =============================================================================
# Schema notes (verified from error messages):
# - User type: nick, followersCount, followeesCount, creationsCount (NO viewsCount)
# - Creation type: name, shortUrl, viewsCount, downloadsCount, likesCount,
#                  illustrationImageUrl, publishedAt (NO salesCount on Creation)
# - Money type requires selections: income { value } or similar
# - Valid sort enums: BY_PUBLICATION, BY_DOWNLOADS (NO BY_VIEWS, NO BY_SALES)
# - SaleBatch has NO totalCount field
# =============================================================================

# Query for user profile data only (public data)
# Using minimal fields first to avoid schema issues
CULTS3D_USER_QUERY = """
query GetUserData($nick: String!) {
  user(nick: $nick) {
    nick
    followersCount
    followeesCount
    creationsCount
  }
}
"""

# Separate query for user creations (may have different field requirements)
CULTS3D_CREATIONS_QUERY = """
query GetUserCreations($nick: String!) {
  user(nick: $nick) {
    latestCreation: creations(limit: 1) {
      name
      shortUrl
      viewsCount
      downloadsCount
      likesCount
      illustrationImageUrl
      publishedAt
    }
  }
}
"""

# Separate query for sales data (requires authentication, may fail)
CULTS3D_SALES_QUERY = """
query GetMySales {
  myself {
    salesBatch(limit: 100) {
      results {
        income {
          value
        }
        createdAt
      }
    }
  }
}
"""

# Query for a single creation by slug/ID
CULTS3D_CREATION_QUERY = """
query GetCreation($slug: String!) {
  creation(slug: $slug) {
    name
    shortUrl
    viewsCount
    downloadsCount
    likesCount
    illustrationImageUrl
    publishedAt
    creator {
      nick
    }
  }
}
"""

# Validation query
CULTS3D_VALIDATION_QUERY = """
query ValidateAuth($nick: String!) {
  user(nick: $nick) {
    nick
  }
}
"""


def extract_slug_from_url(url_or_slug: str) -> str:
    """Extract the creation slug from a Cults3D URL or return as-is if already a slug."""
    # Handle full URLs like https://cults3d.com/en/3d-model/gadget/creation-name
    match = re.search(r"cults3d\.com/\w+/3d-model/[^/]+/([^/?#]+)", url_or_slug)
    if match:
        return match.group(1)
    # Handle short URLs like https://cults3d.com/en/creation-slug
    match = re.search(r"cults3d\.com/\w+/([^/?#]+)$", url_or_slug)
    if match:
        return match.group(1)
    # Assume it's already a slug
    return url_or_slug.strip()


@dataclass
class CreationData:
    """Data class for a single creation."""

    name: str | None = None
    url: str | None = None
    image_url: str | None = None
    views_count: int = 0
    downloads_count: int = 0
    likes_count: int = 0
    published_at: datetime | None = None


@dataclass
class TrackedCreationData:
    """Data class for a tracked external creation with 30-day metrics."""

    slug: str = ""
    name: str | None = None
    url: str | None = None
    image_url: str | None = None
    creator: str | None = None
    published_at: datetime | None = None

    # Current totals
    views_count: int = 0
    downloads_count: int = 0
    likes_count: int = 0

    # 30-day window info
    window_start: datetime | None = None
    window_end: datetime | None = None
    is_within_30_days: bool = False

    # Note: Actual sales data for non-owned creations is NOT available via API.
    # downloads/likes serve as proxy metrics for popularity.


@dataclass
class Cults3DData:
    """Data class for Cults3D coordinator data."""

    username: str = ""

    # Profile stats
    followers_count: int = 0
    following_count: int = 0
    creations_count: int = 0

    # Sales stats (from myself query - may be unavailable)
    total_sales_amount: float = 0.0
    total_sales_count: int = 0
    monthly_sales_amount: float = 0.0
    monthly_sales_count: int = 0
    sales_data_available: bool = False

    # Featured creations (only BY_PUBLICATION and BY_DOWNLOADS sorts available)
    latest_creation: CreationData = field(default_factory=CreationData)
    top_downloaded: CreationData = field(default_factory=CreationData)

    # Tracked external creations
    tracked_creations: dict[str, TrackedCreationData] = field(default_factory=dict)


def _parse_creation(creation_list: list[dict] | None) -> CreationData:
    """Parse a creation from API response."""
    if not creation_list:
        return CreationData()

    creation = creation_list[0]
    url = creation.get("shortUrl", "")
    if url and not url.startswith("http"):
        url = f"https://cults3d.com{url}"

    image_url = creation.get("illustrationImageUrl")

    # Parse publishedAt
    published_at = None
    pub_str = creation.get("publishedAt")
    if pub_str:
        try:
            published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    return CreationData(
        name=creation.get("name"),
        url=url or None,
        image_url=image_url,
        views_count=creation.get("viewsCount", 0) or 0,
        downloads_count=creation.get("downloadsCount", 0) or 0,
        likes_count=creation.get("likesCount", 0) or 0,
        published_at=published_at,
    )


def _parse_single_creation(creation_data: dict | None, slug: str) -> TrackedCreationData:
    """Parse a single creation from API response for tracked creations."""
    if not creation_data:
        return TrackedCreationData(slug=slug)

    url = creation_data.get("shortUrl", "")
    if url and not url.startswith("http"):
        url = f"https://cults3d.com{url}"

    image_url = creation_data.get("illustrationImageUrl")

    # Parse publishedAt and calculate 30-day window
    published_at = None
    window_start = None
    window_end = None
    is_within_30_days = False
    pub_str = creation_data.get("publishedAt")

    if pub_str:
        try:
            published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            window_start = published_at
            window_end = published_at + timedelta(days=30)
            now = datetime.now(timezone.utc)
            is_within_30_days = now <= window_end
        except (ValueError, TypeError):
            pass

    creator_data = creation_data.get("creator", {})
    creator = creator_data.get("nick") if creator_data else None

    return TrackedCreationData(
        slug=slug,
        name=creation_data.get("name"),
        url=url or None,
        image_url=image_url,
        creator=creator,
        published_at=published_at,
        views_count=creation_data.get("viewsCount", 0) or 0,
        downloads_count=creation_data.get("downloadsCount", 0) or 0,
        likes_count=creation_data.get("likesCount", 0) or 0,
        window_start=window_start,
        window_end=window_end,
        is_within_30_days=is_within_30_days,
    )


class Cults3DCoordinator(DataUpdateCoordinator[Cults3DData]):
    """Cults3D data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, username: str, api_key: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.config_entry = entry
        self._username = username
        self._api_key = api_key
        self._session = async_get_clientsession(hass)

    def _get_auth(self) -> BasicAuth:
        """Get HTTP Basic Auth for API requests."""
        return BasicAuth(self._username, self._api_key)

    @property
    def tracked_creation_slugs(self) -> list[str]:
        """Get list of tracked creation slugs from options."""
        return self.config_entry.options.get(CONF_TRACKED_CREATIONS, [])

    async def _async_execute_query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Cults3D API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        # Log query for debugging (first line only to identify which query)
        query_first_line = query.strip().split("\n")[0]
        _LOGGER.debug("Executing GraphQL query: %s", query_first_line)

        try:
            async with self._session.post(
                CULTS3D_GRAPHQL_ENDPOINT,
                json=payload,
                auth=self._get_auth(),
                headers={"Content-Type": "application/json"},
            ) as response:
                _LOGGER.debug("Response status: %s", response.status)

                if response.status == 401:
                    raise ConfigEntryAuthFailed("Invalid username or API key")
                if response.status == 403:
                    raise ConfigEntryAuthFailed(
                        "Access forbidden - check your API key permissions"
                    )
                if response.status != 200:
                    if raise_on_error:
                        raise UpdateFailed(
                            f"API request failed with status {response.status}"
                        )
                    return {"data": None, "errors": [{"message": f"HTTP {response.status}"}]}

                data = await response.json()
                _LOGGER.debug("Response data keys: %s", list(data.keys()) if data else "None")

                if "errors" in data and data["errors"]:
                    error_messages = [
                        err.get("message", "Unknown error") for err in data["errors"]
                    ]
                    error_str = "; ".join(error_messages)
                    _LOGGER.warning("GraphQL errors for query %s: %s", query_first_line, error_str)
                    if raise_on_error:
                        raise UpdateFailed(f"GraphQL error: {error_str}")

                return data

        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Authentication failed - check your credentials"
                ) from err
            if raise_on_error:
                raise UpdateFailed(f"API request failed: {err}") from err
            return {"data": None, "errors": [{"message": str(err)}]}
        except ClientError as err:
            if raise_on_error:
                raise UpdateFailed(f"Connection error: {err}") from err
            return {"data": None, "errors": [{"message": str(err)}]}

    async def async_validate_credentials(self) -> bool:
        """Validate the provided credentials by running a test query."""
        try:
            result = await self._async_execute_query(
                CULTS3D_VALIDATION_QUERY,
                {"nick": self._username},
            )
            user_data = result.get("data", {}).get("user")
            if user_data is None:
                _LOGGER.error("User '%s' not found on Cults3D", self._username)
                return False
            return True
        except ConfigEntryAuthFailed:
            return False
        except UpdateFailed as err:
            _LOGGER.error("Validation failed: %s", err)
            return False

    async def _fetch_tracked_creation(self, slug: str) -> TrackedCreationData:
        """Fetch data for a single tracked creation."""
        try:
            result = await self._async_execute_query(
                CULTS3D_CREATION_QUERY,
                {"slug": slug},
            )
            creation_data = result.get("data", {}).get("creation")
            return _parse_single_creation(creation_data, slug)
        except UpdateFailed as err:
            _LOGGER.warning("Failed to fetch tracked creation %s: %s", slug, err)
            return TrackedCreationData(slug=slug)

    async def _fetch_sales_data(self) -> tuple[float, int, float, int, bool]:
        """Fetch sales data from myself query. Returns defaults if unavailable."""
        total_sales_amount = 0.0
        total_sales_count = 0
        monthly_sales_amount = 0.0
        monthly_sales_count = 0
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        try:
            # Try to fetch sales data - this may fail for various reasons
            result = await self._async_execute_query(
                CULTS3D_SALES_QUERY,
                raise_on_error=False,
            )

            if "errors" in result and result["errors"]:
                _LOGGER.warning(
                    "Sales data unavailable: %s",
                    "; ".join(e.get("message", "") for e in result["errors"])
                )
                return 0.0, 0, 0.0, 0, False

            myself_data = result.get("data", {}).get("myself")
            if not myself_data:
                _LOGGER.info("No sales data available (myself query returned null)")
                return 0.0, 0, 0.0, 0, False

            sales_batch = myself_data.get("salesBatch", {})
            results = sales_batch.get("results", [])

            for sale in results:
                # income is { value: number } structure
                income_data = sale.get("income", {})
                income_value = float(income_data.get("value", 0) or 0) if income_data else 0.0
                total_sales_amount += income_value
                total_sales_count += 1

                # Check if sale is within last 30 days
                created_at_str = sale.get("createdAt")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        if created_at >= thirty_days_ago:
                            monthly_sales_amount += income_value
                            monthly_sales_count += 1
                    except (ValueError, TypeError):
                        pass

            return total_sales_amount, total_sales_count, monthly_sales_amount, monthly_sales_count, True

        except Exception as err:
            _LOGGER.warning("Failed to fetch sales data: %s", err)
            return 0.0, 0, 0.0, 0, False

    async def _fetch_creations_data(self) -> tuple[CreationData, CreationData]:
        """Fetch user creations data. Returns defaults if unavailable."""
        try:
            result = await self._async_execute_query(
                CULTS3D_CREATIONS_QUERY,
                {"nick": self._username},
                raise_on_error=False,
            )

            if "errors" in result and result["errors"]:
                _LOGGER.warning(
                    "Creations data unavailable: %s",
                    "; ".join(e.get("message", "") for e in result["errors"])
                )
                return CreationData(), CreationData()

            user_data = result.get("data", {}).get("user")
            if not user_data:
                return CreationData(), CreationData()

            latest = _parse_creation(user_data.get("latestCreation"))
            # For now, use the same as latest since we removed sorting
            top_downloaded = latest

            return latest, top_downloaded

        except Exception as err:
            _LOGGER.warning("Failed to fetch creations data: %s", err)
            return CreationData(), CreationData()

    async def _async_update_data(self) -> Cults3DData:
        """Fetch data from Cults3D API."""
        _LOGGER.debug("Starting Cults3D data update for user: %s", self._username)

        # Fetch main user data (this must succeed)
        result = await self._async_execute_query(
            CULTS3D_USER_QUERY,
            {"nick": self._username},
        )

        data = result.get("data", {})
        user_data = data.get("user")

        if user_data is None:
            raise UpdateFailed(f"User '{self._username}' not found")

        _LOGGER.debug("User data fetched successfully: %s", user_data.get("nick"))

        # Fetch creations data separately (optional - may fail)
        latest_creation, top_downloaded = await self._fetch_creations_data()

        # Fetch sales data separately (optional - may fail)
        (
            total_sales_amount,
            total_sales_count,
            monthly_sales_amount,
            monthly_sales_count,
            sales_available,
        ) = await self._fetch_sales_data()

        # Fetch tracked creations
        tracked_creations: dict[str, TrackedCreationData] = {}
        for slug in self.tracked_creation_slugs:
            tracked_data = await self._fetch_tracked_creation(slug)
            tracked_creations[slug] = tracked_data

        return Cults3DData(
            username=user_data.get("nick", self._username),
            followers_count=user_data.get("followersCount", 0) or 0,
            following_count=user_data.get("followeesCount", 0) or 0,
            creations_count=user_data.get("creationsCount", 0) or 0,
            total_sales_amount=total_sales_amount,
            total_sales_count=total_sales_count,
            monthly_sales_amount=monthly_sales_amount,
            monthly_sales_count=monthly_sales_count,
            sales_data_available=sales_available,
            latest_creation=latest_creation,
            top_downloaded=top_downloaded,
            tracked_creations=tracked_creations,
        )

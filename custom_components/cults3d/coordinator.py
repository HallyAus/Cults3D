"""DataUpdateCoordinator for Cults3D integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientResponseError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CULTS3D_GRAPHQL_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# GraphQL Queries - Easy to modify if the Cults3D schema changes
# =============================================================================
# These queries fetch user data and statistics from Cults3D.
#
# Schema notes:
# - `myself` returns authenticated user data including sales
# - `user(nick: "...")` returns public user profile data
# - Creations can be sorted: BY_PUBLICATION, BY_DOWNLOADS, BY_VIEWS, BY_SALES
# - `salesBatch` provides transaction history with income
#
# If the schema differs, adjust field names here.
# =============================================================================

# Main query combining user profile, creations stats, and sales data
# Uses `myself` for authenticated access to private data like sales
CULTS3D_FULL_QUERY = """
query GetFullUserData($nick: String!, $thirtyDaysAgo: ISO8601DateTime) {
  user(nick: $nick) {
    nick
    followersCount
    followeesCount
    creationsCount
    viewsCount

    # Latest creation (most recently published)
    latestCreation: creations(limit: 1, sort: BY_PUBLICATION, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }

    # Most downloaded creation (trending)
    topByDownloads: creations(limit: 1, sort: BY_DOWNLOADS, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }

    # Most profitable creation (by total sales)
    topBySales: creations(limit: 1, sort: BY_SALES, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }
  }

  myself {
    totalSalesAmount
    salesCount

    # Monthly sales - get sales from last 30 days
    monthlySales: salesBatch(limit: 100, since: $thirtyDaysAgo) {
      results {
        id
        income
        createdAt
        creation {
          name
        }
      }
    }

    # All-time sales count for statistics
    allSales: salesBatch(limit: 1) {
      totalCount
    }
  }
}
"""

# Fallback query if `myself` doesn't work - uses only public user data
CULTS3D_PUBLIC_QUERY = """
query GetPublicUserData($nick: String!) {
  user(nick: $nick) {
    nick
    followersCount
    followeesCount
    creationsCount
    viewsCount

    latestCreation: creations(limit: 1, sort: BY_PUBLICATION, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }

    topByDownloads: creations(limit: 1, sort: BY_DOWNLOADS, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }

    topBySales: creations(limit: 1, sort: BY_SALES, direction: DESC) {
      name
      url
      viewsCount
      downloadsCount
      likesCount
      totalSalesAmount
      salesCount
      illustrations(limit: 1) {
        url
      }
    }
  }
}
"""

# Validation query - simpler query to test authentication
CULTS3D_VALIDATION_QUERY = """
query ValidateAuth($nick: String!) {
  user(nick: $nick) {
    nick
  }
}
"""


@dataclass
class CreationData:
    """Data class for a single creation."""

    name: str | None = None
    url: str | None = None
    image_url: str | None = None
    views_count: int = 0
    downloads_count: int = 0
    likes_count: int = 0
    total_sales_amount: float = 0.0
    sales_count: int = 0


@dataclass
class Cults3DData:
    """Data class for Cults3D coordinator data."""

    username: str = ""

    # Profile stats
    followers_count: int = 0
    following_count: int = 0
    creations_count: int = 0
    total_views_count: int = 0

    # Sales stats (from myself query)
    total_sales_amount: float = 0.0
    total_sales_count: int = 0

    # Monthly stats
    monthly_sales_amount: float = 0.0
    monthly_sales_count: int = 0

    # Featured creations
    latest_creation: CreationData = field(default_factory=CreationData)
    top_downloaded: CreationData = field(default_factory=CreationData)
    most_profitable: CreationData = field(default_factory=CreationData)


def _parse_creation(creation_list: list[dict] | None) -> CreationData:
    """Parse a creation from API response."""
    if not creation_list:
        return CreationData()

    creation = creation_list[0]
    url = creation.get("url", "")
    if url and not url.startswith("http"):
        url = f"https://cults3d.com{url}"

    # Handle illustrations as an array (API returns array, not single object)
    illustrations = creation.get("illustrations", [])
    image_url = illustrations[0].get("url") if illustrations else None

    return CreationData(
        name=creation.get("name"),
        url=url or None,
        image_url=image_url,
        views_count=creation.get("viewsCount", 0) or 0,
        downloads_count=creation.get("downloadsCount", 0) or 0,
        likes_count=creation.get("likesCount", 0) or 0,
        total_sales_amount=float(creation.get("totalSalesAmount", 0) or 0),
        sales_count=creation.get("salesCount", 0) or 0,
    )


class Cults3DCoordinator(DataUpdateCoordinator[Cults3DData]):
    """Cults3D data update coordinator."""

    def __init__(self, hass: HomeAssistant, username: str, api_key: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._username = username
        self._api_key = api_key
        self._session = async_get_clientsession(hass)
        self._use_full_query = True  # Try full query first, fallback to public

    def _get_auth(self) -> BasicAuth:
        """Get HTTP Basic Auth for API requests."""
        return BasicAuth(self._username, self._api_key)

    async def _async_execute_query(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Cults3D API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            async with self._session.post(
                CULTS3D_GRAPHQL_ENDPOINT,
                json=payload,
                auth=self._get_auth(),
                headers={"Content-Type": "application/json"},
            ) as response:
                # Handle HTTP errors
                if response.status == 401:
                    raise ConfigEntryAuthFailed("Invalid username or API key")
                if response.status == 403:
                    raise ConfigEntryAuthFailed(
                        "Access forbidden - check your API key permissions"
                    )
                if response.status != 200:
                    raise UpdateFailed(
                        f"API request failed with status {response.status}"
                    )

                data = await response.json()

                # Handle GraphQL errors
                if "errors" in data and data["errors"]:
                    error_messages = [
                        err.get("message", "Unknown error") for err in data["errors"]
                    ]
                    error_str = "; ".join(error_messages)
                    _LOGGER.error("GraphQL errors: %s", error_str)
                    raise UpdateFailed(f"GraphQL error: {error_str}")

                return data

        except ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Authentication failed - check your credentials"
                ) from err
            raise UpdateFailed(f"API request failed: {err}") from err
        except ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    async def async_validate_credentials(self) -> bool:
        """Validate the provided credentials by running a test query."""
        try:
            result = await self._async_execute_query(
                CULTS3D_VALIDATION_QUERY,
                {"nick": self._username},
            )
            # Check if user data was returned
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

    async def _async_update_data(self) -> Cults3DData:
        """Fetch data from Cults3D API."""
        # Calculate date for monthly sales filter (30 days ago)
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"

        # Try full query first (includes myself for sales data)
        if self._use_full_query:
            try:
                result = await self._async_execute_query(
                    CULTS3D_FULL_QUERY,
                    {"nick": self._username, "thirtyDaysAgo": thirty_days_ago},
                )
                return self._parse_full_response(result)
            except UpdateFailed as err:
                # If full query fails, try public query
                _LOGGER.warning(
                    "Full query failed, falling back to public query: %s", err
                )
                self._use_full_query = False

        # Fallback to public query
        result = await self._async_execute_query(
            CULTS3D_PUBLIC_QUERY,
            {"nick": self._username},
        )
        return self._parse_public_response(result)

    def _parse_full_response(self, result: dict[str, Any]) -> Cults3DData:
        """Parse response from full query including myself data."""
        data = result.get("data", {})
        user_data = data.get("user")
        myself_data = data.get("myself")

        if user_data is None:
            raise UpdateFailed(f"User '{self._username}' not found")

        # Parse monthly sales
        monthly_amount = 0.0
        monthly_count = 0

        if myself_data:
            monthly_sales = myself_data.get("monthlySales", {}).get("results", [])
            for sale in monthly_sales:
                income = sale.get("income", 0)
                if income:
                    monthly_amount += float(income)
                    monthly_count += 1

        # Get total sales count from allSales if available
        total_sales_count = 0
        if myself_data:
            all_sales = myself_data.get("allSales", {})
            total_sales_count = all_sales.get("totalCount", 0) or 0
            # Fallback to salesCount if totalCount not available
            if not total_sales_count:
                total_sales_count = myself_data.get("salesCount", 0) or 0

        return Cults3DData(
            username=user_data.get("nick", self._username),
            followers_count=user_data.get("followersCount", 0) or 0,
            following_count=user_data.get("followeesCount", 0) or 0,
            creations_count=user_data.get("creationsCount", 0) or 0,
            total_views_count=user_data.get("viewsCount", 0) or 0,
            total_sales_amount=float(myself_data.get("totalSalesAmount", 0) or 0) if myself_data else 0.0,
            total_sales_count=total_sales_count,
            monthly_sales_amount=monthly_amount,
            monthly_sales_count=monthly_count,
            latest_creation=_parse_creation(user_data.get("latestCreation")),
            top_downloaded=_parse_creation(user_data.get("topByDownloads")),
            most_profitable=_parse_creation(user_data.get("topBySales")),
        )

    def _parse_public_response(self, result: dict[str, Any]) -> Cults3DData:
        """Parse response from public query (no myself data)."""
        user_data = result.get("data", {}).get("user")

        if user_data is None:
            raise UpdateFailed(f"User '{self._username}' not found")

        # For public query, we can estimate total sales from most profitable creation
        most_profitable = _parse_creation(user_data.get("topBySales"))

        return Cults3DData(
            username=user_data.get("nick", self._username),
            followers_count=user_data.get("followersCount", 0) or 0,
            following_count=user_data.get("followeesCount", 0) or 0,
            creations_count=user_data.get("creationsCount", 0) or 0,
            total_views_count=user_data.get("viewsCount", 0) or 0,
            total_sales_amount=0.0,  # Not available in public query
            total_sales_count=0,  # Not available in public query
            monthly_sales_amount=0.0,  # Not available in public query
            monthly_sales_count=0,  # Not available in public query
            latest_creation=_parse_creation(user_data.get("latestCreation")),
            top_downloaded=_parse_creation(user_data.get("topByDownloads")),
            most_profitable=most_profitable,
        )

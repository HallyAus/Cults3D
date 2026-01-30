"""DataUpdateCoordinator for Cults3D integration."""

from __future__ import annotations

import logging
from base64 import b64encode
from dataclasses import dataclass
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
# GraphQL Query - Easy to modify if the Cults3D schema changes
# =============================================================================
# This query fetches user data by nickname (username).
# Cults3D uses "nick" as the unique identifier for users.
# The query bundles all needed fields in a single request.
#
# Schema notes:
# - `user(nick: "...")` returns a User object
# - `followersCount` / `followingCount` are integers
# - `creationsCount` is the total number of creations
# - `creations(limit: 1)` returns the most recent creation(s)
#
# If the schema differs, adjust field names here.
# =============================================================================

CULTS3D_USER_QUERY = """
query GetUserData($nick: String!) {
  user(nick: $nick) {
    nick
    followersCount
    followingCount
    creationsCount
    creations(limit: 1) {
      name
      url
      illustration {
        url
      }
    }
  }
}
"""

# Fallback/validation query - simpler query to test authentication
CULTS3D_VALIDATION_QUERY = """
query ValidateAuth($nick: String!) {
  user(nick: $nick) {
    nick
  }
}
"""


@dataclass
class Cults3DData:
    """Data class for Cults3D coordinator data."""

    username: str
    followers_count: int
    following_count: int
    creations_count: int
    latest_creation_name: str | None
    latest_creation_url: str | None
    latest_creation_image: str | None


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
        result = await self._async_execute_query(
            CULTS3D_USER_QUERY,
            {"nick": self._username},
        )

        user_data = result.get("data", {}).get("user")
        if user_data is None:
            raise UpdateFailed(f"User '{self._username}' not found")

        # Extract latest creation info
        creations = user_data.get("creations", [])
        latest_creation = creations[0] if creations else None

        latest_name = None
        latest_url = None
        latest_image = None

        if latest_creation:
            latest_name = latest_creation.get("name")
            latest_url = latest_creation.get("url")
            # Handle the url - ensure it's a full URL
            if latest_url and not latest_url.startswith("http"):
                latest_url = f"https://cults3d.com{latest_url}"
            # Get illustration URL if available
            illustration = latest_creation.get("illustration")
            if illustration:
                latest_image = illustration.get("url")

        return Cults3DData(
            username=user_data.get("nick", self._username),
            followers_count=user_data.get("followersCount", 0),
            following_count=user_data.get("followingCount", 0),
            creations_count=user_data.get("creationsCount", 0),
            latest_creation_name=latest_name,
            latest_creation_url=latest_url,
            latest_creation_image=latest_image,
        )

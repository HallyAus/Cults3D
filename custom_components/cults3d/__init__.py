"""The Cults3D integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import Cults3DCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type Cults3DConfigEntry = ConfigEntry[Cults3DCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Cults3DConfigEntry) -> bool:
    """Set up Cults3D from a config entry."""
    username = entry.data[CONF_USERNAME]
    api_key = entry.data[CONF_API_KEY]

    coordinator = Cults3DCoordinator(hass, entry, username, api_key)

    # Perform initial data fetch
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # Re-raise auth failures to trigger reauth flow
        raise
    except Exception as err:
        _LOGGER.error("Error setting up Cults3D integration: %s", err)
        raise ConfigEntryNotReady(f"Failed to fetch initial data: {err}") from err

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: Cults3DConfigEntry) -> None:
    """Handle options update - reload integration to pick up tracked creations changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Cults3DConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

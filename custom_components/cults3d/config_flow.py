"""Config flow for Cults3D integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from aiohttp import BasicAuth

from .const import CONF_TRACKED_CREATIONS, CULTS3D_GRAPHQL_ENDPOINT, DOMAIN
from .coordinator import CULTS3D_VALIDATION_QUERY, extract_slug_from_url

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def _validate_credentials(hass, username: str, api_key: str) -> bool:
    """Validate credentials without needing a full coordinator."""
    session = async_get_clientsession(hass)
    auth = BasicAuth(username, api_key)

    try:
        async with session.post(
            CULTS3D_GRAPHQL_ENDPOINT,
            json={"query": CULTS3D_VALIDATION_QUERY, "variables": {"nick": username}},
            auth=auth,
            headers={"Content-Type": "application/json"},
        ) as response:
            if response.status != 200:
                return False
            data = await response.json()
            if "errors" in data and data["errors"]:
                return False
            user_data = data.get("data", {}).get("user")
            return user_data is not None
    except Exception:
        return False


class Cults3DConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cults3D."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return Cults3DOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            api_key = user_input[CONF_API_KEY].strip()

            # Check if already configured
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # Validate credentials
            try:
                is_valid = await _validate_credentials(self.hass, username, api_key)
            except Exception as err:
                _LOGGER.exception("Unexpected error during validation: %s", err)
                errors["base"] = "unknown"
            else:
                if is_valid:
                    return self.async_create_entry(
                        title=f"Cults3D ({username})",
                        data={
                            CONF_USERNAME: username,
                            CONF_API_KEY: api_key,
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization if credentials become invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = reauth_entry.data[CONF_USERNAME]
            api_key = user_input[CONF_API_KEY].strip()

            try:
                is_valid = await _validate_credentials(self.hass, username, api_key)
            except Exception as err:
                _LOGGER.exception("Unexpected error during reauth: %s", err)
                errors["base"] = "unknown"
            else:
                if is_valid:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data={
                            CONF_USERNAME: username,
                            CONF_API_KEY: api_key,
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "username": reauth_entry.data[CONF_USERNAME],
            },
        )


class Cults3DOptionsFlow(OptionsFlow):
    """Handle options flow for Cults3D."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options - main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["tracked_creations", "add_tracked_creation"],
        )

    async def async_step_tracked_creations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show current tracked creations and allow removal."""
        current_tracked = self.config_entry.options.get(CONF_TRACKED_CREATIONS, [])

        if user_input is not None:
            # Get selected slugs to keep (unchecked ones will be removed)
            selected = user_input.get("tracked_list", [])
            return self.async_create_entry(
                title="",
                data={CONF_TRACKED_CREATIONS: selected},
            )

        if not current_tracked:
            return self.async_show_form(
                step_id="tracked_creations",
                data_schema=vol.Schema({}),
                description_placeholders={"tracked_list": "None"},
            )

        # Create multi-select schema with current tracked creations
        return self.async_show_form(
            step_id="tracked_creations",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "tracked_list",
                        default=current_tracked,
                    ): vol.All(
                        vol.Coerce(list),
                        [vol.In(current_tracked)],
                    ),
                }
            ),
            description_placeholders={
                "tracked_count": str(len(current_tracked)),
            },
        )

    async def async_step_add_tracked_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new tracked creation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url_or_slug = user_input.get("creation_url", "").strip()

            if url_or_slug:
                slug = extract_slug_from_url(url_or_slug)
                current_tracked = list(
                    self.config_entry.options.get(CONF_TRACKED_CREATIONS, [])
                )

                if slug in current_tracked:
                    errors["base"] = "already_tracked"
                else:
                    # Add the new slug
                    current_tracked.append(slug)
                    return self.async_create_entry(
                        title="",
                        data={CONF_TRACKED_CREATIONS: current_tracked},
                    )
            else:
                errors["base"] = "invalid_url"

        return self.async_show_form(
            step_id="add_tracked_creation",
            data_schema=vol.Schema(
                {
                    vol.Required("creation_url"): str,
                }
            ),
            errors=errors,
        )

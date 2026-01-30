"""Config flow for Cults3D integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_USERNAME

from .const import DOMAIN
from .coordinator import Cults3DCoordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class Cults3DConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cults3D."""

    VERSION = 1

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
            coordinator = Cults3DCoordinator(self.hass, username, api_key)

            try:
                is_valid = await coordinator.async_validate_credentials()
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

            coordinator = Cults3DCoordinator(self.hass, username, api_key)

            try:
                is_valid = await coordinator.async_validate_credentials()
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

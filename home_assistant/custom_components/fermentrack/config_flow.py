"""Config flow for Fermentrack."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FermentrackApi, FermentrackAuthError, FermentrackConnectionError, FermentrackError
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://fermentrack.local"): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class FermentrackConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(self, data: Mapping[str, Any]) -> str | None:
        """Returns an error key, or None on success."""
        api = FermentrackApi(
            async_get_clientsession(self.hass, verify_ssl=data.get(CONF_VERIFY_SSL, True)),
            data[CONF_URL], data[CONF_TOKEN], data.get(CONF_VERIFY_SSL, True),
        )
        try:
            await api.get_devices()
        except FermentrackAuthError:
            return "invalid_auth"
        except FermentrackConnectionError:
            return "cannot_connect"
        except FermentrackError:
            return "unknown"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()
            if (error := await self._validate(user_input)) is None:
                return self.async_create_entry(title="Fermentrack", data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            if (error := await self._validate(data)) is None:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}), errors=errors
        )

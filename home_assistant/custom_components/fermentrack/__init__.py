"""The Fermentrack integration: control a BrewPi fermentation chamber through Fermentrack's /api/ha/ API."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FermentrackApi, FermentrackError
from .const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
    LOGGING_STATUSES,
    SERVICE_SET_LOGGING,
    SERVICE_START_BEER,
    SERVICE_START_PROFILE,
)
from .coordinator import FermentrackCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_DEVICE_ID = "device_id"
ATTR_PROFILE = "profile"
ATTR_START_AT_HOURS = "start_at_hours"
ATTR_NAME = "name"
ATTR_STATUS = "status"

START_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_PROFILE): cv.string,
        vol.Optional(ATTR_START_AT_HOURS): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
START_BEER_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_NAME): cv.string})
SET_LOGGING_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_STATUS): vol.In(LOGGING_STATUSES)}
)

type FermentrackConfigEntry = ConfigEntry[FermentrackCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions (services)."""

    def resolve(call: ServiceCall) -> tuple[FermentrackCoordinator, int]:
        """Map a Home Assistant device id onto (coordinator, Fermentrack device id)."""
        device = dr.async_get(hass).async_get(call.data[ATTR_DEVICE_ID])
        if device is None:
            raise ServiceValidationError("Unknown device")
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            entry_id, _, fermentrack_id = identifier.rpartition("_")
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError("The Fermentrack integration for this device is not loaded")
            return entry.runtime_data, int(fermentrack_id)
        raise ServiceValidationError("Device is not a Fermentrack controller")

    async def run(coordinator: FermentrackCoordinator, coro) -> None:
        try:
            await coro
        except FermentrackError as err:
            raise HomeAssistantError(f"Fermentrack rejected the request: {err}") from err
        await coordinator.async_request_refresh()

    async def start_profile(call: ServiceCall) -> None:
        coordinator, device_id = resolve(call)
        wanted = call.data[ATTR_PROFILE].strip()
        profiles = coordinator.data.profiles
        matches = [p for p in profiles if str(p["id"]) == wanted] or \
                  [p for p in profiles if p["name"].lower() == wanted.lower()]
        if len(matches) != 1:
            raise ServiceValidationError(
                f"Profile '{wanted}' not found (or ambiguous). Available: "
                + ", ".join(f"{p['name']} (#{p['id']})" for p in profiles)
            )
        await run(coordinator, coordinator.api.start_profile(device_id, matches[0]["id"],
                                                             call.data.get(ATTR_START_AT_HOURS)))

    async def start_beer(call: ServiceCall) -> None:
        coordinator, device_id = resolve(call)
        await run(coordinator, coordinator.api.start_beer(device_id, call.data[ATTR_NAME]))

    async def set_logging(call: ServiceCall) -> None:
        coordinator, device_id = resolve(call)
        await run(coordinator, coordinator.api.set_logging(device_id, call.data[ATTR_STATUS]))

    hass.services.async_register(DOMAIN, SERVICE_START_PROFILE, start_profile, schema=START_PROFILE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_START_BEER, start_beer, schema=START_BEER_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_LOGGING, set_logging, schema=SET_LOGGING_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FermentrackConfigEntry) -> bool:
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    api = FermentrackApi(
        async_get_clientsession(hass, verify_ssl=verify_ssl), entry.data[CONF_URL], entry.data[CONF_TOKEN], verify_ssl
    )
    coordinator = FermentrackCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FermentrackConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

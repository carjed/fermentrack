"""Fermentation profile selector for a Fermentrack temperature controller."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import FermentrackError
from .const import MODE_BEER_PROFILE
from .coordinator import FermentrackCoordinator
from .entity import FermentrackEntity

NO_PROFILE = "None"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FermentrackCoordinator = entry.runtime_data
    async_add_entities(FermentrackProfileSelect(coordinator, device_id) for device_id in coordinator.data.devices)


class FermentrackProfileSelect(FermentrackEntity, SelectEntity):
    """Shows the active fermentation profile; choosing one starts it from the beginning.

    Choosing "None" doesn't change anything on the controller; to leave profile mode, set a constant temperature or
    turn the thermostat off.
    """

    _attr_translation_key = "profile"

    def __init__(self, coordinator: FermentrackCoordinator, device_id: int) -> None:
        super().__init__(coordinator, device_id, "profile")

    def _labels(self) -> dict[str, int]:
        """Option label -> profile id. Duplicate names get the id appended so every option is unique."""
        profiles = self.coordinator.data.profiles
        names = [p["name"] for p in profiles]
        return {
            (p["name"] if names.count(p["name"]) == 1 else f"{p['name']} (#{p['id']})"): p["id"]
            for p in profiles
        }

    @property
    def options(self) -> list[str]:
        return [NO_PROFILE, *self._labels()]

    @property
    def current_option(self) -> str | None:
        active = self.device.get("active_profile")
        if self.device.get("mode") != MODE_BEER_PROFILE or not active:
            return NO_PROFILE
        for label, profile_id in self._labels().items():
            if profile_id == active["id"]:
                return label
        return NO_PROFILE

    async def async_select_option(self, option: str) -> None:
        if option == NO_PROFILE:
            return
        profile_id = self._labels().get(option)
        if profile_id is None:
            raise HomeAssistantError(f"Unknown fermentation profile {option}")
        try:
            await self.coordinator.api.start_profile(self.device_id, profile_id)
        except FermentrackError as err:
            raise HomeAssistantError(f"Fermentrack rejected the request: {err}") from err
        await self.coordinator.async_request_refresh()

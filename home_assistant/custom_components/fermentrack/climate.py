"""Climate entity for a Fermentrack temperature controller."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import FermentrackError
from .const import MODE_BEER_CONSTANT, MODE_BEER_PROFILE, MODE_FRIDGE_CONSTANT, MODE_OFF
from .coordinator import FermentrackCoordinator
from .entity import FermentrackEntity

PRESETS = [MODE_BEER_CONSTANT, MODE_FRIDGE_CONSTANT, MODE_BEER_PROFILE]

STATE_TO_ACTION = {
    "idle": HVACAction.IDLE,
    "state_off": HVACAction.OFF,
    "door_open": HVACAction.IDLE,
    "heating": HVACAction.HEATING,
    "heating_min_time": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
    "cooling_min_time": HVACAction.COOLING,
    "waiting_to_cool": HVACAction.IDLE,
    "waiting_to_heat": HVACAction.IDLE,
    "waiting_for_peak_detect": HVACAction.IDLE,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FermentrackCoordinator = entry.runtime_data
    async_add_entities(FermentrackClimate(coordinator, device_id) for device_id in coordinator.data.devices)


class FermentrackClimate(FermentrackEntity, ClimateEntity):
    """Fermentation chamber thermostat.

    hvac_mode is OFF or HEAT_COOL (the controller heats and cools as needed). The preset selects what is being
    controlled: the beer temperature, the fridge temperature, or a fermentation profile.
    """

    _attr_name = None  # Use the device name
    _attr_translation_key = "chamber"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_preset_modes = PRESETS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 0.1

    def __init__(self, coordinator: FermentrackCoordinator, device_id: int) -> None:
        super().__init__(coordinator, device_id, "climate")
        # Remember the last constant preset so turning back on (or setting a temperature) restores it
        mode = coordinator.data.devices[device_id].get("mode")
        self._last_constant_preset = mode if mode in (MODE_BEER_CONSTANT, MODE_FRIDGE_CONSTANT) else MODE_BEER_CONSTANT

    # --- State ---

    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.FAHRENHEIT if self.device.get("temp_format") == "F" else UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> float:
        return 28.0 if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else -2.0

    @property
    def max_temp(self) -> float:
        return 86.0 if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else 30.0

    @property
    def _mode(self) -> str | None:
        return self.device.get("mode")

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._mode is None:
            return None
        return HVACMode.OFF if self._mode == MODE_OFF else HVACMode.HEAT_COOL

    @property
    def hvac_action(self) -> HVACAction | None:
        if self._mode == MODE_OFF:
            return HVACAction.OFF
        return STATE_TO_ACTION.get(self.device.get("controller_state"))

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._mode in (MODE_BEER_CONSTANT, MODE_FRIDGE_CONSTANT):
            self._last_constant_preset = self._mode
        super()._handle_coordinator_update()

    @property
    def preset_mode(self) -> str | None:
        return self._mode if self._mode in PRESETS else None

    @property
    def current_temperature(self) -> float | None:
        if self._mode == MODE_FRIDGE_CONSTANT:
            return self.device.get("fridge_temp")
        return self.device.get("beer_temp")

    @property
    def target_temperature(self) -> float | None:
        if self._mode == MODE_FRIDGE_CONSTANT:
            return self.device.get("fridge_set")
        if self._mode in (MODE_BEER_CONSTANT, MODE_BEER_PROFILE):
            return self.device.get("beer_set")
        return None

    @property
    def current_humidity(self) -> float | None:
        return self.device.get("fridge_humidity")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile = self.device.get("active_profile")
        beer = self.device.get("active_beer")
        return {
            "beer_temperature": self.device.get("beer_temp"),
            "fridge_temperature": self.device.get("fridge_temp"),
            "room_temperature": self.device.get("room_temp"),
            "controller_state": self.device.get("controller_state"),
            "active_profile": profile["name"] if profile else None,
            "profile_started": self.device.get("profile_started"),
            "active_beer": beer["name"] if beer else None,
            "logging_status": self.device.get("logging_status"),
        }

    # --- Commands ---

    async def _set_mode(self, mode: str, temperature: float | None = None) -> None:
        try:
            await self.coordinator.api.set_mode(self.device_id, mode, temperature)
        except FermentrackError as err:
            raise HomeAssistantError(f"Fermentrack rejected the request: {err}") from err
        await self.coordinator.async_request_refresh()

    def _fallback_target(self, preset: str) -> float:
        key = "fridge_set" if preset == MODE_FRIDGE_CONSTANT else "beer_set"
        for candidate in (self.device.get(key), self.target_temperature, self.current_temperature):
            if candidate is not None:
                return candidate
        raise ServiceValidationError("No target temperature known yet - set a temperature instead")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if kwargs.get(ATTR_HVAC_MODE) == HVACMode.OFF:
            await self._set_mode(MODE_OFF)
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        # Setting a temperature while off or on a profile switches to the last-used constant mode
        preset = self._mode if self._mode in (MODE_BEER_CONSTANT, MODE_FRIDGE_CONSTANT) else self._last_constant_preset
        await self._set_mode(preset, float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._set_mode(MODE_OFF)
        elif self.hvac_mode != HVACMode.HEAT_COOL:
            preset = self._last_constant_preset
            await self._set_mode(preset, self._fallback_target(preset))

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == MODE_BEER_PROFILE:
            raise ServiceValidationError(
                "Choose a fermentation profile with the profile select entity or the fermentrack.start_profile action"
            )
        self._last_constant_preset = preset_mode
        await self._set_mode(preset_mode, self._fallback_target(preset_mode))

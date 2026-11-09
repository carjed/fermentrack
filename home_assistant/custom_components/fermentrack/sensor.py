"""Sensors for a Fermentrack temperature controller."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONTROLLER_STATES, LOGGING_STATUSES
from .coordinator import FermentrackCoordinator
from .entity import FermentrackEntity


@dataclass(frozen=True, kw_only=True)
class FermentrackSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    is_temperature: bool = False


def _name(obj: dict | None) -> str | None:
    return obj["name"] if obj else None


SENSORS: tuple[FermentrackSensorDescription, ...] = (
    FermentrackSensorDescription(
        key="beer_temp", translation_key="beer_temp", device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT, is_temperature=True, value_fn=lambda d: d.get("beer_temp"),
    ),
    FermentrackSensorDescription(
        key="fridge_temp", translation_key="fridge_temp", device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT, is_temperature=True, value_fn=lambda d: d.get("fridge_temp"),
    ),
    FermentrackSensorDescription(
        key="room_temp", translation_key="room_temp", device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT, is_temperature=True, value_fn=lambda d: d.get("room_temp"),
    ),
    FermentrackSensorDescription(
        key="beer_set", translation_key="beer_set", device_class=SensorDeviceClass.TEMPERATURE,
        is_temperature=True, value_fn=lambda d: d.get("beer_set"),
    ),
    FermentrackSensorDescription(
        key="fridge_set", translation_key="fridge_set", device_class=SensorDeviceClass.TEMPERATURE,
        is_temperature=True, value_fn=lambda d: d.get("fridge_set"),
    ),
    FermentrackSensorDescription(
        key="fridge_humidity", translation_key="fridge_humidity", device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.get("fridge_humidity"),
    ),
    FermentrackSensorDescription(
        key="controller_state", translation_key="controller_state", device_class=SensorDeviceClass.ENUM,
        options=CONTROLLER_STATES, value_fn=lambda d: d.get("controller_state"),
    ),
    FermentrackSensorDescription(
        key="logging_status", translation_key="logging_status", device_class=SensorDeviceClass.ENUM,
        options=LOGGING_STATUSES, value_fn=lambda d: d.get("logging_status"),
    ),
    FermentrackSensorDescription(
        key="active_beer", translation_key="active_beer", value_fn=lambda d: _name(d.get("active_beer")),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FermentrackCoordinator = entry.runtime_data
    async_add_entities(
        FermentrackSensor(coordinator, device_id, description)
        for device_id in coordinator.data.devices
        for description in SENSORS
    )


class FermentrackSensor(FermentrackEntity, SensorEntity):
    entity_description: FermentrackSensorDescription

    def __init__(self, coordinator: FermentrackCoordinator, device_id: int,
                 description: FermentrackSensorDescription) -> None:
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.is_temperature:
            return UnitOfTemperature.FAHRENHEIT if self.device.get("temp_format") == "F" else UnitOfTemperature.CELSIUS
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device)

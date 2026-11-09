"""Base entity for Fermentrack."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FermentrackCoordinator


class FermentrackEntity(CoordinatorEntity[FermentrackCoordinator]):
    """An entity tied to one Fermentrack temperature controller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FermentrackCoordinator, device_id: int, key: str) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{device_id}_{key}"
        device = coordinator.data.devices[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{device_id}")},
            name=device["name"],
            manufacturer="BrewPi / Fermentrack",
            model=device.get("board_type"),
            configuration_url=coordinator.config_entry.data["url"].rstrip("/") + f"/devices/{device_id}/dashboard/",
        )

    @property
    def device(self) -> dict[str, Any]:
        return self.coordinator.data.devices.get(self.device_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self.device.get("available"))

"""Data update coordinator for Fermentrack."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FermentrackApi, FermentrackAuthError, FermentrackError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FermentrackData:
    """Snapshot of everything we poll from Fermentrack."""

    devices: dict[int, dict[str, Any]] = field(default_factory=dict)
    profiles: list[dict[str, Any]] = field(default_factory=list)


class FermentrackCoordinator(DataUpdateCoordinator[FermentrackData]):
    """Polls all Fermentrack temperature controllers plus the list of fermentation profiles."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: FermentrackApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> FermentrackData:
        try:
            state = await self.api.get_state()
        except FermentrackAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FermentrackError as err:
            raise UpdateFailed(f"Error communicating with Fermentrack: {err}") from err

        return FermentrackData(devices={d["id"]: d for d in state["devices"]}, profiles=state["profiles"])

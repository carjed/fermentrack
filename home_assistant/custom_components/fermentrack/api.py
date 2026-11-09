"""Async client for the Fermentrack Home Assistant API (/api/ha/)."""
from __future__ import annotations

from typing import Any

import aiohttp


class FermentrackError(Exception):
    """Generic Fermentrack API error."""


class FermentrackAuthError(FermentrackError):
    """The API token was rejected (or the API is disabled)."""


class FermentrackConnectionError(FermentrackError):
    """Fermentrack could not be reached."""


class FermentrackApi:
    """Thin wrapper around the Fermentrack /api/ha/ endpoints."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str, verify_ssl: bool = True) -> None:
        self._session = session
        self._base = url.rstrip("/") + "/api/ha/"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._ssl = None if verify_ssl else False

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                self._base + path,
                headers=self._headers,
                json=json,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    data = {}
                if resp.status in (401, 403):
                    raise FermentrackAuthError(data.get("error", "Authentication failed"))
                if resp.status >= 400:
                    raise FermentrackError(data.get("error", f"HTTP {resp.status}"))
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FermentrackConnectionError(str(err)) from err

    async def get_state(self) -> dict[str, Any]:
        """Full state of every device plus the assignable profiles, in one request."""
        return await self._request("GET", "state/")

    async def get_devices(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "devices/"))["devices"]

    async def get_device(self, device_id: int) -> dict[str, Any]:
        return await self._request("GET", f"devices/{device_id}/")

    async def get_profiles(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "profiles/"))["profiles"]

    async def set_mode(self, device_id: int, mode: str, temperature: float | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"mode": mode}
        if temperature is not None:
            body["temperature"] = temperature
        return await self._request("POST", f"devices/{device_id}/mode/", body)

    async def start_profile(self, device_id: int, profile_id: int, start_at_hours: float | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"profile_id": profile_id}
        if start_at_hours is not None:
            body["start_at_hours"] = start_at_hours
        return await self._request("POST", f"devices/{device_id}/profile/", body)

    async def start_beer(self, device_id: int, name: str) -> dict[str, Any]:
        return await self._request("POST", f"devices/{device_id}/beer/", {"name": name})

    async def set_logging(self, device_id: int, status: str) -> dict[str, Any]:
        return await self._request("POST", f"devices/{device_id}/logging/", {"status": status})

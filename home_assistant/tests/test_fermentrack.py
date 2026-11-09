import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

URL = "http://ft.local"
BASE = URL + "/api/ha/"

STATE = {
    "id": 1, "name": "Chamber", "temp_format": "C", "status": "active", "board_type": "uno", "available": True,
    "mode": "beer_constant", "beer_temp": 19.5, "fridge_temp": 17.2, "room_temp": None, "fridge_humidity": 61.0,
    "beer_set": 20.0, "fridge_set": 16.0, "controller_state": "cooling", "controller_state_id": 4,
    "log_interval": 60.0, "logging_status": "active", "active_beer": {"id": 3, "name": "IPA"},
    "active_profile": None, "profile_started": None, "profile_temp": None,
}


def mock_api(aioclient_mock, state=STATE):
    aioclient_mock.get(BASE + "devices/", json={"devices": [{k: state[k] for k in ("id", "name", "temp_format", "status", "board_type")}]})
    aioclient_mock.get(BASE + "state/", json={
        "devices": [state], "profiles": [{"id": 7, "name": "Lager", "type": "Standard Profile"}]})
    for ep in ("mode", "profile", "beer", "logging"):
        aioclient_mock.post(BASE + f"devices/1/{ep}/", json={"ok": True})


async def setup(hass, aioclient_mock):
    mock_api(aioclient_mock)
    entry = MockConfigEntry(domain="fermentrack", data={"url": URL, "token": "t", "verify_ssl": True})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def posts(aioclient_mock):
    return [(str(url), data) for method, url, data, _ in aioclient_mock.mock_calls if method == "POST"]


async def test_entities(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    climate = hass.states.get("climate.chamber")
    assert climate.state == "heat_cool"
    assert climate.attributes["current_temperature"] == 19.5
    assert climate.attributes["temperature"] == 20.0
    assert climate.attributes["current_humidity"] == 61.0
    assert climate.attributes["hvac_action"] == "cooling"
    assert climate.attributes["preset_mode"] == "beer_constant"
    assert hass.states.get("sensor.chamber_fridge_humidity").state == "61.0"
    assert hass.states.get("sensor.chamber_controller_state").state == "cooling"
    assert hass.states.get("sensor.chamber_active_beer").state == "IPA"
    assert hass.states.get("sensor.chamber_room_temperature").state == "unknown"
    sel = hass.states.get("select.chamber_fermentation_profile")
    assert sel.state == "None" and sel.attributes["options"] == ["None", "Lager"]


async def test_climate_commands(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    await hass.services.async_call("climate", "set_temperature", {"entity_id": "climate.chamber", "temperature": 18.0}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {"entity_id": "climate.chamber", "preset_mode": "fridge_constant"}, blocking=True)
    await hass.services.async_call("climate", "turn_off", {"entity_id": "climate.chamber"}, blocking=True)
    assert posts(aioclient_mock) == [
        (BASE + "devices/1/mode/", {"mode": "beer_constant", "temperature": 18.0}),
        (BASE + "devices/1/mode/", {"mode": "fridge_constant", "temperature": 16.0}),
        (BASE + "devices/1/mode/", {"mode": "off"}),
    ]
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("climate", "set_preset_mode", {"entity_id": "climate.chamber", "preset_mode": "beer_profile"}, blocking=True)


async def test_select_and_services(hass: HomeAssistant, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    await hass.services.async_call("select", "select_option", {"entity_id": "select.chamber_fermentation_profile", "option": "Lager"}, blocking=True)
    device = dr.async_get(hass).async_get_device(identifiers={("fermentrack", f"{entry.entry_id}_1")})
    await hass.services.async_call("fermentrack", "start_profile", {"device_id": device.id, "profile": "lager", "start_at_hours": 24}, blocking=True)
    await hass.services.async_call("fermentrack", "start_beer", {"device_id": device.id, "name": "Stout"}, blocking=True)
    await hass.services.async_call("fermentrack", "set_logging", {"device_id": device.id, "status": "paused"}, blocking=True)
    assert posts(aioclient_mock) == [
        (BASE + "devices/1/profile/", {"profile_id": 7}),
        (BASE + "devices/1/profile/", {"profile_id": 7, "start_at_hours": 24.0}),
        (BASE + "devices/1/beer/", {"name": "Stout"}),
        (BASE + "devices/1/logging/", {"status": "paused"}),
    ]


async def test_auth_failure_triggers_reauth(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(BASE + "state/", status=401, json={"error": "Invalid or missing API token"})
    entry = MockConfigEntry(domain="fermentrack", data={"url": URL, "token": "bad", "verify_ssl": True})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["step_id"] == "reauth_confirm" for f in hass.config_entries.flow.async_progress())


async def test_polls_with_single_request(hass: HomeAssistant, aioclient_mock):
    await setup(hass, aioclient_mock)
    gets = [str(url) for method, url, _, _ in aioclient_mock.mock_calls if method == "GET"]
    assert gets == [BASE + "state/"]


async def test_config_flow(hass: HomeAssistant, aioclient_mock):
    mock_api(aioclient_mock)
    result = await hass.config_entries.flow.async_init("fermentrack", context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": URL + "/", "token": "t", "verify_ssl": True})
    assert result["type"] == "create_entry"
    assert result["data"]["url"] == URL

# Fermentrack ↔ Home Assistant

This directory contains a Home Assistant custom integration that monitors and controls Fermentrack's BrewPi
temperature controllers through Fermentrack's token-authenticated JSON API (`/api/ha/`).

## 1. Enable the API in Fermentrack

On the Fermentrack host (inside the container if you run Fermentrack in Docker), run:

```bash
python manage.py ha_api_token --regenerate   # prints a new token
python manage.py ha_api_token                # shows the current token
python manage.py ha_api_token --disable      # clears the token, which disables the API
```

You can also edit the token directly at `/admin/constance/config/` (the **Home Assistant API** section).
While the token is blank, every `/api/ha/` endpoint returns 403.

## 2. Install the integration

1. Copy `custom_components/fermentrack/` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Fermentrack** and enter the Fermentrack URL
   (for example `http://fermentrack.local`) and the token.

Each BrewPi controller shows up as a device with these entities:

| Entity | Description |
|---|---|
| `climate.<name>` | Thermostat. Off / Heat-Cool; presets `beer_constant`, `fridge_constant`, `beer_profile`. Shows beer temperature, setpoint and fridge humidity. Setting a temperature while off or running a profile switches to the last-used constant mode. |
| `sensor.<name>_beer_temperature`, `_fridge_temperature`, `_room_temperature` | Temperature readings |
| `sensor.<name>_beer_setpoint`, `_fridge_setpoint` | Current setpoints |
| `sensor.<name>_fridge_humidity` | Fridge humidity |
| `sensor.<name>_controller_state` | idle / heating / cooling / waiting_to_cool / … |
| `sensor.<name>_logging_status`, `_active_beer` | Beer log status |
| `select.<name>_fermentation_profile` | Choosing a profile starts it from the beginning |

Actions (services):

```yaml
action: fermentrack.start_profile
data:
  device_id: <HA device id>
  profile: "Lager"        # name or numeric id
  start_at_hours: 48      # optional: start 48 hours into the profile

action: fermentrack.start_beer
data:
  device_id: <HA device id>
  name: "Oktoberfest 2026"

action: fermentrack.set_logging
data:
  device_id: <HA device id>
  status: paused          # active | paused | stopped
```

The integration polls `/api/ha/state/` every 30 seconds (one request per poll). If you add a controller in Fermentrack, reload the integration to pick it up.

Example dashboard card:

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.chamber
    features:
      - type: climate-preset-modes
        style: dropdown
  - type: entities
    entities:
      - sensor.chamber_fridge_temperature
      - sensor.chamber_fridge_humidity
      - sensor.chamber_controller_state
      - select.chamber_fermentation_profile
      - sensor.chamber_active_beer
```

## API reference

Every request needs the header `Authorization: Bearer <token>`. Temperatures use the device's own unit
(`temp_format` is `C` or `F`). A reading that brewpi.py hasn't reported yet (0 or missing) comes back as `null`.

| Method | Path | Body |
|---|---|---|
| GET | `/api/ha/state/` | — (every device's full state plus profiles; what the integration polls) |
| GET | `/api/ha/devices/` | — |
| GET | `/api/ha/devices/<id>/` | — (full state; `available: false` if brewpi.py can't be reached) |
| POST | `/api/ha/devices/<id>/mode/` | `{"mode": "off"}` or `{"mode": "beer_constant" \| "fridge_constant", "temperature": 18.5}` |
| POST | `/api/ha/devices/<id>/profile/` | `{"profile_id": 3, "start_at_hours": 0}` |
| POST | `/api/ha/devices/<id>/beer/` | `{"name": "My Beer"}` |
| POST | `/api/ha/devices/<id>/logging/` | `{"status": "active" \| "paused" \| "stopped"}` |
| GET | `/api/ha/profiles/` | — |

```bash
curl -H "Authorization: Bearer $TOKEN" http://fermentrack.local/api/ha/devices/1/
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"mode":"beer_constant","temperature":19}' http://fermentrack.local/api/ha/devices/1/mode/
```

## Tests

- Fermentrack API: `python manage.py test app` (from the repo root)
- HA integration: `pip install pytest-homeassistant-custom-component && pytest tests` (from this directory)

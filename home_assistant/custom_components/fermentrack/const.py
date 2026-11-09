"""Constants for the Fermentrack integration."""
from datetime import timedelta

DOMAIN = "fermentrack"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

MODE_OFF = "off"
MODE_BEER_CONSTANT = "beer_constant"
MODE_FRIDGE_CONSTANT = "fridge_constant"
MODE_BEER_PROFILE = "beer_profile"

LOGGING_STATUSES = ["active", "paused", "stopped"]

CONTROLLER_STATES = [
    "idle",
    "state_off",
    "door_open",
    "heating",
    "cooling",
    "waiting_to_cool",
    "waiting_to_heat",
    "waiting_for_peak_detect",
    "cooling_min_time",
    "heating_min_time",
]

SERVICE_START_PROFILE = "start_profile"
SERVICE_START_BEER = "start_beer"
SERVICE_SET_LOGGING = "set_logging"

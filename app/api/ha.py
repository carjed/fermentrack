"""
JSON API intended for Home Assistant (or any other automation client).

All endpoints live under /api/ha/ and require an "Authorization: Bearer <token>" header matching the HA_API_TOKEN
Constance setting. If HA_API_TOKEN is blank, the API is disabled. Generate a token with:

    python manage.py ha_api_token --regenerate

Responses are plain JSON with numeric values (no HTML formatting), so they are easy to consume programmatically.
"""
import datetime
import hmac
import json
import logging
from functools import wraps

from constance import config
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.models import BrewPiDevice, Beer, BeerLogPoint, FermentationProfile

logger = logging.getLogger(__name__)

# Device mode letters (as used by brewpi.py) <-> API mode names
MODE_LETTER_TO_NAME = {
    'o': 'off',
    'b': 'beer_constant',
    'f': 'fridge_constant',
    'p': 'beer_profile',
}
CONSTANT_MODES = ('off', 'beer_constant', 'fridge_constant')

# Controller state integers -> lowercase names (from BeerLogPoint.STATE_CHOICES)
STATE_NAMES = {num: name.lower() for num, name in BeerLogPoint.STATE_CHOICES}

# Map the API's logging status names onto BrewPiDevice.manage_logging() actions
LOGGING_STATUS_TO_ACTION = {
    BrewPiDevice.DATA_LOGGING_ACTIVE: 'resume',
    BrewPiDevice.DATA_LOGGING_PAUSED: 'pause',
    BrewPiDevice.DATA_LOGGING_STOPPED: 'stop',
}


# --- Helpers -----------------------------------------------------------------------------------------------------------

def _error(message, status):
    return JsonResponse({'error': message}, status=status)


def ha_api_token_required(view_func):
    """Requires a valid bearer token (HA_API_TOKEN). Also makes the view CSRF-exempt, since token auth is used."""
    @csrf_exempt
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        expected = config.HA_API_TOKEN or ''
        if not expected:
            return _error('API disabled: no HA_API_TOKEN configured', 403)

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        scheme, _, provided = auth_header.partition(' ')
        if scheme.lower() != 'bearer' or not hmac.compare_digest(provided.strip().encode(), expected.encode()):
            return _error('Invalid or missing API token', 401)

        return view_func(request, *args, **kwargs)
    return _wrapped


def require_method(method):
    """Returns a JSON 405 for any HTTP method other than the one given."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.method != method:
                resp = _error('Method not allowed', 405)
                resp['Allow'] = method
                return resp
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _parse_json_body(request):
    """Returns (data, error_response)."""
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return None, _error('Request body must be valid JSON', 400)
    if not isinstance(data, dict):
        return None, _error('Request body must be a JSON object', 400)
    return data, None


def _get_device(device_id):
    try:
        return BrewPiDevice.objects.get(id=device_id)
    except BrewPiDevice.DoesNotExist:
        return None


def _reading(value):
    """brewpi.py initializes readings to 0/None before the first read from the controller - treat both as unknown."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if value == 0 else value


def _device_summary(device):
    return {
        'id': device.id,
        'name': device.device_name,
        'temp_format': device.temp_format,
        'status': device.status,
        'board_type': device.board_type,
    }


def _device_state(device):
    info = device.get_dashpanel_info()
    available = info is not None
    info = info or {}

    mode_letter = info.get('Mode')
    state_num = info.get('State')
    try:
        state_num = int(state_num) if state_num is not None else None
    except (TypeError, ValueError):
        state_num = None

    profile_temp = None
    if device.active_profile is not None and device.time_profile_started is not None:
        try:
            profile_temp = device.get_profile_temp()
        except Exception:  # Profile math can fail on odd profiles - this is informational only
            profile_temp = None

    state = _device_summary(device)
    state.update({
        'available': available,
        'mode': MODE_LETTER_TO_NAME.get(mode_letter) if available else None,
        'beer_temp': _reading(info.get('BeerTemp')),
        'fridge_temp': _reading(info.get('FridgeTemp')),
        'room_temp': _reading(info.get('RoomTemp')),
        'fridge_humidity': _reading(info.get('FridgeHumidity')),
        'beer_set': _reading(info.get('BeerSet')),
        'fridge_set': _reading(info.get('FridgeSet')),
        'controller_state': STATE_NAMES.get(state_num),
        'controller_state_id': state_num,
        'log_interval': info.get('LogInterval'),
        'logging_status': device.logging_status,
        'active_beer': {'id': device.active_beer.id, 'name': device.active_beer.name}
        if device.active_beer is not None else None,
        'active_profile': {'id': device.active_profile.id, 'name': device.active_profile.name}
        if device.active_profile is not None else None,
        'profile_started': device.time_profile_started.isoformat() if device.time_profile_started else None,
        'profile_temp': profile_temp,
    })
    return state


def _assignable_profiles():
    profiles = [p for p in FermentationProfile.objects.all().order_by('name') if p.is_assignable()]
    return [{'id': p.id, 'name': p.name, 'type': p.profile_type} for p in profiles]


# --- Endpoints ---------------------------------------------------------------------------------------------------------

@ha_api_token_required
@require_method('GET')
def device_list(request):
    devices = BrewPiDevice.objects.all().order_by('device_name')
    return JsonResponse({'devices': [_device_summary(d) for d in devices]})


@ha_api_token_required
@require_method('GET')
def device_detail(request, device_id):
    device = _get_device(device_id)
    if device is None:
        return _error('Device not found', 404)
    return JsonResponse(_device_state(device))


@ha_api_token_required
@require_method('POST')
def device_set_mode(request, device_id):
    """POST {"mode": "off" | "beer_constant" | "fridge_constant", "temperature": float}"""
    device = _get_device(device_id)
    if device is None:
        return _error('Device not found', 404)
    data, resp = _parse_json_body(request)
    if resp is not None:
        return resp

    mode = data.get('mode')
    if mode not in CONSTANT_MODES:
        return _error("'mode' must be one of: {} (use the profile endpoint for beer_profile)".format(
            ', '.join(CONSTANT_MODES)), 400)

    set_temp = None
    if mode != 'off':
        try:
            set_temp = float(data['temperature'])
        except (KeyError, TypeError, ValueError):
            return _error("'temperature' (number) is required for mode {}".format(mode), 400)

    try:
        device.set_temp_control(method=mode, set_temp=set_temp)
    except ValueError as e:
        return _error(str(e), 400)

    return JsonResponse({'ok': True, 'mode': mode, 'temperature': set_temp})


@ha_api_token_required
@require_method('POST')
def device_set_profile(request, device_id):
    """POST {"profile_id": int, "start_at_hours": float (optional)}"""
    device = _get_device(device_id)
    if device is None:
        return _error('Device not found', 404)
    data, resp = _parse_json_body(request)
    if resp is not None:
        return resp

    try:
        profile_id = int(data['profile_id'])
    except (KeyError, TypeError, ValueError):
        return _error("'profile_id' (integer) is required", 400)

    try:
        profile = FermentationProfile.objects.get(id=profile_id)
    except FermentationProfile.DoesNotExist:
        return _error('Fermentation profile not found', 404)
    if not profile.is_assignable():
        return _error('Fermentation profile is not assignable', 400)

    start_at = None
    if data.get('start_at_hours') is not None:
        try:
            hours = float(data['start_at_hours'])
        except (TypeError, ValueError):
            return _error("'start_at_hours' must be a number", 400)
        if hours < 0:
            return _error("'start_at_hours' must not be negative", 400)
        start_at = datetime.timedelta(hours=hours)

    try:
        device.set_temp_control(method='beer_profile', profile=profile.id, profile_startat=start_at)
    except ValueError as e:
        return _error(str(e), 400)

    return JsonResponse({'ok': True, 'mode': 'beer_profile',
                         'profile': {'id': profile.id, 'name': profile.name}})


@ha_api_token_required
@require_method('POST')
def device_start_beer(request, device_id):
    """POST {"name": str} - creates (or reuses) a beer log on this device and starts logging to it"""
    device = _get_device(device_id)
    if device is None:
        return _error('Device not found', 404)
    data, resp = _parse_json_body(request)
    if resp is not None:
        return resp

    name = data.get('name')
    if not isinstance(name, str) or not name.strip():
        return _error("'name' (string) is required", 400)
    name = name.strip()
    if len(name) > 255 or not Beer.name_is_valid(name):
        return _error('Beer name must only consist of letters, numbers, dashes, spaces, and underscores', 400)

    beer, created, gravity_started = Beer.create_and_start_on_device(device=device, name=name)
    return JsonResponse({'ok': True, 'beer': {'id': beer.id, 'name': beer.name}, 'created': created,
                         'gravity_logging_started': gravity_started})


@ha_api_token_required
@require_method('POST')
def device_set_logging(request, device_id):
    """POST {"status": "active" | "paused" | "stopped"}"""
    device = _get_device(device_id)
    if device is None:
        return _error('Device not found', 404)
    data, resp = _parse_json_body(request)
    if resp is not None:
        return resp

    status = data.get('status')
    if status not in LOGGING_STATUS_TO_ACTION:
        return _error("'status' must be one of: {}".format(', '.join(LOGGING_STATUS_TO_ACTION)), 400)
    if status != BrewPiDevice.DATA_LOGGING_STOPPED and device.active_beer is None:
        return _error('No active beer on this device - start a beer first', 400)

    device.manage_logging(status=LOGGING_STATUS_TO_ACTION[status])
    return JsonResponse({'ok': True, 'logging_status': device.logging_status})


@ha_api_token_required
@require_method('GET')
def profile_list(request):
    return JsonResponse({'profiles': _assignable_profiles()})


@ha_api_token_required
@require_method('GET')
def state(request):
    """Everything Home Assistant polls for, in one request: full state of every device plus assignable profiles"""
    devices = BrewPiDevice.objects.all().order_by('device_name')
    return JsonResponse({'devices': [_device_state(d) for d in devices], 'profiles': _assignable_profiles()})

import json
from unittest import mock

from constance.test import override_config
from django.test import TestCase
from django.urls import reverse

from app.models import BrewPiDevice, Beer, FermentationProfile

TOKEN = 'test-token-123'

DASH_INFO = {
    'BeerTemp': 19.5, 'FridgeTemp': 17.25, 'BeerAnn': None, 'FridgeAnn': None, 'FridgeHumidity': 61.0,
    'RoomTemp': None, 'State': 4, 'BeerSet': 20.0, 'FridgeSet': 0, 'LogInterval': 60.0, 'Mode': 'b',
}


@override_config(HA_API_TOKEN=TOKEN)
class HomeAssistantApiTests(TestCase):
    def setUp(self):
        self.device = BrewPiDevice.objects.create(device_name='Chamber', temp_format='C')
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer ' + TOKEN}

    def post_json(self, url_name, body, **kwargs):
        return self.client.post(reverse(url_name, kwargs={'device_id': self.device.id}),
                                data=json.dumps(body), content_type='application/json', **{**self.auth, **kwargs})

    # --- Auth ---

    def test_missing_token_rejected(self):
        resp = self.client.get(reverse('ha_device_list'))
        self.assertEqual(resp.status_code, 401)

    def test_wrong_token_rejected(self):
        resp = self.client.get(reverse('ha_device_list'), HTTP_AUTHORIZATION='Bearer nope')
        self.assertEqual(resp.status_code, 401)

    @override_config(HA_API_TOKEN='')
    def test_api_disabled_without_configured_token(self):
        resp = self.client.get(reverse('ha_device_list'), HTTP_AUTHORIZATION='Bearer ')
        self.assertEqual(resp.status_code, 403)

    def test_wrong_method(self):
        resp = self.client.post(reverse('ha_device_list'), **self.auth)
        self.assertEqual(resp.status_code, 405)

    # --- Reads ---

    def test_device_list(self):
        resp = self.client.get(reverse('ha_device_list'), **self.auth)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['devices'][0]['name'], 'Chamber')

    @mock.patch.object(BrewPiDevice, 'get_dashpanel_info', return_value=DASH_INFO)
    def test_device_detail(self, _):
        resp = self.client.get(reverse('ha_device_detail', kwargs={'device_id': self.device.id}), **self.auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['available'])
        self.assertEqual(data['mode'], 'beer_constant')
        self.assertEqual(data['beer_temp'], 19.5)
        self.assertEqual(data['fridge_humidity'], 61.0)
        self.assertEqual(data['beer_set'], 20.0)
        self.assertIsNone(data['fridge_set'])  # 0 = not yet read
        self.assertIsNone(data['room_temp'])
        self.assertEqual(data['controller_state'], 'cooling')

    @mock.patch.object(BrewPiDevice, 'get_dashpanel_info', return_value=None)
    def test_device_detail_unavailable(self, _):
        resp = self.client.get(reverse('ha_device_detail', kwargs={'device_id': self.device.id}), **self.auth)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['available'])
        self.assertIsNone(resp.json()['mode'])

    def test_device_not_found(self):
        resp = self.client.get(reverse('ha_device_detail', kwargs={'device_id': 9999}), **self.auth)
        self.assertEqual(resp.status_code, 404)

    def test_profile_list_only_assignable(self):
        FermentationProfile.objects.create(name='Lager')
        FermentationProfile.objects.create(name='Deleted', status=FermentationProfile.STATUS_PENDING_DELETE)
        resp = self.client.get(reverse('ha_profile_list'), **self.auth)
        self.assertEqual([p['name'] for p in resp.json()['profiles']], ['Lager'])

    @mock.patch.object(BrewPiDevice, 'get_dashpanel_info', return_value=DASH_INFO)
    def test_state_endpoint(self, _):
        FermentationProfile.objects.create(name='Lager')
        resp = self.client.get(reverse('ha_state'), **self.auth)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['devices']), 1)
        self.assertEqual(data['devices'][0]['beer_temp'], 19.5)
        self.assertEqual(data['devices'][0]['mode'], 'beer_constant')
        self.assertEqual([p['name'] for p in data['profiles']], ['Lager'])

    # --- Mode / setpoint ---

    @mock.patch.object(BrewPiDevice, 'set_temp_control', return_value=True)
    def test_set_beer_constant(self, set_temp_control):
        resp = self.post_json('ha_device_set_mode', {'mode': 'beer_constant', 'temperature': 18.5})
        self.assertEqual(resp.status_code, 200)
        set_temp_control.assert_called_once_with(method='beer_constant', set_temp=18.5)

    @mock.patch.object(BrewPiDevice, 'set_temp_control', return_value=True)
    def test_set_off(self, set_temp_control):
        resp = self.post_json('ha_device_set_mode', {'mode': 'off'})
        self.assertEqual(resp.status_code, 200)
        set_temp_control.assert_called_once_with(method='off', set_temp=None)

    @mock.patch.object(BrewPiDevice, 'set_temp_control')
    def test_set_mode_validation(self, set_temp_control):
        self.assertEqual(self.post_json('ha_device_set_mode', {'mode': 'fridge_constant'}).status_code, 400)
        self.assertEqual(self.post_json('ha_device_set_mode', {'mode': 'turbo'}).status_code, 400)
        self.assertEqual(self.post_json('ha_device_set_mode', {'mode': 'beer_profile'}).status_code, 400)
        resp = self.client.post(reverse('ha_device_set_mode', kwargs={'device_id': self.device.id}),
                                data='not json', content_type='application/json', **self.auth)
        self.assertEqual(resp.status_code, 400)
        set_temp_control.assert_not_called()

    # --- Profiles ---

    @mock.patch.object(BrewPiDevice, 'set_temp_control', return_value=True)
    def test_start_profile(self, set_temp_control):
        profile = FermentationProfile.objects.create(name='Ale')
        resp = self.post_json('ha_device_set_profile', {'profile_id': profile.id, 'start_at_hours': 12})
        self.assertEqual(resp.status_code, 200)
        _, kwargs = set_temp_control.call_args
        self.assertEqual(kwargs['method'], 'beer_profile')
        self.assertEqual(kwargs['profile'], profile.id)
        self.assertEqual(kwargs['profile_startat'].total_seconds(), 12 * 3600)

    def test_start_missing_profile(self):
        self.assertEqual(self.post_json('ha_device_set_profile', {'profile_id': 9999}).status_code, 404)

    # --- Beer / logging ---

    @mock.patch.object(BrewPiDevice, 'send_message', return_value=True)
    def test_start_beer_and_logging(self, _):
        resp = self.post_json('ha_device_start_beer', {'name': 'Test IPA'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['created'])
        self.device.refresh_from_db()
        self.assertEqual(self.device.active_beer.name, 'Test IPA')
        self.assertEqual(self.device.active_beer.format, 'C')
        self.assertEqual(self.device.logging_status, BrewPiDevice.DATA_LOGGING_ACTIVE)

        resp = self.post_json('ha_device_set_logging', {'status': 'paused'})
        self.assertEqual(resp.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.logging_status, BrewPiDevice.DATA_LOGGING_PAUSED)

        resp = self.post_json('ha_device_set_logging', {'status': 'stopped'})
        self.assertEqual(resp.status_code, 200)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.active_beer)

    def test_start_beer_invalid_name(self):
        self.assertEqual(self.post_json('ha_device_start_beer', {'name': '../etc/passwd'}).status_code, 400)
        self.assertEqual(Beer.objects.count(), 0)

    def test_resume_logging_without_beer(self):
        self.assertEqual(self.post_json('ha_device_set_logging', {'status': 'active'}).status_code, 400)


@override_config(USER_HAS_COMPLETED_CONFIGURATION=True)
class BeerCreateViewTests(TestCase):
    """Covers the web UI beer creation view, which shares Beer.create_and_start_on_device with the API"""

    @mock.patch.object(BrewPiDevice, 'send_message', return_value=True)
    def test_beer_create_view(self, _):
        from django.contrib.auth.models import User
        User.objects.create_user('brewer', password='pw')
        self.client.login(username='brewer', password='pw')
        device = BrewPiDevice.objects.create(device_name='Chamber', temp_format='C')
        resp = self.client.post(reverse('beer_create', kwargs={'device_id': device.id}),
                                {'beer_name': 'Stout', 'device': device.id})
        self.assertEqual(resp.status_code, 302)
        device.refresh_from_db()
        self.assertEqual(device.active_beer.name, 'Stout')
        self.assertEqual(device.active_beer.format, 'C')


class HaApiTokenCommandTests(TestCase):
    @override_config(HA_API_TOKEN='')
    def test_generate_regenerate_disable(self):
        from io import StringIO
        from constance import config
        from django.core.management import call_command

        call_command('ha_api_token', stdout=StringIO())
        first = config.HA_API_TOKEN
        self.assertGreaterEqual(len(first), 32)

        out = StringIO()
        call_command('ha_api_token', stdout=out)  # Shows the existing token without changing it
        self.assertEqual(out.getvalue().strip(), first)

        call_command('ha_api_token', '--regenerate', stdout=StringIO())
        self.assertNotEqual(config.HA_API_TOKEN, first)

        call_command('ha_api_token', '--disable', stdout=StringIO())
        self.assertEqual(config.HA_API_TOKEN, '')


class BrewPiSocketTests(TestCase):
    """send_message must time out, close its socket, and report failure rather than hang or raise"""

    def setUp(self):
        self.device = BrewPiDevice.objects.create(device_name='Chamber', temp_format='C')

    @mock.patch('app.models.socket.socket')
    def test_read_timeout_returns_none_and_closes(self, socket_cls):
        import socket as socket_module
        from app.models import BREWPI_SOCKET_TIMEOUT
        sock = socket_cls.return_value
        sock.recv.side_effect = socket_module.timeout
        self.assertIsNone(self.device.send_message('getDashInfo', read_response=True))
        sock.settimeout.assert_called_once_with(BREWPI_SOCKET_TIMEOUT)
        sock.close.assert_called()
        self.assertIsNone(self.device.get_dashpanel_info())

    @mock.patch('app.models.socket.socket')
    def test_connect_failure_returns_false(self, socket_cls):
        sock = socket_cls.return_value
        sock.connect.side_effect = ConnectionRefusedError
        self.assertFalse(self.device.send_message('setOff'))
        sock.sendall.assert_not_called()
        sock.close.assert_called()

    @mock.patch('app.models.socket.socket')
    def test_successful_round_trip_closes(self, socket_cls):
        sock = socket_cls.return_value
        sock.recv.return_value = json.dumps({'BeerTemp': 20}).encode('cp437')
        self.assertEqual(self.device.get_dashpanel_info(), {'BeerTemp': 20})
        sock.close.assert_called_once()

    @mock.patch('app.models.socket.socket')
    def test_empty_response_is_unavailable(self, socket_cls):
        socket_cls.return_value.recv.return_value = b''
        self.assertIsNone(self.device.get_dashpanel_info())

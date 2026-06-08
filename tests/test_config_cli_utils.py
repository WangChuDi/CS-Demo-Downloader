import bz2
import hashlib
import io
import json
import os
import struct
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import requests

from cs_demo_downloader import cli
from cs_demo_downloader.core.config import Config, ConfigLoadError, load_config
from cs_demo_downloader.core.downloader_pwa import (
    PwaSignerUnavailableError,
    build_download_headers,
    build_pwa_list_headers,
    call_pwa_et_decryptor_exe,
    get_all_demo_urls as get_pwa_demo_urls,
    get_demo_url,
    get_match_list_records,
    sign_demo_request,
)
from cs_demo_downloader.core.downloader_steam import decode_share_code, get_all_demo_urls, resolve_demo_url_from_share_code
from cs_demo_downloader.core.utils import download_and_extract, download_file, redact_url, unzip_file
from cs_demo_downloader.pwa_dll_updater import (
    LatestClientInfo,
    PvpAliveUpdateError,
    download_zip_member_by_range,
    fetch_latest_client_info,
    fetch_latest_zip_url,
    update_cached_pvp_alive_dll,
)
from cs_demo_downloader.pwa_bridge import (
    PvpAliveBridgeError,
    call_pvp_alive_swap_data,
    call_pvp_alive_swap_data_wine,
    get_pvp_alive_bridge_path,
)


class LoadConfigTests(unittest.TestCase):
    def test_explicit_missing_config_raises(self):
        missing_path = os.path.join(tempfile.gettempdir(), 'missing-config-for-test.json')

        with self.assertRaises(ConfigLoadError) as ctx:
            load_config(missing_path)

        self.assertIn("Config file not found", str(ctx.exception))
        self.assertIn(missing_path, str(ctx.exception))

    def test_explicit_malformed_config_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('{invalid json')

            with self.assertRaises(ConfigLoadError) as ctx:
                load_config(config_path)

        self.assertIn("Error loading config", str(ctx.exception))
        self.assertIn("config.json", str(ctx.exception))

    def test_default_missing_config_returns_empty_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = os.path.join(temp_dir, 'config.json')

            with mock.patch('cs_demo_downloader.core.config.get_config_path', return_value=missing_path):
                config = load_config()

        self.assertIsInstance(config, Config)
        self.assertEqual(config.download_path, '.')
        self.assertEqual(config.steam_resolver, {})
        self.assertEqual(config.steam_gc, {})
        self.assertEqual(config.users_5e, [])
        self.assertEqual(config.users_pwa, [])
        self.assertEqual(config.users_steam, [])

    def test_load_config_reads_steam_users(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('''{
  "download_path": "/tmp/demos",
  "users_steam": [
    {
      "name": "steam_user",
      "steamid": "76561198159976336",
      "api_key": "api-key",
      "steamidkey": "steamid-key",
      "knowncode": "CSGO-abcde-abcde-abcde-abcde-abcde"
    }
  ]
}''')

            config = load_config(config_path)

        users = config.get_users_steam()
        self.assertEqual(1, len(users))
        self.assertEqual('steam_user', users[0].name)
        self.assertEqual('api-key', users[0].api_key)

    def test_load_config_reads_jsonc_nested_schema_and_label(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('''{
  // Download into the current working directory.
  "download_path": ".",
  "five_e": {
    "users": [
      {"label": "five-e-label", "userid": "5e-user"}
    ]
  },
  "pwa": {
    "default_access_token": "shared-token",
    "users": [
      {"label": "pwa-one", "steamid": "steam-1"},
      {"label": "pwa-two", "steamid": "steam-2", "access_token": "override-token"}
    ]
  },
  "steam": {
    "users": [
      {
        "label": "steam-label",
        "steamid": "76561198159976336",
        "api_key": "api-key",
        "steamidkey": "steamid-key",
        "knowncode": "CSGO-abcde-abcde-abcde-abcde-abcde"
      }
    ],
    "resolver": {"type": "boiler"},
    "gc": {"timeout": "30"}
  }
}''')

            config = load_config(config_path)

        self.assertEqual('.', config.download_path)
        self.assertEqual('five-e-label', config.get_users_5e()[0].label)
        self.assertEqual('five-e-label', config.get_users_5e()[0].name)
        pwa_users = config.get_users_pwa()
        self.assertEqual('shared-token', pwa_users[0].access_token)
        self.assertEqual('override-token', pwa_users[1].access_token)
        self.assertEqual({'type': 'boiler'}, config.steam_resolver)
        self.assertEqual({'timeout': '30'}, config.steam_gc)

    def test_load_config_accepts_legacy_name_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.json')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('''{
  "users_5e": [{"name": "legacy", "userid": "5e-user"}]
}''')

            config = load_config(config_path)

        user = config.get_users_5e()[0]
        self.assertEqual('legacy', user.label)
        self.assertEqual('legacy', user.name)

    def test_load_config_reads_scheduler_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('''{
  "scheduler": {
    "enabled": true,
    "interval_seconds": 300,
    "run_on_start": true,
    "config": "/config/config.jsonc",
    "output": "/demos",
    "platforms": ["pwa", "steam"]
  }
}''')

            config = load_config(config_path)

        self.assertEqual(True, config.scheduler['enabled'])
        self.assertEqual(300, config.scheduler['interval_seconds'])
        self.assertEqual(True, config.scheduler['run_on_start'])
        self.assertEqual('/config/config.jsonc', config.scheduler['config'])
        self.assertEqual('/demos', config.scheduler['output'])
        self.assertEqual(['pwa', 'steam'], config.scheduler['platforms'])


class CliTests(unittest.TestCase):
    def test_cli_returns_non_zero_for_explicit_missing_config(self):
        missing_path = os.path.join(tempfile.gettempdir(), 'missing-cli-config-for-test.json')
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch('sys.argv', ['cli.py', 'download', '--config', missing_path]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.main()

        self.assertNotEqual(exit_code, 0)
        self.assertIn('Config file not found', stderr.getvalue())
        self.assertEqual('', stdout.getvalue())

    def test_scheduler_env_overrides_config(self):
        config = Config(
            scheduler={
                'enabled': False,
                'interval_seconds': 300,
                'run_on_start': False,
                'config': '/config/from-config.jsonc',
                'output': '/from-config',
                'platforms': ['5e'],
            }
        )

        with mock.patch.dict(os.environ, {
            'CS_DEMO_SCHEDULE_ENABLED': 'true',
            'CS_DEMO_SCHEDULE_INTERVAL_SECONDS': '45',
            'CS_DEMO_SCHEDULE_RUN_ON_START': 'yes',
            'CS_DEMO_SCHEDULE_CONFIG': '/config/from-env.jsonc',
            'CS_DEMO_SCHEDULE_OUTPUT': '/from-env',
            'CS_DEMO_SCHEDULE_PLATFORMS': 'pwa,steam',
        }, clear=True):
            settings = cli.resolve_scheduler_settings(base_config=config)

        self.assertTrue(settings.enabled)
        self.assertEqual(45, settings.interval_seconds)
        self.assertTrue(settings.run_on_start)
        self.assertEqual('/config/from-env.jsonc', settings.config_path)
        self.assertEqual('/from-env', settings.output_path)
        self.assertEqual(['pwa', 'steam'], settings.platforms)

    def test_scheduler_disabled_does_not_call_download_helper(self):
        stdout = io.StringIO()

        stop_event = mock.Mock()
        stop_event.wait.return_value = True

        with mock.patch('cs_demo_downloader.cli.threading.Event', return_value=stop_event):
            with mock.patch('cs_demo_downloader.cli.signal.signal'):
                with mock.patch('cs_demo_downloader.cli.run_download') as run_download:
                    with mock.patch.dict(os.environ, {}, clear=True):
                        with redirect_stdout(stdout):
                            exit_code = cli.run_schedule_command(stop_event=stop_event)

        self.assertEqual(0, exit_code)
        run_download.assert_not_called()
        self.assertIn('Scheduler disabled. Container is idle.', stdout.getvalue())
        stop_event.wait.assert_called_once_with()

    def test_scheduler_enabled_run_on_start_calls_download_helper_once(self):
        config = Config(download_path='.', scheduler={})
        stdout = io.StringIO()

        stop_event = mock.Mock()
        stop_event.wait.side_effect = [True]

        with mock.patch('cs_demo_downloader.cli.threading.Event', return_value=stop_event):
            with mock.patch('cs_demo_downloader.cli.signal.signal'):
                with mock.patch('cs_demo_downloader.cli.load_config', return_value=config) as load_config:
                    with mock.patch('cs_demo_downloader.cli.run_download', return_value=0) as run_download:
                        with mock.patch.dict(os.environ, {}, clear=True):
                            with redirect_stdout(stdout):
                                exit_code = cli.run_schedule_command(
                                    config_path='/config/config.jsonc',
                                    output_path='/demos',
                                    platforms='pwa,steam',
                                    enabled=True,
                                    interval_seconds=60,
                                    run_on_start=True,
                                    stop_event=stop_event,
                                )

        self.assertEqual(0, exit_code)
        self.assertEqual(2, load_config.call_count)
        run_download.assert_called_once_with(config, output_path='/demos', platforms=['pwa', 'steam'])
        self.assertIn('Running scheduled download immediately on startup.', stdout.getvalue())
        self.assertEqual([60], [call.args[0] for call in stop_event.wait.call_args_list])

    def test_scheduler_rejects_invalid_interval(self):
        stderr = io.StringIO()

        with mock.patch.dict(os.environ, {}, clear=True):
            with redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(enabled=True, interval_seconds=0, run_once=True)

        self.assertEqual(1, exit_code)
        self.assertIn('positive integer', stderr.getvalue())

    def test_scheduler_rejects_invalid_platforms(self):
        stderr = io.StringIO()

        with mock.patch.dict(os.environ, {}, clear=True):
            with redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(enabled=True, interval_seconds=60, platforms='pwa,invalid', run_once=True)

        self.assertEqual(1, exit_code)
        self.assertIn('Invalid scheduler platform', stderr.getvalue())


class DownloadFileTests(unittest.TestCase):
    def test_download_file_returns_none_on_open_error(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {'content-length': '4', 'Content-Type': 'application/octet-stream'}
        response.iter_content.return_value = [b'data']

        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, 'demo.zip')
            stdout = io.StringIO()

            with mock.patch('cs_demo_downloader.core.utils.requests.get', return_value=response):
                with mock.patch('builtins.open', side_effect=OSError('permission denied')):
                    with redirect_stdout(stdout):
                        result = download_file('https://example.invalid/demo.zip', local_path)

        self.assertIsNone(result)
        self.assertIn('File write error', stdout.getvalue())
        self.assertIn(local_path, stdout.getvalue())

    def test_download_file_redacts_sensitive_url_on_request_error(self):
        sensitive_url = 'https://example.invalid/demo.dem?access_token=secret-token&s=secret-signature&match_id=1'
        stdout = io.StringIO()

        with mock.patch('cs_demo_downloader.core.utils.requests.get', side_effect=requests.RequestException('boom')):
            with redirect_stdout(stdout):
                result = download_file(sensitive_url, '/tmp/demo.zip')

        self.assertIsNone(result)
        self.assertNotIn('secret-token', stdout.getvalue())
        self.assertNotIn('secret-signature', stdout.getvalue())
        self.assertIn('access_token=%3Credacted%3E', stdout.getvalue())

    def test_download_file_redacts_sensitive_url_on_json_response(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {'Content-Type': 'application/json'}
        response.raise_for_status.return_value = None
        sensitive_url = 'https://example.invalid/demo.dem?access_token=secret-token&match_id=1'
        stdout = io.StringIO()

        with mock.patch('cs_demo_downloader.core.utils.requests.get', return_value=response):
            with redirect_stdout(stdout):
                result = download_file(sensitive_url, '/tmp/demo.zip')

        self.assertIsNone(result)
        self.assertNotIn('secret-token', stdout.getvalue())
        self.assertIn('access_token=%3Credacted%3E', stdout.getvalue())


class RedactUrlTests(unittest.TestCase):
    def test_redact_url_hides_sensitive_query_values(self):
        url = redact_url('https://example.invalid/demo?access_token=secret&s=sig&match_id=123')

        self.assertNotIn('secret', url)
        self.assertNotIn('sig', url)
        self.assertIn('match_id=123', url)
        self.assertIn('access_token=%3Credacted%3E', url)


class UnzipFileTests(unittest.TestCase):
    def test_unzip_file_extracts_safe_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'safe.zip')
            extract_path = os.path.join(temp_dir, 'extract')
            expected_file = os.path.join(extract_path, 'nested', 'demo.dem')

            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                zip_file.writestr('nested/demo.dem', 'demo-content')

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = unzip_file(zip_path, extract_path)

            self.assertTrue(result)
            self.assertTrue(os.path.isfile(expected_file))
            with open(expected_file, 'r', encoding='utf-8') as extracted_file:
                self.assertEqual('demo-content', extracted_file.read())
            self.assertEqual('', stdout.getvalue())

    def test_unzip_file_rejects_zip_slip_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'malicious.zip')
            extract_path = os.path.join(temp_dir, 'extract')
            outside_file = os.path.join(temp_dir, 'escape.dem')

            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                zip_file.writestr('../escape.dem', 'malicious-content')

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = unzip_file(zip_path, extract_path)

            self.assertFalse(result)
            self.assertFalse(os.path.exists(outside_file))
            self.assertIn('Unsafe zip entry detected', stdout.getvalue())


class SteamDownloaderTests(unittest.TestCase):
    def test_decode_share_code_rejects_invalid_code(self):
        with self.assertRaises(ValueError):
            decode_share_code('not-a-share-code')

    def test_resolve_demo_url_requires_gc_resolver(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            url = resolve_demo_url_from_share_code('CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD')

        self.assertIsNone(url)
        self.assertIn('Steam GC match-info resolver is not configured', stdout.getvalue())

    def test_resolve_demo_url_uses_injected_gc_resolver(self):
        def resolver(share_code, decoded):
            self.assertEqual('CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD', share_code)
            self.assertIn('matchid', decoded)
            return 'http://replay129.valve.net/730/003676362600158855257_1677101043.dem.bz2'

        url = resolve_demo_url_from_share_code('CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD', resolver)

        self.assertEqual('http://replay129.valve.net/730/003676362600158855257_1677101043.dem.bz2', url)

    def test_get_all_demo_urls_iterates_share_codes_with_resolver(self):
        response_one = mock.MagicMock()
        response_one.status_code = 200
        response_one.json.return_value = {
            'result': {'nextcode': 'CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD'}
        }
        response_two = mock.MagicMock()
        response_two.status_code = 200
        response_two.json.return_value = {'result': {}}

        def resolver(share_code, decoded):
            return f"http://replay129.valve.net/730/{decoded['outcomeid']}_1677101043.dem.bz2"

        with mock.patch('cs_demo_downloader.core.downloader_steam.requests.get', side_effect=[response_one, response_two]) as get:
            demo_urls = get_all_demo_urls(
                'api-key', 'steamid', 'steamid-key', 'known-code', limit=2, demo_url_resolver=resolver
            )

        self.assertEqual(2, get.call_count)
        self.assertEqual(['CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD'], list(demo_urls.keys()))
        self.assertTrue(demo_urls['CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD'].endswith('.dem.bz2'))


class PwaDownloaderTests(unittest.TestCase):
    def test_sign_demo_request_delegates_to_compiled_signer(self):
        compiled_signer = SimpleNamespace(sign_demo_request=mock.Mock(return_value='compiled-signature'))
        with mock.patch('cs_demo_downloader.core.downloader_pwa._load_compiled_signer', return_value=compiled_signer):
            signature = sign_demo_request(
                '123456',
                '1710000000',
                'access_token=sample-token&cup_id=0&match_id=987654321',
            )

        self.assertEqual('compiled-signature', signature)
        compiled_signer.sign_demo_request.assert_called_once_with(
            '123456',
            '1710000000',
            'access_token=sample-token&cup_id=0&match_id=987654321',
        )

    def test_sign_demo_request_reports_missing_compiled_signer(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            empty_package = Path(temp_dir_name)
            with mock.patch('cs_demo_downloader.core.downloader_pwa.resources.files', return_value=empty_package):
                with mock.patch.dict('sys.modules', {'cs_demo_pwa_signer': None}):
                    with self.assertRaises(PwaSignerUnavailableError) as ctx:
                        sign_demo_request('123456', '1710000000', 'access_token=token')

        self.assertIn('cs-demo-pwa-signer', str(ctx.exception))

    def test_get_demo_url_includes_signed_query(self):
        with mock.patch('cs_demo_downloader.core.downloader_pwa.random.randint', return_value=123456):
            with mock.patch('cs_demo_downloader.core.downloader_pwa.time.time', return_value=1710000000):
                compiled_signer = SimpleNamespace(sign_demo_request=mock.Mock(return_value='compiled-signature'))
                with mock.patch('cs_demo_downloader.core.downloader_pwa._load_compiled_signer', return_value=compiled_signer):
                    demo_url = get_demo_url('987654321', 'sample-token')

        self.assertTrue(demo_url.startswith('https://pwaweblogin.wmpvp.com/csgo/demo/987654321_0.dem?'))
        self.assertIn('a=20000', demo_url)
        self.assertIn('r=123456', demo_url)
        self.assertIn('t=1710000000', demo_url)
        self.assertIn('access_token=sample-token&cup_id=0&match_id=987654321', demo_url)
        self.assertIn('s=compiled-signature', demo_url)

    def test_get_match_list_records_includes_signed_query(self):
        response = mock.MagicMock()
        response.status_code = 200
        response.json.return_value = {'data': [{'match': 'match-1'}]}

        with mock.patch('cs_demo_downloader.core.downloader_pwa.random.randint', return_value=123456):
            with mock.patch('cs_demo_downloader.core.downloader_pwa.time.time', return_value=1710000000):
                with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.get', return_value=response) as get:
                    records = get_match_list_records(
                        'steamid',
                        'sample-token',
                        size=10,
                        signer=lambda randnum, timestamp, data: f'signed:{randnum}:{timestamp}:{data}',
                    )

        self.assertEqual([{'match': 'match-1'}], records)
        params = get.call_args.kwargs['params']
        self.assertEqual('20000', params['a'])
        self.assertEqual('123456', params['r'])
        self.assertEqual('1710000000', params['t'])
        self.assertEqual('sample-token', params['access_token'])
        self.assertEqual('10', params['size'])
        self.assertEqual('steamid', params['uid'])
        self.assertEqual('signed:123456:1710000000:access_token=sample-token&size=10&uid=steamid', params['s'])
        headers = get.call_args.kwargs['headers']
        self.assertEqual('https://client.wmpvp.com/', headers['Referer'])
        self.assertEqual('none', headers['sec-fetch-site'])
        self.assertEqual('no-cors', headers['sec-fetch-mode'])
        self.assertIn('steam_cn_token=sample-token', headers['Cookie'])

    def test_get_match_list_records_can_query_explicit_season(self):
        response = mock.MagicMock()
        response.status_code = 200
        response.json.return_value = {'data': [{'match': 'match-s23'}]}

        with mock.patch('cs_demo_downloader.core.downloader_pwa.random.randint', return_value=123456):
            with mock.patch('cs_demo_downloader.core.downloader_pwa.time.time', return_value=1710000000):
                with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.get', return_value=response) as get:
                    records = get_match_list_records(
                        'steamid',
                        'sample-token',
                        size=10,
                        season='S23',
                        signer=lambda _randnum, _timestamp, data: f'signed:{data}',
                    )

        self.assertEqual([{'match': 'match-s23'}], records)
        params = get.call_args.kwargs['params']
        self.assertEqual('S23', params['season'])
        self.assertEqual('signed:access_token=sample-token&season=S23&size=10&uid=steamid', params['s'])

    def test_get_match_list_records_falls_back_to_decrypted_previous_season(self):
        empty_response = mock.MagicMock()
        empty_response.status_code = 200
        empty_response.json.return_value = {'data': []}
        current_season_response = mock.MagicMock()
        current_season_response.status_code = 200
        current_season_response.json.return_value = {'data': {'season': 'S24'}}
        season_list_response = mock.MagicMock()
        season_list_response.status_code = 200
        season_list_response.json.return_value = {
            'data': [
                {'season': 'S23', 'match_count': 72, 'score': 2005},
            ]
        }
        current_season_match_response = mock.MagicMock()
        current_season_match_response.status_code = 200
        current_season_match_response.json.return_value = {'data': []}
        current_encrypted_response = mock.MagicMock()
        current_encrypted_response.status_code = 200
        current_encrypted_response.json.return_value = {'data': {'e': 'encrypted-s24', 't': 'token-s24'}}
        previous_recent_response = mock.MagicMock()
        previous_recent_response.status_code = 200
        previous_recent_response.json.return_value = {'data': []}
        previous_encrypted_response = mock.MagicMock()
        previous_encrypted_response.status_code = 200
        previous_encrypted_response.json.return_value = {'data': {'e': 'encrypted-s23', 't': 'token-s23'}}

        def fake_decryptor(encrypted, token):
            if (encrypted, token) == ('encrypted-s23', 'token-s23'):
                return {'list': [{'match_id': 'match-s23'}]}
            return {'list': []}

        with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.get', side_effect=[empty_response, season_list_response, current_season_match_response, current_encrypted_response, previous_recent_response, previous_encrypted_response]) as get:
            with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.post', return_value=current_season_response):
                records = get_match_list_records(
                    'steamid',
                    'sample-token',
                    size=10,
                    signer=lambda _randnum, _timestamp, _data: 'signed',
                    max_seasons=2,
                    et_decryptor=fake_decryptor,
                )

        self.assertEqual([{'match_id': 'match-s23', 'match': 'match-s23', 'season': 'S23'}], records)
        requested_seasons = [call.kwargs['params'].get('season') for call in get.call_args_list if 'params' in call.kwargs]
        self.assertIn('S23', requested_seasons)

    def test_get_match_list_records_returns_empty_without_decryptor_for_encrypted_match_list(self):
        recent_response = mock.MagicMock()
        recent_response.status_code = 200
        recent_response.json.return_value = {'data': []}
        encrypted_response = mock.MagicMock()
        encrypted_response.status_code = 200
        encrypted_response.json.return_value = {'data': {'e': 'encrypted', 't': 'token'}}

        with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.get', side_effect=[recent_response, encrypted_response]):
            records = get_match_list_records(
                'steamid',
                'sample-token',
                size=10,
                season='S23',
                signer=lambda _randnum, _timestamp, _data: 'signed',
            )

        self.assertEqual([], records)

    def test_get_match_list_records_uses_compiled_wheel_decryptor_for_encrypted_match_list(self):
        recent_response = mock.MagicMock()
        recent_response.status_code = 200
        recent_response.json.return_value = {'data': []}
        encrypted_response = mock.MagicMock()
        encrypted_response.status_code = 200
        encrypted_response.json.return_value = {'data': {'e': 'encrypted', 't': 'token'}}
        compiled_signer = SimpleNamespace(decrypt_pwa_response=mock.Mock(return_value='[{"match_id":"match-s23"}]'))

        with mock.patch('cs_demo_downloader.core.downloader_pwa.requests.get', side_effect=[recent_response, encrypted_response]):
            with mock.patch('cs_demo_downloader.core.downloader_pwa._load_compiled_signer', return_value=compiled_signer):
                records = get_match_list_records(
                    'steamid',
                    'sample-token',
                    size=10,
                    season='S23',
                    signer=lambda _randnum, _timestamp, _data: 'signed',
                )

        self.assertEqual([{'match_id': 'match-s23', 'match': 'match-s23'}], records)
        compiled_signer.decrypt_pwa_response.assert_called_once_with('encrypted', 'token')

    def test_call_pwa_et_decryptor_exe_sends_encrypted_payload_on_stdin(self):
        completed = SimpleNamespace(returncode=0, stdout='[{"match_id":"m1"}]\n', stderr='')

        with mock.patch('cs_demo_downloader.core.downloader_pwa.subprocess.run', return_value=completed) as run:
            plaintext = call_pwa_et_decryptor_exe('ciphertext', 'nonce-token', '/private/pwa-decryptor.exe', timeout=7)

        self.assertEqual('[{"match_id":"m1"}]', plaintext)
        self.assertEqual(('/private/pwa-decryptor.exe',), run.call_args.args[0])
        self.assertEqual('{"e":"ciphertext","t":"nonce-token"}', run.call_args.kwargs['input'])
        self.assertEqual(7, run.call_args.kwargs['timeout'])

    def test_build_pwa_list_headers_can_include_acw_tc_cookie(self):
        headers = build_pwa_list_headers('steamid', 'token', acw_tc='edge-cookie')

        self.assertEqual('steamid', headers['pwasteamid'])
        self.assertEqual('steamid', headers['x-pwa-steamid'])
        self.assertEqual('https://client.wmpvp.com/', headers['Referer'])
        self.assertIn('steam_cn_token=token', headers['Cookie'])
        self.assertIn('acw_tc=edge-cookie', headers['Cookie'])

    def test_build_download_headers_includes_pwa_signature(self):
        compiled_signer = SimpleNamespace(build_x_pwa_signature=mock.Mock(return_value='1710000000-compiled'))
        with mock.patch('cs_demo_downloader.core.downloader_pwa._load_compiled_signer', return_value=compiled_signer):
            headers = build_download_headers(
                '76561198159976336',
                public_ip='203.0.113.7',
                timestamp=1710000000,
            )

        self.assertEqual('76561198159976336', headers['X-PWA-SteamId'])
        self.assertEqual('76561198159976336', headers['PwaSteamId'])
        self.assertEqual('1710000000-compiled', headers['X-PWA-Signature'])
        self.assertIn('perfectworldarena/1.0.26051411', headers['User-Agent'])

    def test_cli_downloads_pwa_with_signed_headers(self):
        config = Config(download_path='/tmp/demos')
        config.add_user_pwa('pwa-user', '76561198159976336', 'token')
        stdout = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.get_pwa_demos', return_value={'match-1': 'https://pwaweblogin.wmpvp.com/csgo/demo/match-1_0.dem?access_token=secret-token&a=20000'}):
            with mock.patch('cs_demo_downloader.cli.build_pwa_download_headers', return_value={'X-PWA-Signature': 'signed'}) as build_headers:
                with mock.patch('cs_demo_downloader.cli.download_and_extract') as download:
                    with redirect_stdout(stdout):
                        cli.download_pwa_demos(config)

        build_headers.assert_called_once_with('76561198159976336')
        download.assert_called_once_with(
            'https://pwaweblogin.wmpvp.com/csgo/demo/match-1_0.dem?access_token=secret-token&a=20000',
            '/tmp/demos',
            cli.print_progress,
            headers={'X-PWA-Signature': 'signed'},
        )
        self.assertNotIn('secret-token', stdout.getvalue())
        self.assertIn('access_token=%3Credacted%3E', stdout.getvalue())


class PvpAliveDllUpdaterTests(unittest.TestCase):
    def test_fetch_latest_zip_url_uses_path_and_replaces_exe_suffix(self):
        response = mock.MagicMock()
        response.text = '''version: 1.0.0
files:
  - url: fallback.exe
path: perfectworldarena_win32_v1.0.0.exe
'''
        response.raise_for_status.return_value = None

        with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.get', return_value=response):
            zip_url = fetch_latest_zip_url('https://client.wmpvp.com/download/latest.yml', timeout=5)

        self.assertEqual('https://client.wmpvp.com/download/perfectworldarena_win32_v1.0.0.zip', zip_url)

    def test_fetch_latest_client_info_keeps_version_and_installer_path(self):
        response = mock.MagicMock()
        response.text = '''version: 1.0.0
path: perfectworldarena_win32_v1.0.0.exe
'''
        response.raise_for_status.return_value = None

        with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.get', return_value=response):
            info = fetch_latest_client_info('https://client.wmpvp.com/download/latest.yml', timeout=5)

        self.assertEqual('1.0.0', info.version)
        self.assertEqual('perfectworldarena_win32_v1.0.0.exe', info.installer_path)
        self.assertEqual('https://client.wmpvp.com/download/perfectworldarena_win32_v1.0.0.zip', info.zip_url)

    def test_fetch_latest_zip_url_rejects_non_exe(self):
        response = mock.MagicMock()
        response.text = 'path: client.zip\n'
        response.raise_for_status.return_value = None

        with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.get', return_value=response):
            with self.assertRaises(PvpAliveUpdateError) as ctx:
                fetch_latest_zip_url('https://client.wmpvp.com/download/latest.yml')

        self.assertIn('not an .exe', str(ctx.exception))

    def test_download_zip_member_by_range_extracts_target_without_full_zip(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('padding.bin', b'x' * 70000, compress_type=zipfile.ZIP_STORED)
            zip_file.writestr('plugin/Other.dll', b'other')
            zip_file.writestr('plugin/PvpAlive.dll', b'pvp-dll-bytes')
        zip_bytes = zip_buffer.getvalue()
        requested_ranges = []

        head_response = mock.MagicMock()
        head_response.headers = {'Content-Length': str(len(zip_bytes)), 'Accept-Ranges': 'bytes'}
        head_response.raise_for_status.return_value = None

        def fake_get(_url, headers=None, timeout=None):
            request_headers = headers or {}
            range_header = request_headers['Range']
            requested_ranges.append(range_header)
            start_text, end_text = range_header.removeprefix('bytes=').split('-', 1)
            start = int(start_text)
            end = int(end_text)
            response = mock.MagicMock()
            response.status_code = 206
            response.content = zip_bytes[start:end + 1]
            return response

        with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.head', return_value=head_response):
            with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.get', side_effect=fake_get):
                data = download_zip_member_by_range('https://example.invalid/client.zip', timeout=5)

        self.assertEqual(b'pvp-dll-bytes', data)
        self.assertGreaterEqual(len(requested_ranges), 4)
        self.assertNotIn(f'bytes=0-{len(zip_bytes) - 1}', requested_ranges)

    def test_download_zip_member_by_range_reports_missing_target_choices(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('plugin/Other.dll', b'other')
        zip_bytes = zip_buffer.getvalue()

        head_response = mock.MagicMock()
        head_response.headers = {'Content-Length': str(len(zip_bytes))}
        head_response.raise_for_status.return_value = None

        def fake_get(_url, headers=None, timeout=None):
            request_headers = headers or {}
            start_text, end_text = request_headers['Range'].removeprefix('bytes=').split('-', 1)
            response = mock.MagicMock()
            response.status_code = 206
            response.content = zip_bytes[int(start_text):int(end_text) + 1]
            return response

        with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.head', return_value=head_response):
            with mock.patch('cs_demo_downloader.pwa_dll_updater.requests.get', side_effect=fake_get):
                with self.assertRaises(PvpAliveUpdateError) as ctx:
                    download_zip_member_by_range('https://example.invalid/client.zip')

        self.assertIn('plugin/Other.dll', str(ctx.exception))

    def test_update_cached_pvp_alive_dll_writes_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, 'cache', 'PvpAlive.dll')
            info = LatestClientInfo(
                latest_yml_url='https://example.invalid/latest.yml',
                version='1.0.0',
                installer_path='client.exe',
                zip_url='https://example.invalid/client.zip',
            )
            with mock.patch('cs_demo_downloader.pwa_dll_updater.fetch_latest_client_info', return_value=info):
                with mock.patch('cs_demo_downloader.pwa_dll_updater.download_zip_member_by_range', return_value=b'dll'):
                    result = update_cached_pvp_alive_dll(target_path=target_path)

            self.assertEqual(target_path, result)
            with open(target_path, 'rb') as dll_file:
                self.assertEqual(b'dll', dll_file.read())
            with open(target_path + '.json', 'r', encoding='utf-8') as metadata_file:
                metadata = json.load(metadata_file)
            self.assertEqual('1.0.0', metadata['version'])
            self.assertEqual('client.exe', metadata['installer_path'])

    def test_update_cached_pvp_alive_dll_skips_when_metadata_is_current(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, 'cache', 'PvpAlive.dll')
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'wb') as dll_file:
                dll_file.write(b'existing')
            metadata = {
                'latest_yml_url': 'https://example.invalid/latest.yml',
                'version': '1.0.0',
                'installer_path': 'client.exe',
                'zip_url': 'https://example.invalid/client.zip',
            }
            with open(target_path + '.json', 'w', encoding='utf-8') as metadata_file:
                json.dump(metadata, metadata_file)
            info = LatestClientInfo(**metadata)

            with mock.patch('cs_demo_downloader.pwa_dll_updater.fetch_latest_client_info', return_value=info):
                with mock.patch('cs_demo_downloader.pwa_dll_updater.download_zip_member_by_range') as download:
                    result = update_cached_pvp_alive_dll(target_path=target_path)

            self.assertEqual(target_path, result)
            download.assert_not_called()
            with open(target_path, 'rb') as dll_file:
                self.assertEqual(b'existing', dll_file.read())

    def test_update_cached_pvp_alive_dll_force_ignores_current_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, 'cache', 'PvpAlive.dll')
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'wb') as dll_file:
                dll_file.write(b'existing')
            metadata = {
                'latest_yml_url': 'https://example.invalid/latest.yml',
                'version': '1.0.0',
                'installer_path': 'client.exe',
                'zip_url': 'https://example.invalid/client.zip',
            }
            with open(target_path + '.json', 'w', encoding='utf-8') as metadata_file:
                json.dump(metadata, metadata_file)
            info = LatestClientInfo(**metadata)

            with mock.patch('cs_demo_downloader.pwa_dll_updater.fetch_latest_client_info', return_value=info):
                with mock.patch('cs_demo_downloader.pwa_dll_updater.download_zip_member_by_range', return_value=b'new') as download:
                    result = update_cached_pvp_alive_dll(target_path=target_path, force=True)

            self.assertEqual(target_path, result)
            download.assert_called_once_with('https://example.invalid/client.zip', 'plugin/PvpAlive.dll', 30)
            with open(target_path, 'rb') as dll_file:
                self.assertEqual(b'new', dll_file.read())


class PvpAliveBridgeTests(unittest.TestCase):
    def test_get_pvp_alive_bridge_path_points_to_packaged_exe(self):
        bridge_path = get_pvp_alive_bridge_path()

        self.assertTrue(bridge_path.endswith(os.path.join('bin', 'pvp_alive_bridge.exe')))
        self.assertTrue(os.path.isfile(bridge_path))

    def test_bridge_rejects_non_windows_platform(self):
        with mock.patch('cs_demo_downloader.pwa_bridge.platform.system', return_value='Linux'):
            with self.assertRaises(PvpAliveBridgeError) as ctx:
                call_pvp_alive_swap_data('/tmp/PvpAlive.dll', '{}')

        self.assertIn('allow_wine=True', str(ctx.exception))

    def test_bridge_invokes_packaged_exe_on_windows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dll_path = os.path.join(temp_dir, 'PvpAlive.dll')
            bridge_path = os.path.join(temp_dir, 'pvp_alive_bridge.exe')
            with open(dll_path, 'wb') as dll_file:
                dll_file.write(b'dll')
            with open(bridge_path, 'wb') as bridge_file:
                bridge_file.write(b'exe')

            completed = SimpleNamespace(returncode=0, stdout='signature\n', stderr='')
            with mock.patch('cs_demo_downloader.pwa_bridge.platform.system', return_value='Windows'):
                with mock.patch('cs_demo_downloader.pwa_bridge.subprocess.run', return_value=completed) as run:
                    signature = call_pvp_alive_swap_data(dll_path, '{"a":1}', bridge_path=bridge_path, timeout=7)

        self.assertEqual('signature', signature)
        command = run.call_args.args[0]
        self.assertEqual((bridge_path, dll_path, '{"a":1}'), command)
        self.assertEqual(7, run.call_args.kwargs['timeout'])

    def test_bridge_invokes_wine_on_linux_when_explicitly_allowed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dll_path = os.path.join(temp_dir, 'PvpAlive.dll')
            bridge_path = os.path.join(temp_dir, 'pvp_alive_bridge.exe')
            with open(dll_path, 'wb') as dll_file:
                dll_file.write(b'dll')
            with open(bridge_path, 'wb') as bridge_file:
                bridge_file.write(b'exe')

            completed = SimpleNamespace(returncode=0, stdout='wine-signature\n', stderr='')
            with mock.patch('cs_demo_downloader.pwa_bridge.platform.system', return_value='Linux'):
                with mock.patch('cs_demo_downloader.pwa_bridge.shutil.which', return_value='/usr/bin/wine'):
                    with mock.patch('cs_demo_downloader.pwa_bridge.subprocess.run', return_value=completed) as run:
                        signature = call_pvp_alive_swap_data_wine(
                            dll_path,
                            '{"a":1}',
                            bridge_path=bridge_path,
                            timeout=9,
                        )

        self.assertEqual('wine-signature', signature)
        command = run.call_args.args[0]
        self.assertEqual(('/usr/bin/wine', bridge_path, dll_path, '{"a":1}'), command)
        self.assertEqual(9, run.call_args.kwargs['timeout'])
        self.assertEqual('-all', run.call_args.kwargs['env']['WINEDEBUG'])

    def test_bridge_reports_missing_wine_binary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dll_path = os.path.join(temp_dir, 'PvpAlive.dll')
            bridge_path = os.path.join(temp_dir, 'pvp_alive_bridge.exe')
            with open(dll_path, 'wb') as dll_file:
                dll_file.write(b'dll')
            with open(bridge_path, 'wb') as bridge_file:
                bridge_file.write(b'exe')

            with mock.patch('cs_demo_downloader.pwa_bridge.platform.system', return_value='Linux'):
                with mock.patch('cs_demo_downloader.pwa_bridge.shutil.which', return_value=None):
                    with self.assertRaises(PvpAliveBridgeError) as ctx:
                        call_pvp_alive_swap_data_wine(dll_path, '{}', bridge_path=bridge_path)

        self.assertIn('Wine binary not found', str(ctx.exception))


class PwaSignerSelectionTests(unittest.TestCase):
    def test_get_demo_url_uses_custom_signer_when_provided(self):
        def signer(randnum, timestamp, data):
            self.assertTrue(randnum.isdigit())
            self.assertTrue(timestamp.isdigit())
            self.assertEqual('access_token=token&cup_id=0&match_id=match-1', data)
            return 'custom-signature'

        url = get_demo_url('match-1', 'token', signer=signer)

        self.assertIn('s=custom-signature', url)

    def test_get_all_demo_urls_passes_custom_signer(self):
        with mock.patch('cs_demo_downloader.core.downloader_pwa.get_match_list', return_value=['m1']):
            result = get_pwa_demo_urls('steamid', 'token', signer=lambda _r, _t, _d: 'sig')

        self.assertTrue(result['m1'].startswith('https://pwaweblogin.wmpvp.com/csgo/demo/m1_0.dem?a=20000&r='))
        self.assertIn('s=sig', result['m1'])

    def test_build_pwa_demo_url_signer_defaults_to_compiled(self):
        config = Config(pwa={'signature_provider': 'compiled'})

        self.assertIsNone(cli.build_pwa_demo_url_signer(config))

    def test_build_pwa_demo_url_signer_invokes_native_bridge(self):
        config = Config(pwa={
            'signature_provider': 'pvp_alive_native',
            'pvp_alive_dll': '/cache/PvpAlive.dll',
            'pvp_alive_bridge_exe': '/app/pvp_alive_bridge.exe',
            'pvp_alive_timeout': '12',
        })

        with mock.patch('cs_demo_downloader.pwa_bridge.call_pvp_alive_swap_data', return_value='native-signature') as call:
            signer = cli.build_pwa_demo_url_signer(config)
            if signer is None:
                self.fail('expected native signer')
            signature = signer('123456', '1700000000', 'access_token=token&cup_id=0&match_id=m1')

        self.assertEqual('native-signature', signature)
        self.assertEqual('/cache/PvpAlive.dll', call.call_args.kwargs['dll_path'])
        self.assertEqual('/app/pvp_alive_bridge.exe', call.call_args.kwargs['bridge_path'])
        self.assertEqual(12, call.call_args.kwargs['timeout'])

    def test_build_pwa_demo_url_signer_invokes_wine_bridge(self):
        config = Config(pwa={
            'signature_provider': 'pvp_alive_wine',
            'pvp_alive_dll': '/cache/PvpAlive.dll',
            'pvp_alive_wine_executable': '/usr/bin/wine',
        })

        with mock.patch('cs_demo_downloader.pwa_bridge.call_pvp_alive_swap_data_wine', return_value='wine-signature') as call:
            signer = cli.build_pwa_demo_url_signer(config)
            if signer is None:
                self.fail('expected wine signer')
            signature = signer('123456', '1700000000', 'access_token=token&cup_id=0&match_id=m1')

        self.assertEqual('wine-signature', signature)
        self.assertEqual('/usr/bin/wine', call.call_args.kwargs['wine_binary'])

    def test_build_pwa_demo_url_signer_rejects_unknown_provider(self):
        config = Config(pwa={'signature_provider': 'bad-provider'})

        with self.assertRaises(RuntimeError) as ctx:
            cli.build_pwa_demo_url_signer(config)

        self.assertIn('Unsupported PWA signature_provider', str(ctx.exception))

    def test_build_pwa_et_decryptor_invokes_private_exe_boundary(self):
        config = Config(pwa={
            'pwa_response_decryptor_exe': '/private/pwa-decryptor.exe',
            'pwa_response_decryptor_timeout': '15',
        })

        with mock.patch('cs_demo_downloader.cli.call_pwa_et_decryptor_exe', return_value='[]') as call:
            decryptor = cli.build_pwa_et_decryptor(config)
            if decryptor is None:
                self.fail('expected PWA e/t decryptor')
            plaintext = decryptor('ciphertext', 'nonce-token')

        self.assertEqual('[]', plaintext)
        self.assertEqual('/private/pwa-decryptor.exe', call.call_args.kwargs['executable_path'])
        self.assertEqual(15, call.call_args.kwargs['timeout'])


class Bz2DownloadTests(unittest.TestCase):
    def test_download_and_extract_handles_dem_bz2(self):
        compressed = bz2.compress(b'demo-data')

        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {
            'content-length': str(len(compressed)),
            'Content-Type': 'application/octet-stream',
        }
        response.iter_content.return_value = [compressed]

        with tempfile.TemporaryDirectory() as temp_dir:
            url = 'http://replay.valve.net/730/1_2_3.dem.bz2'
            with mock.patch('cs_demo_downloader.core.utils.requests.get', return_value=response):
                result = download_and_extract(url, temp_dir)

            dem_path = os.path.join(temp_dir, '1_2_3.dem')
            self.assertTrue(result)
            self.assertTrue(os.path.exists(dem_path))
            with open(dem_path, 'rb') as demo_file:
                self.assertEqual(b'demo-data', demo_file.read())


class BoilerResolverTests(unittest.TestCase):
    def test_boiler_resolver_invokes_executable_and_parser(self):
        from cs_demo_downloader.steam.boiler_resolver import BoilerWritterResolver

        parsed_paths = []

        def parser(path):
            parsed_paths.append(path)
            self.assertTrue(os.path.exists(path))
            return 'http://replay129.valve.net/730/003676362600158855257_1677101043.dem.bz2'

        resolver = BoilerWritterResolver(
            executable_path='boiler-writter',
            timeout=12,
            match_list_parser=parser,
        )

        with mock.patch('cs_demo_downloader.steam.boiler_resolver.subprocess.run') as run:
            url = resolver.resolve_demo_url(
                'CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD',
                {'matchid': 1, 'outcomeid': 2, 'token': 3},
            )

        self.assertEqual('http://replay129.valve.net/730/003676362600158855257_1677101043.dem.bz2', url)
        self.assertEqual(1, run.call_count)
        command = run.call_args.args[0]
        self.assertEqual('boiler-writter', command[0])
        self.assertEqual(['1', '2', '3'], command[-3:])
        self.assertEqual(1, len(parsed_paths))

    def test_boiler_extracts_demo_url_from_match_list(self):
        from cs_demo_downloader.steam.boiler_resolver import extract_demo_url_from_match_list

        message = SimpleNamespace(matches=[
            SimpleNamespace(roundstatsall=[
                SimpleNamespace(map=''),
                SimpleNamespace(map='http://replay129.valve.net/730/from-boiler.dem.bz2'),
            ])
        ])

        self.assertEqual('http://replay129.valve.net/730/from-boiler.dem.bz2', extract_demo_url_from_match_list(message))

    def test_boiler_default_parser_reports_not_configured(self):
        from cs_demo_downloader.steam.boiler_resolver import BoilerResolverError, extract_demo_url_from_match_list_file

        with self.assertRaises(BoilerResolverError) as ctx:
            extract_demo_url_from_match_list_file('/tmp/match-list.pb')

        self.assertIn('optional dependencies', str(ctx.exception))

    def test_boiler_platform_asset_names(self):
        from cs_demo_downloader.steam.boiler_resolver import get_boiler_platform_asset_name

        self.assertEqual('boiler-writter-linux-1.7.0.zip', get_boiler_platform_asset_name('v1.7.0', 'Linux', 'x86_64'))
        self.assertEqual('boiler-writter-mac-arm64-1.7.0.zip', get_boiler_platform_asset_name('v1.7.0', 'Darwin', 'arm64'))
        self.assertEqual('boiler-writter-win-1.7.0.zip', get_boiler_platform_asset_name('v1.7.0', 'Windows', 'AMD64'))

    def test_boiler_sha256_verification(self):
        from cs_demo_downloader.steam.boiler_resolver import verify_sha256

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b'archive')
            temp_path = temp_file.name

        try:
            digest = hashlib.sha256(b'archive').hexdigest()
            verify_sha256(Path(temp_path), f'sha256:{digest}')
        finally:
            os.remove(temp_path)

    def test_boiler_resolver_auto_downloads_binary(self):
        from cs_demo_downloader.steam.boiler_resolver import BoilerWritterResolver

        resolver = BoilerWritterResolver(
            auto_download=True,
            match_list_parser=lambda path: 'http://replay129.valve.net/730/demo.dem.bz2',
        )

        with mock.patch('cs_demo_downloader.steam.boiler_resolver.download_boiler_writter', return_value='/tmp/boiler-writter') as download:
            with mock.patch('cs_demo_downloader.steam.boiler_resolver.subprocess.run') as run:
                url = resolver.resolve_demo_url(
                    'CSGO-3VocL-obGr4-SjkBU-DjHhz-KWtrD',
                    {'matchid': 1, 'outcomeid': 2, 'token': 3},
                )

        self.assertEqual('http://replay129.valve.net/730/demo.dem.bz2', url)
        download.assert_called_once()
        self.assertEqual('/tmp/boiler-writter', run.call_args.args[0][0])


class SteamLoginResolverTests(unittest.TestCase):
    def test_login_resolver_requires_env_credentials(self):
        from cs_demo_downloader.steam.login_resolver import SteamLoginResolver, SteamLoginResolverError

        resolver = SteamLoginResolver(username_env='MISSING_STEAM_USER', password_env='MISSING_STEAM_PASS')

        with self.assertRaises(SteamLoginResolverError) as ctx:
            resolver.resolve_demo_url('share-code', {'matchid': 1, 'outcomeid': 2, 'token': 3})

        self.assertIn('MISSING_STEAM_USER', str(ctx.exception))

    def test_login_resolver_extracts_demo_url_from_match_list(self):
        from cs_demo_downloader.steam.login_resolver import extract_demo_url_from_match_list

        message = SimpleNamespace(matches=[
            SimpleNamespace(roundstatsall=[
                SimpleNamespace(map=''),
                SimpleNamespace(map='http://replay129.valve.net/730/demo.dem.bz2'),
            ])
        ])

        self.assertEqual('http://replay129.valve.net/730/demo.dem.bz2', extract_demo_url_from_match_list(message))

    def test_login_resolver_reports_missing_optional_dependencies(self):
        from cs_demo_downloader.steam.login_resolver import SteamLoginResolver, SteamLoginResolverError

        resolver = SteamLoginResolver(username_env='TEST_STEAM_USER', password_env='TEST_STEAM_PASS')

        env = {'TEST_STEAM_USER': 'user', 'TEST_STEAM_PASS': 'pass'}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.dict('sys.modules', {'steam.client': None, 'csgo.client': None}):
                with self.assertRaises(SteamLoginResolverError) as ctx:
                    resolver.resolve_demo_url('share-code', {'matchid': 1, 'outcomeid': 2, 'token': 3})

        self.assertIn('optional dependencies', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

import bz2
import hashlib
import io
import os
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
from cs_demo_downloader.core.downloader_pwa import build_download_headers, get_demo_url, sign_demo_request
from cs_demo_downloader.core.downloader_steam import decode_share_code, get_all_demo_urls, resolve_demo_url_from_share_code
from cs_demo_downloader.core.utils import download_and_extract, download_file, redact_url, unzip_file


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
        self.assertEqual(config.download_path, '')
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
    def test_sign_demo_request_matches_known_formula(self):
        signature = sign_demo_request(
            '123456',
            '1710000000',
            'access_token=sample-token&cup_id=0&match_id=987654321',
        )

        self.assertEqual('compiled-signature', signature)

    def test_get_demo_url_includes_signed_query(self):
        with mock.patch('cs_demo_downloader.core.downloader_pwa.random.randint', return_value=123456):
            with mock.patch('cs_demo_downloader.core.downloader_pwa.time.time', return_value=1710000000):
                demo_url = get_demo_url('987654321', 'sample-token')

        self.assertTrue(demo_url.startswith('https://pwaweblogin.wmpvp.com/csgo/demo/987654321_0.dem?'))
        self.assertIn('a=20000', demo_url)
        self.assertIn('r=123456', demo_url)
        self.assertIn('t=1710000000', demo_url)
        self.assertIn('access_token=sample-token&cup_id=0&match_id=987654321', demo_url)
        self.assertIn('s=compiled-signature', demo_url)

    def test_build_download_headers_includes_pwa_signature(self):
        headers = build_download_headers(
            '76561198159976336',
            public_ip='203.0.113.7',
            timestamp=1710000000,
        )

        self.assertEqual('76561198159976336', headers['X-PWA-SteamId'])
        self.assertEqual('76561198159976336', headers['PwaSteamId'])
        self.assertTrue(headers['X-PWA-Signature'].startswith('1710000000-'))
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

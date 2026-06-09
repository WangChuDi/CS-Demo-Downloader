import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from cs_demo_downloader import cli
from cs_demo_downloader.core.config import Config, default_docker_config_data, load_config


class SchedulerConfigTests(unittest.TestCase):
    def test_load_config_reads_scheduler_section(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('{\n  "scheduler": {\n    "enabled": "true",\n    "interval_seconds": "3600",\n    "daily_time": "8:00",\n    "run_on_start": "false",\n    "platforms": "pwa",\n    "output": "/demos"\n  }\n}')

            config = load_config(config_path)

        self.assertEqual('true', config.scheduler['enabled'])
        self.assertEqual('3600', config.scheduler['interval_seconds'])
        self.assertEqual('8:00', config.scheduler['daily_time'])
        self.assertEqual('pwa', config.scheduler['platforms'])
        self.assertEqual('/demos', config.scheduler['output'])

    def test_env_overrides_scheduler_config(self):
        config = Config(scheduler={
            'enabled': 'false',
            'interval_seconds': '3600',
            'run_on_start': 'false',
            'platforms': '5e',
            'output': '/from-config',
        })
        env = {
            'CS_DEMO_SCHEDULE_ENABLED': 'true',
            'CS_DEMO_SCHEDULE_INTERVAL_SECONDS': '60',
            'CS_DEMO_SCHEDULE_DAILY_TIME': '8:05',
            'CS_DEMO_SCHEDULE_RUN_ON_START': 'true',
            'CS_DEMO_SCHEDULE_PLATFORMS': 'steam',
            'CS_DEMO_SCHEDULE_OUTPUT': '/from-env',
        }

        settings = cli.resolve_scheduler_settings(env=env, base_config=config)

        self.assertTrue(settings.enabled)
        self.assertEqual(60, settings.interval_seconds)
        self.assertEqual('08:05', settings.daily_time)
        self.assertTrue(settings.run_on_start)
        self.assertEqual('steam', settings.platforms)
        self.assertEqual('/from-env', settings.output_path)

    def test_scheduler_platform_singular_aliases(self):
        config = Config(scheduler={
            'enabled': 'true',
            'platform': 'steam',
        })

        settings = cli.resolve_scheduler_settings(env={}, base_config=config)

        self.assertEqual('steam', settings.platforms)

        settings = cli.resolve_scheduler_settings(
            env={
                'CS_DEMO_SCHEDULE_ENABLED': 'true',
                'CS_DEMO_SCHEDULE_PLATFORM': 'pwa',
            },
            base_config=Config(scheduler={'platforms': '5e'}),
        )

        self.assertEqual('pwa', settings.platforms)

    def test_daily_time_from_config_takes_precedence_for_wait(self):
        config = Config(scheduler={
            'enabled': 'true',
            'interval_seconds': '3600',
            'daily_time': '8:00',
        })

        settings = cli.resolve_scheduler_settings(env={}, base_config=config)

        daily_time = settings.daily_time
        self.assertEqual('08:00', daily_time)
        if daily_time is None:
            self.fail('daily_time should be resolved from config')
        now = cli.datetime.datetime(2026, 6, 9, 7, 30, tzinfo=cli.datetime.timezone.utc)
        self.assertEqual(1800, cli._seconds_until_daily_time(daily_time, now=now))
        self.assertEqual('daily at 08:00', cli._schedule_description(settings))

    def test_daily_time_rolls_to_next_day(self):
        now = cli.datetime.datetime(2026, 6, 9, 8, 0, tzinfo=cli.datetime.timezone.utc)

        self.assertEqual(86400, cli._seconds_until_daily_time('08:00', now=now))

    def test_invalid_daily_time_fails_clearly(self):
        with self.assertRaises(cli.SchedulerConfigError) as ctx:
            cli.resolve_scheduler_settings(
                env={'CS_DEMO_SCHEDULE_DAILY_TIME': '25:00'},
                base_config=Config(scheduler={'enabled': 'true'}),
            )

        self.assertIn('between 00:00 and 23:59', str(ctx.exception))

class SchedulerCommandTests(unittest.TestCase):
    def test_disabled_scheduler_does_not_load_missing_config_or_download(self):
        missing_path = os.path.join(tempfile.gettempdir(), 'missing-scheduler-config.jsonc')
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.run_download_command') as run_download:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(
                    config_path=missing_path,
                    env={'CS_DEMO_SCHEDULE_ENABLED': 'false'},
                    run_once=True,
                    install_signal_handlers=False,
                )

        self.assertEqual(0, exit_code)
        run_download.assert_not_called()
        self.assertIn('Scheduler disabled', stdout.getvalue())
        self.assertEqual('', stderr.getvalue())

    def test_enabled_run_on_start_invokes_download_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            with open(config_path, 'w', encoding='utf-8') as config_file:
                config_file.write('{}')
            env = {
                'CS_DEMO_SCHEDULE_ENABLED': 'true',
                'CS_DEMO_SCHEDULE_INTERVAL_SECONDS': '60',
                'CS_DEMO_SCHEDULE_DAILY_TIME': '08:00',
                'CS_DEMO_SCHEDULE_RUN_ON_START': 'true',
                'CS_DEMO_SCHEDULE_CONFIG': config_path,
                'CS_DEMO_SCHEDULE_OUTPUT': '/demos',
                'CS_DEMO_SCHEDULE_PLATFORMS': 'pwa',
            }

            with mock.patch('cs_demo_downloader.cli.run_download_command', return_value=0) as run_download:
                exit_code = cli.run_schedule_command(
                    env=env,
                    run_once=True,
                    install_signal_handlers=False,
                )

        self.assertEqual(0, exit_code)
        run_download.assert_called_once_with(config_path, '/demos', 'pwa', False)

    def test_invalid_interval_fails_clearly(self):
        stderr = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.run_download_command') as run_download:
            with redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(
                    env={
                        'CS_DEMO_SCHEDULE_ENABLED': 'true',
                        'CS_DEMO_SCHEDULE_INTERVAL_SECONDS': '0',
                    },
                    run_once=True,
                    install_signal_handlers=False,
                )

        self.assertEqual(1, exit_code)
        run_download.assert_not_called()
        self.assertIn('positive integer', stderr.getvalue())

    def test_invalid_platform_fails_clearly(self):
        stderr = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.run_download_command') as run_download:
            with redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(
                    env={
                        'CS_DEMO_SCHEDULE_ENABLED': 'true',
                        'CS_DEMO_SCHEDULE_PLATFORMS': 'faceit',
                    },
                    run_once=True,
                    install_signal_handlers=False,
                )

        self.assertEqual(1, exit_code)
        run_download.assert_not_called()
        self.assertIn('Invalid scheduler platform', stderr.getvalue())

    def test_invalid_daily_time_command_fails_clearly(self):
        stderr = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.run_download_command') as run_download:
            with redirect_stderr(stderr):
                exit_code = cli.run_schedule_command(
                    env={
                        'CS_DEMO_SCHEDULE_ENABLED': 'true',
                        'CS_DEMO_SCHEDULE_DAILY_TIME': '24:00',
                    },
                    run_once=True,
                    install_signal_handlers=False,
                )

        self.assertEqual(1, exit_code)
        run_download.assert_not_called()
        self.assertIn('between 00:00 and 23:59', stderr.getvalue())

    def test_create_default_config_writes_docker_schedule(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            stdout = io.StringIO()

            with mock.patch('cs_demo_downloader.cli._next_wait_seconds', return_value=1):
                with mock.patch('cs_demo_downloader.cli.run_download_command', return_value=0) as run_download:
                    with redirect_stdout(stdout):
                        exit_code = cli.run_schedule_command(
                            config_path=config_path,
                            env={'CS_DEMO_CREATE_DEFAULT_CONFIG': 'true'},
                            run_once=True,
                            install_signal_handlers=False,
                        )

            config = load_config(config_path)

        self.assertEqual(0, exit_code)
        self.assertTrue(config.scheduler['enabled'])
        self.assertEqual('08:00', config.scheduler['daily_time'])
        self.assertEqual('/demos', config.download_path)
        self.assertEqual([], config.users_5e)
        self.assertEqual([], config.users_pwa)
        self.assertEqual([], config.users_steam)
        self.assertIn('Created default Docker config', stdout.getvalue())
        run_download.assert_called_once_with(config_path, '/demos', None, True)

    def test_download_command_can_create_default_docker_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, 'config.jsonc')
            stdout = io.StringIO()

            with mock.patch.dict(os.environ, {'CS_DEMO_CREATE_DEFAULT_CONFIG': 'true'}, clear=True):
                with mock.patch('cs_demo_downloader.cli.run_download', return_value=0) as run_download:
                    with redirect_stdout(stdout):
                        exit_code = cli.run_download_command(config_path, '/demos', None, True)

            config = load_config(config_path)

        self.assertEqual(0, exit_code)
        self.assertEqual('08:00', config.scheduler['daily_time'])
        self.assertEqual('/demos', config.download_path)
        self.assertIn('Created default Docker config', stdout.getvalue())
        run_download.assert_called_once()
        self.assertEqual('/demos', run_download.call_args.kwargs['output_path'])
        self.assertIsNone(run_download.call_args.kwargs['platforms'])



class DockerDefaultTests(unittest.TestCase):
    def test_docker_defaults_do_not_download(self):
        repo = Path(__file__).resolve().parents[1]

        for name in ('Dockerfile', 'Dockerfile.wine'):
            dockerfile = (repo / name).read_text(encoding='utf-8')
            self.assertIn('CMD ["schedule"]', dockerfile)
            self.assertIn('ENV PYTHONUNBUFFERED=1', dockerfile)
            self.assertNotIn('CMD ["download"', dockerfile)

        compose = (repo / 'docker-compose.yml').read_text(encoding='utf-8')
        self.assertNotIn('command: ["download"', compose)
        self.assertIn('./config:/config', compose)
        self.assertIn('CS_DEMO_CREATE_DEFAULT_CONFIG: "true"', compose)
        self.assertIn('CS_DEMO_SCHEDULE_CONFIG: "/config/config.jsonc"', compose)
        self.assertIn('command: ["schedule"]', compose)

    def test_default_docker_config_has_daily_scheduler_without_credentials(self):
        config = default_docker_config_data()

        self.assertEqual('/demos', config['download_path'])
        self.assertTrue(config['scheduler']['enabled'])
        self.assertEqual('08:00', config['scheduler']['daily_time'])
        self.assertEqual('/config/config.jsonc', config['scheduler']['config'])
        self.assertEqual('/demos', config['scheduler']['output'])
        self.assertEqual([], config['five_e']['users'])
        self.assertEqual([], config['pwa']['users'])
        self.assertEqual('', config['pwa']['default_access_token'])
        self.assertEqual([], config['steam']['users'])


if __name__ == '__main__':
    unittest.main()

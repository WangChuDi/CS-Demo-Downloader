import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from cs_demo_downloader import cli
from cs_demo_downloader.core.config import Config
from cs_demo_downloader.core.downloader_5e import build_match_metadata as build_5e_match_metadata
from cs_demo_downloader.core.downloader_5e import get_all_demo_metadata as get_5e_demo_metadata
from cs_demo_downloader.core.downloader_pwa import (
    build_match_metadata as build_pwa_match_metadata,
    get_all_demo_metadata as get_pwa_demo_metadata,
)
from cs_demo_downloader.core.metadata import MatchMetadata, metadata_list_to_dicts


class MetadataModelTests(unittest.TestCase):
    def test_metadata_serialization_redacts_sensitive_urls_in_raw_fields(self):
        match = MatchMetadata(
            platform='pwa',
            match_id='match-1',
            demo_url='https://example.invalid/demo.dem?access_token=secret&s=sig&match_id=match-1',
            raw_detail={
                'demo_info': {
                    'demo_url': 'https://example.invalid/demo.dem?access_token=secret&s=sig',
                }
            },
        )

        payload = metadata_list_to_dicts([match], redact_sensitive_urls=True, include_raw=True)
        encoded = json.dumps(payload)

        self.assertNotIn('secret', encoded)
        self.assertNotIn('sig', encoded)
        self.assertIn('access_token=%3Credacted%3E', encoded)

    def test_metadata_serialization_can_omit_raw_fields(self):
        match = MatchMetadata(platform='5e', match_id='match-1', raw_summary={'map': 'de_inferno'})

        payload = metadata_list_to_dicts([match], include_raw=False)

        self.assertNotIn('raw_summary', payload[0])
        self.assertNotIn('raw_detail', payload[0])


class FiveEMetadataTests(unittest.TestCase):
    def test_build_match_metadata_normalizes_detail_payload(self):
        summary = {
            'match_id': 'summary-match',
            'map': 'de_inferno',
            'map_name': '炼狱小镇',
        }
        detail = {
            'main': {
                'match_code': 'detail-match',
                'demo_url': 'https://hz-demo.5eplaycdn.com/pug/detail-match.zip',
                'map': 'de_inferno',
                'map_desc': '炼狱小镇',
                'start_time': 1710000000,
                'end_time': 1710003000,
                'location_full': 'Shanghai Server',
                'match_winner': '1',
                'season': '42',
                'year': '2026',
                'round_total': '24',
                'group1_all_score': 13,
                'group2_all_score': 11,
                'group1_tid': 'team-1',
                'group2_tid': 'team-2',
                'group1_uids': 'player-1,player-3',
                'group2_uids': ['player-2', 'player-4'],
                'group1_origin_elo': '1800',
                'group2_origin_elo': '1700',
                'group1_change_elo': '12',
                'group2_change_elo': '-12',
                'group1_fh_score': 9,
                'group1_sh_score': 4,
                'group1_fh_role': 'T',
                'group1_sh_role': 'CT',
                'group2_fh_role': 'CT',
                'group2_sh_role': 'T',
                'mvp_uid': 'player-1',
                'most_assist_uid': 'player-2',
                'most_awp_uid': 'player-3',
                'most_end_uid': 'player-4',
                'most_first_kill_uid': 'player-5',
                'most_headshot_uid': 'player-6',
                'most_jump_uid': 'player-7',
                'most_1v2_uid': 'player-8',
            },
            'season_type': 'ladder',
            'group_1': [
                {
                    'fight': {
                        'uid': 'player-1',
                        'kill': 25,
                        'death': 15,
                        'assist': 4,
                        'rating': '1.23',
                        'rating2': '1.55',
                        'rating3': '7.77',
                        'adr': '95.5',
                        'rws': '14.2',
                        'kast': '0.82',
                        'headshot': '12',
                        'per_headshot': '0.48',
                        'first_kill': '3',
                        'first_death': '1',
                        'awp_kill': '2',
                        'kill_1': '7',
                        'kill_2': '3',
                        'kill_3': '1',
                        'kill_4': '0',
                        'kill_5': '0',
                        'end_1v1': '1',
                        'end_1v2': '0',
                        'end_1v3': '0',
                        'end_1v4': '0',
                        'end_1v5': '0',
                        'planted_bomb': '1',
                        'defused_bomb': '0',
                        'throw_harm': '33',
                        'throw_harm_enemy': '22',
                        'flash_enemy': '5',
                        'flash_enemy_time': '12.5',
                        'flash_team': '1',
                        'flash_team_time': '2.0',
                        'perfect_kill': '2',
                        'assisted_kill': '4',
                        'revenge_kill': '1',
                        'benefit_kill': '3',
                        'team_kill': '0',
                        'jump_kill': '1',
                        'knife_kill': '0',
                        'entry_kill': '3',
                        'trade_kill': '2',
                        'is_mvp': '1',
                        'is_svp': '0',
                        'is_highlight': '1',
                    },
                    'fight_t': {'kill': '15', 'death': '8', 'assist': '2', 'rating2': '1.7', 'rating3': '2.5'},
                    'fight_ct': {'kill': '10', 'death': '7', 'assist': '2', 'rating2': '1.3', 'rating3': '5.0'},
                    'level_info': {'score': '1888', 'level': '8', 'level_name': 'S'},
                    'sts': {'elo': '1901', 'change_elo': '+12'},
                    'user_info': {
                        'user_data': {
                            'username': 'player-one',
                            'domain': 'player-one-domain',
                            'profile': {'nickname': 'profile-player-one', 'avatar_url': 'https://avatar.invalid/a.png'},
                            'steam': {'steamId': 'steam-1', 'personaname': 'steam-player-one'},
                        }
                    },
                }
            ],
            'group_2': [
                {
                    'fight': {'kill': 19, 'death': 18, 'assist': 7, 'rating': '0.97'},
                    'user_info': {'nick_name': 'player-two'},
                }
            ],
            'advanced': {'generated': True},
            'leetify_rating': {'leetify_data': {'round_total': 24}},
            'vip_plus': {'player-key': {'kast': 80}},
        }

        match = build_5e_match_metadata(summary, detail)

        self.assertIsNotNone(match)
        if match is None:
            self.fail('expected metadata')
        self.assertEqual('5e', match.platform)
        self.assertEqual('detail-match', match.match_id)
        self.assertEqual('de_inferno', match.map_name)
        self.assertEqual('炼狱小镇', match.map_label)
        self.assertEqual('Shanghai Server', match.location)
        self.assertEqual('1', match.match_winner)
        self.assertEqual(42, match.season)
        self.assertEqual('ladder', match.season_type)
        self.assertEqual(2026, match.year)
        self.assertEqual(24, match.round_total)
        self.assertEqual(13, match.teams[0].score)
        self.assertEqual('team-1', match.teams[0].team_id)
        self.assertEqual(['player-1', 'player-3'], match.teams[0].player_ids)
        self.assertEqual('T', match.teams[0].first_half_side)
        self.assertEqual('CT', match.teams[0].second_half_side)
        self.assertEqual(1800, match.teams[0].origin_elo)
        self.assertEqual(12, match.teams[0].change_elo)
        self.assertEqual(['player-2', 'player-4'], match.teams[1].player_ids)
        self.assertEqual(9, match.teams[0].half_scores['first_half'])
        self.assertEqual('player-1', match.match_awards['mvp_player_id'])
        self.assertEqual('player-8', match.match_awards['most_1v2_clutches_player_id'])
        self.assertEqual('profile-player-one', match.players[0].name)
        self.assertEqual('player-1', match.players[0].player_id)
        self.assertEqual('steam-1', match.players[0].steam_id)
        self.assertEqual('https://www.5eplay.com/player/player-one-domain', match.players[0].profile['profile_url'])
        self.assertEqual('https://steamcommunity.com/profiles/steam-1', match.players[0].profile['steam_profile_url'])
        self.assertEqual('steam-player-one', match.players[0].profile['steam_nickname'])
        self.assertEqual({'score': 1888, 'level': 8, 'level_name': 'S', 'elo': 1901, 'change_elo': 12}, match.players[0].ladder_stats)
        self.assertEqual(25, match.players[0].kills)
        self.assertEqual(4, match.players[0].assists)
        self.assertEqual(15, match.players[0].deaths)
        self.assertEqual(1.55, match.players[0].rating)
        self.assertEqual(7.77, match.players[0].swing_score)
        self.assertEqual(95.5, match.players[0].adr)
        self.assertEqual(0.48, match.players[0].headshot_rate)
        self.assertEqual(4, match.players[0].multi_kill_count)
        self.assertEqual({'1': 7, '2': 3, '3': 1, '4': 0, '5': 0}, match.players[0].multi_kills)
        self.assertEqual(1, match.players[0].clutch_count)
        self.assertEqual({'1': 1, '2': 0, '3': 0, '4': 0, '5': 0}, match.players[0].clutches)
        self.assertEqual(1, match.players[0].bomb_plants)
        self.assertEqual({'kills': 15, 'deaths': 8, 'assists': 2, 'rating': 1.7, 'swing_score': 2.5}, match.players[0].side_stats['t'])
        self.assertEqual({'kills': 10, 'deaths': 7, 'assists': 2, 'rating': 1.3, 'swing_score': 5.0}, match.players[0].side_stats['ct'])
        self.assertEqual(33, match.players[0].utility_stats['utility_damage'])
        self.assertEqual(12.5, match.players[0].utility_stats['enemy_flash_duration'])
        self.assertEqual(2, match.players[0].impact_stats['perfect_kills'])
        self.assertEqual(3, match.players[0].impact_stats['benefit_kills'])
        self.assertEqual(1, match.players[0].impact_stats['jump_kills'])
        self.assertEqual(2, match.players[0].impact_stats['trade_kills'])
        self.assertEqual({'is_mvp': True, 'is_svp': False, 'is_highlight': True}, match.players[0].award_flags)
        self.assertEqual('player-two', match.players[1].name)
        self.assertEqual(19, match.players[1].kills)
        self.assertEqual({'generated': True}, match.raw_detail['advanced'])
        self.assertIn('leetify_rating', match.raw_detail)
        self.assertIn('vip_plus', match.raw_detail)

    def test_get_all_demo_metadata_merges_advanced_payloads(self):
        with mock.patch('cs_demo_downloader.core.downloader_5e.get_uuid', return_value='uuid'):
            with mock.patch('cs_demo_downloader.core.downloader_5e.get_match_list_records', return_value=[{'match_id': 'match-1'}]):
                with mock.patch('cs_demo_downloader.core.downloader_5e.get_match_detail', return_value={
                    'main': {'match_code': 'match-1', 'demo_url': 'https://example.invalid/match-1.zip'},
                    'group_1': [],
                    'group_2': [],
                }):
                    with mock.patch('cs_demo_downloader.core.downloader_5e.get_match_extra_data', return_value={
                        'advanced': {'role': 'entry'},
                        'vip_plus': {'player-key': {'awp_kill': 3}},
                    }):
                        matches = get_5e_demo_metadata('userid', limit=1)

        self.assertEqual(1, len(matches))
        self.assertEqual({'role': 'entry'}, matches[0].raw_detail['advanced'])
        self.assertIn('vip_plus', matches[0].raw_detail)


class PwaMetadataTests(unittest.TestCase):
    def test_build_match_metadata_uses_report_payload_when_available(self):
        summary = {'match': 'summary-match', 'map': 'de_mirage'}
        report = {
            'match_id': 'report-match',
            'report': {
                'match_id': 'report-match',
                'game_mode': 'ladder',
                'match_type': 'ranked',
                'is_green': True,
                'win_camp': 'T',
                'win_team_id': '2',
                'lose_team_id': '3',
                'map': 'de_ancient',
                'location': 'Beijing',
                'match_winner': 'T',
                'season': '9',
                'season_type': 'ladder',
                'year': '2026',
                'round_total': '23',
                'match_starttime': '1710000000',
                'match_endtime': '1710003600',
                't_team_id': '2',
                'ct_team_id': '3',
                't_origin_elo': '1500',
                't_change_elo': '10',
                'ct_origin_elo': '1510',
                'ct_change_elo': '-10',
                'mvp_uid': 'user-1',
                't_win_times': '13',
                'ct_win_times': '10',
                'players': [
                    {
                        'user_id': 'user-1',
                        'steam_id': 'steam-1',
                        'steamAccountId': 'account-1',
                        'steam_nick': 'pwa-player-one',
                        'avatar_url': 'https://avatar.invalid/pwa.png',
                        'team_id': '2',
                        'camp': 'T',
                        'kill': '21',
                        'death': '17',
                        'assist': '5',
                        'rating': '1.11',
                        'adpr': '88.8',
                        'rws': '12.3',
                        'headshot_kill_count': '10',
                        'first_kill': '4',
                        'first_death': '2',
                        'two_kill': '3',
                        'three_kill': '1',
                        'four_kill': '0',
                        'five_kill': '0',
                        '1v1': '1',
                        '1v2': '0',
                        'score': '1666',
                        'level': '7',
                        'grenade_damage': '45',
                        'flash_enemy': '4',
                        'flash_enemy_time': '9.5',
                        'awp_kill': '2',
                        'jump_kill': '1',
                        'trade_kill': '3',
                        'is_mvp': '1',
                        'actual_accuracy': '0.47',
                        'avg_reaction_time': '250',
                        'weapon_cause_damage_type_count': {'ak47': 5},
                        'cellphone': 'sensitive-phone',
                    },
                    {
                        'steam_nick': 'pwa-player-two',
                        'team_id': '3',
                        'camp': 'CT',
                        'kill': '18',
                        'death': '19',
                        'assist': '8',
                        'pw_rating': '0.99',
                    },
                ],
                'results': [
                    {
                        'round': '1',
                        'win_camp': 'T',
                        'win_team_id': '2',
                        'lose_team_id': '3',
                        'win_type': 'bomb',
                        'half_match_type': 'first',
                        'bomb_planter': 'user-1',
                        'bomb_defuser': '',
                    }
                ],
            },
            'demo_info': {
                'demo_id': 'demo-1',
                'demo_is_available': True,
                'demo_url': 'https://pwaweblogin.wmpvp.com/csgo/demo/report-match_0.dem?access_token=secret-token&s=secret-signature',
                'expire_soon': False,
                'expired': False,
                'has_demo': True,
                'is_disabled': False,
            },
            'perfect_moment': {'mapName': 'de_ancient', 'matchTime': '2026-05-26 22:54:59'},
            'round_simple_list': [{'round': '1', 'kill': '{"1":1}'}],
        }

        match = build_pwa_match_metadata(summary, 'https://fallback.invalid/demo.dem', report)

        self.assertIsNotNone(match)
        if match is None:
            self.fail('expected metadata')
        self.assertEqual('pwa', match.platform)
        self.assertEqual('report-match', match.match_id)
        self.assertEqual('de_ancient', match.map_name)
        self.assertEqual('Beijing', match.location)
        self.assertEqual('T', match.match_winner)
        self.assertEqual(9, match.season)
        self.assertEqual('ladder', match.season_type)
        self.assertEqual(2026, match.year)
        self.assertEqual(23, match.round_total)
        self.assertTrue(match.demo_available)
        self.assertEqual('demo-1', match.demo_info['demo_id'])
        self.assertEqual(False, match.demo_info['expire_soon'])
        self.assertEqual('ladder', match.platform_match['game_mode'])
        self.assertEqual(True, match.platform_match['is_green'])
        self.assertEqual('2', match.platform_match['win_team_id'])
        self.assertEqual(1, match.round_results[0]['round'])
        self.assertEqual('bomb', match.round_results[0]['win_type'])
        self.assertEqual(13, match.teams[0].score)
        self.assertEqual('2', match.teams[0].team_id)
        self.assertEqual(['user-1'], match.teams[0].player_ids)
        self.assertEqual(1500, match.teams[0].origin_elo)
        self.assertEqual(10, match.teams[0].change_elo)
        self.assertEqual(10, match.teams[1].score)
        self.assertEqual('user-1', match.match_awards['mvp_player_id'])
        self.assertEqual('pwa-player-one', match.players[0].name)
        self.assertEqual('user-1', match.players[0].player_id)
        self.assertEqual('steam-1', match.players[0].steam_id)
        self.assertEqual('https://steamcommunity.com/profiles/steam-1', match.players[0].profile['steam_profile_url'])
        self.assertEqual('account-1', match.players[0].profile['steam_account_id'])
        self.assertEqual('https://avatar.invalid/pwa.png', match.players[0].profile['avatar_url'])
        self.assertEqual({'score': 1666, 'level': 7}, match.players[0].ladder_stats)
        self.assertEqual(21, match.players[0].kills)
        self.assertEqual(5, match.players[0].assists)
        self.assertEqual(17, match.players[0].deaths)
        self.assertEqual(1.11, match.players[0].rating)
        self.assertEqual(88.8, match.players[0].adr)
        self.assertEqual(10, match.players[0].headshots)
        self.assertEqual(4, match.players[0].multi_kill_count)
        self.assertEqual({'2': 3, '3': 1, '4': 0, '5': 0}, match.players[0].multi_kills)
        self.assertEqual(1, match.players[0].clutch_count)
        self.assertEqual({'1': 1, '2': 0}, match.players[0].clutches)
        self.assertEqual(45, match.players[0].utility_stats['utility_damage'])
        self.assertEqual(9.5, match.players[0].utility_stats['enemy_flash_duration'])
        self.assertEqual(2, match.players[0].impact_stats['awp_kills'])
        self.assertEqual(1, match.players[0].impact_stats['jump_kills'])
        self.assertEqual(3, match.players[0].impact_stats['trade_kills'])
        self.assertEqual({'is_mvp': True}, match.players[0].award_flags)
        self.assertEqual('0.47', match.players[0].platform_stats['actual_accuracy'])
        self.assertEqual({'ak47': 5}, match.players[0].platform_stats['weapon_cause_damage_type_count'])
        self.assertNotIn('cellphone', match.players[0].platform_stats)
        self.assertEqual('pwa-player-two', match.players[1].name)
        self.assertEqual(18, match.players[1].kills)
        self.assertIn('perfect_moment', match.raw_detail)
        self.assertIn('round_simple_list', match.raw_detail)

    def test_get_all_demo_metadata_falls_back_without_report_fetcher(self):
        with mock.patch('cs_demo_downloader.core.downloader_pwa.get_match_list_records', return_value=[{'match': 'match-1'}]):
            with mock.patch('cs_demo_downloader.core.downloader_pwa.random.randint', return_value=123456):
                with mock.patch('cs_demo_downloader.core.downloader_pwa.time.time', return_value=1710000000):
                    matches = get_pwa_demo_metadata(
                        'steamid',
                        'token',
                        signer=lambda _randnum, _timestamp, _data: 'signed',
                        report_fetcher=None,
                        extra_fetcher=None,
                    )

        self.assertEqual(1, len(matches))
        self.assertEqual('match-1', matches[0].match_id)
        self.assertIn('access_token=token', matches[0].demo_url or '')
        self.assertTrue(matches[0].demo_available)

    def test_get_all_demo_metadata_uses_injected_report_fetcher(self):
        report_fetcher = mock.Mock(return_value={
            'report': {'match_id': 'match-1', 'map': 'de_nuke'},
            'demo_info': {'demo_is_available': True},
        })
        extra_fetcher = mock.Mock(return_value={
            'perfect_moment': {'matchId': 'match-1'},
            'round_simple_list': [{'round': '1'}],
        })

        with mock.patch('cs_demo_downloader.core.downloader_pwa.get_match_list_records', return_value=[{'match': 'match-1'}]):
            matches = get_pwa_demo_metadata(
                'steamid',
                'token',
                signer=lambda _randnum, _timestamp, _data: 'signed',
                report_fetcher=report_fetcher,
                extra_fetcher=extra_fetcher,
            )

        report_fetcher.assert_called_once_with('match-1', 'steamid', 'token')
        extra_fetcher.assert_called_once_with('match-1', 'steamid', 'token')
        self.assertEqual('de_nuke', matches[0].map_name)
        self.assertEqual({'matchId': 'match-1'}, matches[0].raw_detail['perfect_moment'])
        self.assertEqual([{'round': '1'}], matches[0].raw_detail['round_simple_list'])


class MetadataCliTests(unittest.TestCase):
    def test_run_metadata_outputs_redacted_json(self):
        config = Config()
        config.add_user_pwa('pwa-user', 'steamid', 'token')
        stdout = io.StringIO()
        match = MatchMetadata(
            platform='pwa',
            match_id='match-1',
            demo_url='https://pwaweblogin.wmpvp.com/csgo/demo/match-1_0.dem?access_token=secret-token&s=secret-signature',
        )

        with mock.patch('cs_demo_downloader.cli.get_pwa_metadata', return_value=[match]):
            with mock.patch('cs_demo_downloader.cli.build_pwa_demo_url_signer', return_value=lambda _r, _t, _d: 'sig'):
                with redirect_stdout(stdout):
                    exit_code = cli.run_metadata(config, platform='pwa', limit=1, pretty=True, include_raw=True)

        self.assertEqual(0, exit_code)
        output = stdout.getvalue()
        self.assertNotIn('secret-token', output)
        self.assertNotIn('secret-signature', output)
        self.assertIn('access_token=%3Credacted%3E', output)
        payload = json.loads(output)
        self.assertEqual('match-1', payload[0]['match_id'])

    def test_metadata_command_loads_config_and_dispatches(self):
        config = Config()
        stdout = io.StringIO()

        with mock.patch('cs_demo_downloader.cli.load_config', return_value=config) as load_config:
            with mock.patch('cs_demo_downloader.cli.collect_5e_metadata', return_value=[]):
                with redirect_stdout(stdout):
                    exit_code = cli.run_metadata_command(
                        '/config/config.jsonc',
                        '5e',
                        False,
                        3,
                        False,
                        False,
                    )

        self.assertEqual(0, exit_code)
        load_config.assert_called_once_with('/config/config.jsonc')
        self.assertEqual('[]\n', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()

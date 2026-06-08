"""
5E 平台 Demo 下载器
"""
import requests
from typing import Optional, List, Dict
from collections.abc import Mapping

from .metadata import JSONValue, MatchMetadata, MatchPlayer, MatchTeam, json_object, optional_float, optional_int, optional_str
from .utils import get_end_of_day_timestamp, get_timestamp_days_ago


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

URL_ID_TRANSFER = 'https://gate.5eplay.com/userinterface/http/v1/userinterface/idTransfer'
URL_MATCH_ADVANCED_PREFIX = 'https://gate.5eplay.com/crane/http/api/data/match/advanced'
URL_MATCH_LEETIFY_PREFIX = 'https://gate.5eplay.com/crane/http/api/match/leetify_rating'
URL_MATCH_VIP_PLUS_PREFIX = 'https://gate.5eplay.com/crane/http/api/data/vip_plus_match_data'


def get_uuid(userid: str) -> Optional[str]:
    """
    通过 5E userid 获取 uuid
    
    Args:
        userid: 5E 用户 ID（如 11814738gjdwn7）
    
    Returns:
        uuid 字符串，失败返回 None
    """
    try:
        payload = {
            "trans": {
                "domain": userid
            }
        }
        response = requests.post(URL_ID_TRANSFER, json=payload, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            uuid = data.get('data', {}).get('uuid')
            return uuid
        else:
            print(f"Failed to get uuid, status: {response.status_code}")
            return None
    except requests.RequestException as e:
        print(f"Error getting uuid: {e}")
        return None


def get_match_list(
    uuid: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: int = 30
) -> List[str]:
    """
    获取比赛列表
    
    Args:
        uuid: 用户 uuid
        start_time: 开始时间戳（默认 180 天前）
        end_time: 结束时间戳（默认当天）
        limit: 返回数量限制
    
    Returns:
        match_id 列表
    """
    if start_time is None:
        start_time = get_timestamp_days_ago(180)
    if end_time is None:
        end_time = get_end_of_day_timestamp()
    
    records = get_match_list_records(uuid, start_time=start_time, end_time=end_time, limit=limit)
    match_ids: List[str] = []
    for match in records:
        match_id = match.get('match_id')
        if isinstance(match_id, str):
            match_ids.append(match_id)
    return match_ids


def get_match_list_records(
    uuid: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: int = 30
) -> List[Dict[str, object]]:
    """获取 5E 比赛列表原始记录。"""
    if start_time is None:
        start_time = get_timestamp_days_ago(180)
    if end_time is None:
        end_time = get_end_of_day_timestamp()

    url = (
        f'https://gate.5eplay.com/crane/http/api/data/match/list'
        f'?match_type=-1&page=1&date=0'
        f'&start_time={start_time}&end_time={end_time}'
        f'&uuid={uuid}&limit={limit}&cs_type=0'
    )
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            match_data = data.get('data', [])
            if isinstance(match_data, list):
                records: List[Dict[str, object]] = []
                for match in match_data:
                    if isinstance(match, dict):
                        records.append({str(key): value for key, value in match.items()})
                return records

        return []
    except requests.RequestException as e:
        print(f"Error getting match list: {e}")
        return []


def get_demo_url(match_id: str) -> Optional[str]:
    """
    获取比赛的 Demo 下载链接
    
    Args:
        match_id: 比赛 ID
    
    Returns:
        Demo 下载 URL，失败返回 None
    """
    detail = get_match_detail(match_id)
    main = detail.get('main')
    if isinstance(main, dict):
        demo_url = main.get('demo_url')
        if isinstance(demo_url, str):
            return demo_url
    return None


def get_match_detail(match_id: str) -> Dict[str, object]:
    """获取 5E 比赛详情原始 data 对象。"""
    url = f'https://gate.5eplay.com/crane/http/api/data/match/{match_id}'

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                detail = data.get('data', {})
                if isinstance(detail, dict):
                    return {str(key): value for key, value in detail.items()}

        return {}
    except requests.RequestException as e:
        print(f"Error getting match detail for match {match_id}: {e}")
        return {}


def get_match_advanced_data(match_id: str) -> Dict[str, object]:
    """获取 5E 比赛高级角色评分原始 data。"""
    return _get_optional_match_data(f'{URL_MATCH_ADVANCED_PREFIX}/{match_id}', 'advanced data', match_id)


def get_match_leetify_rating(match_id: str) -> Dict[str, object]:
    """获取 5E Leetify-like 回合分析原始 data。"""
    return _get_optional_match_data(f'{URL_MATCH_LEETIFY_PREFIX}/{match_id}', 'leetify rating', match_id)


def get_match_vip_plus_data(match_id: str) -> Dict[str, object]:
    """获取 5E VIP+ 补充统计原始 data。"""
    return _get_optional_match_data(f'{URL_MATCH_VIP_PLUS_PREFIX}/{match_id}', 'vip plus data', match_id)


def get_match_extra_data(match_id: str) -> Dict[str, object]:
    """Best-effort 获取 5E 可构造的高级数据。"""
    extras: Dict[str, object] = {}
    advanced = get_match_advanced_data(match_id)
    if advanced:
        extras['advanced'] = advanced
    leetify_rating = get_match_leetify_rating(match_id)
    if leetify_rating:
        extras['leetify_rating'] = leetify_rating
    vip_plus = get_match_vip_plus_data(match_id)
    if vip_plus:
        extras['vip_plus'] = vip_plus
    return extras


def _get_optional_match_data(url: str, label: str, match_id: str) -> Dict[str, object]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        print(f"Error getting 5E {label} for match {match_id}: {e}")
        return {}

    if response.status_code != 200:
        return {}
    data = response.json()
    if not isinstance(data, dict):
        return {}
    payload = data.get('data', {})
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items()}


def get_all_demo_urls(userid: str, limit: int = 30) -> Dict[str, str]:
    """
    获取用户所有比赛的 Demo 下载链接
    
    Args:
        userid: 5E 用户 ID
        limit: 返回数量限制
    
    Returns:
        {match_id: demo_url} 字典
    """
    uuid = get_uuid(userid)
    if not uuid:
        return {}
    
    match_ids = get_match_list(uuid, limit=limit)
    demo_urls = {}
    
    for match_id in match_ids:
        demo_url = get_demo_url(match_id)
        if demo_url:
            demo_urls[match_id] = demo_url
    
    return demo_urls


def build_match_metadata(summary: Mapping[str, object], detail: Mapping[str, object]) -> Optional[MatchMetadata]:
    """Build normalized 5E metadata from list and detail payloads."""
    main_value = detail.get('main')
    main = main_value if isinstance(main_value, Mapping) else {}
    match_id = optional_str(main.get('match_code')) or optional_str(summary.get('match_id'))
    if match_id is None:
        return None

    group1_score = optional_int(main.get('group1_all_score')) or optional_int(summary.get('group1_all_score'))
    group2_score = optional_int(main.get('group2_all_score')) or optional_int(summary.get('group2_all_score'))

    teams = [
        MatchTeam(
            name='group_1',
            team_id=optional_str(main.get('group1_tid')),
            player_ids=_split_player_ids(main.get('group1_uids')),
            side=optional_str(main.get('group1_fh_role')),
            first_half_side=optional_str(main.get('group1_fh_role')),
            second_half_side=optional_str(main.get('group1_sh_role')),
            score=group1_score,
            origin_elo=optional_int(main.get('group1_origin_elo')),
            change_elo=optional_int(main.get('group1_change_elo')),
            half_scores=_five_e_half_scores(main, 'group1'),
        ),
        MatchTeam(
            name='group_2',
            team_id=optional_str(main.get('group2_tid')),
            player_ids=_split_player_ids(main.get('group2_uids')),
            side=optional_str(main.get('group2_fh_role')),
            first_half_side=optional_str(main.get('group2_fh_role')),
            second_half_side=optional_str(main.get('group2_sh_role')),
            score=group2_score,
            origin_elo=optional_int(main.get('group2_origin_elo')),
            change_elo=optional_int(main.get('group2_change_elo')),
            half_scores=_five_e_half_scores(main, 'group2'),
        ),
    ]

    return MatchMetadata(
        platform='5e',
        match_id=match_id,
        demo_url=optional_str(main.get('demo_url')),
        demo_available=optional_str(main.get('demo_url')) is not None,
        map_name=optional_str(main.get('map')) or optional_str(summary.get('map')),
        map_label=optional_str(main.get('map_desc')) or optional_str(summary.get('map_name')),
        location=optional_str(main.get('location_full')) or optional_str(main.get('location')),
        match_winner=optional_str(main.get('match_winner')),
        season=optional_int(main.get('season')),
        season_type=optional_str(detail.get('season_type')) or optional_str(main.get('season_type')),
        year=optional_int(main.get('year')),
        round_total=optional_int(main.get('round_total')),
        started_at=optional_int(main.get('start_time')) or optional_int(summary.get('start_time')),
        ended_at=optional_int(main.get('end_time')) or optional_int(summary.get('end_time')),
        teams=teams,
        players=_five_e_players(detail),
        match_awards=_five_e_match_awards(main),
        raw_summary=json_object(dict(summary)),
        raw_detail=json_object(dict(detail)),
    )


def get_all_demo_metadata(userid: str, limit: int = 30) -> List[MatchMetadata]:
    """获取用户所有 5E 比赛的规范化 metadata。"""
    uuid = get_uuid(userid)
    if not uuid:
        return []

    metadata: List[MatchMetadata] = []
    for summary in get_match_list_records(uuid, limit=limit):
        match_id = summary.get('match_id')
        if not isinstance(match_id, str):
            continue
        detail = get_match_detail(match_id)
        extras = get_match_extra_data(match_id)
        if extras:
            detail = {**detail, **extras}
        match_metadata = build_match_metadata(summary, detail)
        if match_metadata is not None:
            metadata.append(match_metadata)
    return metadata


def _five_e_half_scores(main: Mapping[str, object], group_prefix: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    first_half = optional_int(main.get(f'{group_prefix}_fh_score'))
    second_half = optional_int(main.get(f'{group_prefix}_sh_score'))
    if first_half is not None:
        scores['first_half'] = first_half
    if second_half is not None:
        scores['second_half'] = second_half
    return scores


def _five_e_match_awards(main: Mapping[str, object]) -> Dict[str, JSONValue]:
    awards: Dict[str, JSONValue] = {}
    for normalized_key, source_key in (
        ('mvp_player_id', 'mvp_uid'),
        ('most_assists_player_id', 'most_assist_uid'),
        ('most_awp_kills_player_id', 'most_awp_uid'),
        ('most_clutches_player_id', 'most_end_uid'),
        ('most_first_kills_player_id', 'most_first_kill_uid'),
        ('most_headshots_player_id', 'most_headshot_uid'),
        ('most_jump_kills_player_id', 'most_jump_uid'),
        ('most_1v2_clutches_player_id', 'most_1v2_uid'),
    ):
        value = optional_str(main.get(source_key))
        if value is not None:
            awards[normalized_key] = value
    return awards


def _split_player_ids(value: object) -> List[str]:
    if isinstance(value, list):
        return [player_id for item in value if (player_id := optional_str(item)) is not None]
    text = optional_str(value)
    if text is None:
        return []
    return [item.strip() for item in text.replace(';', ',').split(',') if item.strip()]


def _five_e_players(detail: Mapping[str, object]) -> List[MatchPlayer]:
    players: List[MatchPlayer] = []
    for team_index, group_name in ((1, 'group_1'), (2, 'group_2')):
        group_value = detail.get(group_name)
        if not isinstance(group_value, list):
            continue
        for row in group_value:
            if not isinstance(row, Mapping):
                continue
            fight_value = row.get('fight')
            fight = fight_value if isinstance(fight_value, Mapping) else row
            user_info_value = row.get('user_info')
            user_info = user_info_value if isinstance(user_info_value, Mapping) else {}
            user_data_value = user_info.get('user_data')
            user_data = user_data_value if isinstance(user_data_value, Mapping) else user_info
            profile_value = user_data.get('profile')
            profile = profile_value if isinstance(profile_value, Mapping) else {}
            steam_value = user_data.get('steam')
            steam = steam_value if isinstance(steam_value, Mapping) else {}
            multi_kills = _numbered_stats(fight, 'kill_', 1, 5)
            clutches = _numbered_stats(fight, 'end_1v', 1, 5)
            level_info_value = row.get('level_info')
            level_info = level_info_value if isinstance(level_info_value, Mapping) else {}
            sts_value = row.get('sts')
            sts = sts_value if isinstance(sts_value, Mapping) else {}
            players.append(MatchPlayer(
                player_id=optional_str(fight.get('uid')) or optional_str(user_data.get('uid')),
                steam_id=optional_str(steam.get('steamId')) or optional_str(steam.get('steam_id')),
                name=(
                    optional_str(user_info.get('nick_name'))
                    or optional_str(user_info.get('nickname'))
                    or optional_str(profile.get('nickname'))
                    or optional_str(user_data.get('username'))
                ),
                profile=_five_e_player_profile(user_info, user_data, profile, steam),
                team_index=team_index,
                ladder_stats=_five_e_ladder_stats(level_info, sts),
                kills=optional_int(fight.get('kill')),
                deaths=optional_int(fight.get('death')),
                assists=optional_int(fight.get('assist')),
                rating=optional_float(fight.get('rating2')) or optional_float(fight.get('rating')),
                swing_score=optional_float(fight.get('rating3')),
                adr=optional_float(fight.get('adr')),
                rws=optional_float(fight.get('rws')),
                kast=optional_float(fight.get('kast')),
                headshots=optional_int(fight.get('headshot')),
                headshot_rate=optional_float(fight.get('per_headshot')),
                first_kills=optional_int(fight.get('first_kill')),
                first_deaths=optional_int(fight.get('first_death')),
                awp_kills=optional_int(fight.get('awp_kill')),
                multi_kill_count=sum(value for key, value in multi_kills.items() if key != '1'),
                multi_kills=multi_kills,
                clutch_count=sum(clutches.values()),
                clutches=clutches,
                bomb_plants=optional_int(fight.get('planted_bomb')),
                bomb_defuses=optional_int(fight.get('defused_bomb')),
                side_stats=_five_e_side_stats(row),
                utility_stats=_five_e_utility_stats(fight),
                impact_stats=_five_e_impact_stats(fight),
                award_flags=_five_e_award_flags(fight),
                raw=json_object(dict(row)),
            ))
    return players


def _five_e_ladder_stats(level_info: Mapping[str, object], sts: Mapping[str, object]) -> Dict[str, JSONValue]:
    stats: Dict[str, JSONValue] = {}
    for normalized_key, source in (
        ('score', level_info.get('score')),
        ('level', level_info.get('level')),
        ('level_name', level_info.get('level_name')),
        ('rank', level_info.get('rank')),
        ('rank_name', level_info.get('rank_name')),
        ('change_score', level_info.get('change_score')),
        ('elo', sts.get('elo')),
        ('origin_elo', sts.get('origin_elo')),
        ('change_elo', sts.get('change_elo')),
    ):
        value = _normalized_scalar(source)
        if value is not None:
            stats[normalized_key] = value
    return stats


def _five_e_player_profile(
    user_info: Mapping[str, object],
    user_data: Mapping[str, object],
    profile: Mapping[str, object],
    steam: Mapping[str, object],
) -> Dict[str, JSONValue]:
    player_id = optional_str(user_data.get('domain')) or optional_str(user_data.get('uid')) or optional_str(user_info.get('uid'))
    steam_id = optional_str(steam.get('steamId')) or optional_str(steam.get('steam_id'))
    stats: Dict[str, JSONValue] = {}
    for normalized_key, source in (
        ('profile_url', f'https://www.5eplay.com/player/{player_id}' if player_id else None),
        ('avatar_url', profile.get('avatar') or profile.get('avatar_url') or user_info.get('avatar')),
        ('nickname', profile.get('nickname') or user_info.get('nick_name') or user_info.get('nickname')),
        ('username', user_data.get('username')),
        ('steam_profile_url', f'https://steamcommunity.com/profiles/{steam_id}' if steam_id else None),
        ('steam_nickname', steam.get('personaname') or steam.get('nickname')),
    ):
        value = _normalized_scalar(source)
        if value is not None:
            stats[normalized_key] = value
    return stats


def _five_e_side_stats(row: Mapping[str, object]) -> Dict[str, JSONValue]:
    stats: Dict[str, JSONValue] = {}
    for side_name, source_key in (('t', 'fight_t'), ('ct', 'fight_ct')):
        value = row.get(source_key)
        if isinstance(value, Mapping):
            stats[side_name] = _compact_stats(value, {
                'kills': 'kill',
                'deaths': 'death',
                'assists': 'assist',
                'adr': 'adr',
                'rws': 'rws',
                'rating': 'rating2',
                'swing_score': 'rating3',
                'first_kills': 'first_kill',
                'first_deaths': 'first_death',
            })
    return stats


def _five_e_utility_stats(fight: Mapping[str, object]) -> Dict[str, JSONValue]:
    return _compact_stats(fight, {
        'bomb_plants': 'planted_bomb',
        'bomb_defuses': 'defused_bomb',
        'utility_damage': 'throw_harm',
        'enemy_utility_damage': 'throw_harm_enemy',
        'enemies_flashed': 'flash_enemy',
        'enemy_flash_duration': 'flash_enemy_time',
        'teammates_flashed': 'flash_team',
        'team_flash_duration': 'flash_team_time',
    })


def _five_e_impact_stats(fight: Mapping[str, object]) -> Dict[str, JSONValue]:
    return _compact_stats(fight, {
        'awp_kills': 'awp_kill',
        'jump_kills': 'jump_kill',
        'knife_kills': 'knife_kill',
        'entry_kills': 'entry_kill',
        'trade_kills': 'trade_kill',
        'first_kills': 'first_kill',
        'first_deaths': 'first_death',
        'perfect_kills': 'perfect_kill',
        'assisted_kills': 'assisted_kill',
        'revenge_kills': 'revenge_kill',
        'benefit_kills': 'benefit_kill',
        'team_kills': 'team_kill',
    })


def _five_e_award_flags(fight: Mapping[str, object]) -> Dict[str, JSONValue]:
    flags: Dict[str, JSONValue] = {}
    for normalized_key, source_key in (
        ('is_mvp', 'is_mvp'),
        ('is_svp', 'is_svp'),
        ('is_highlight', 'is_highlight'),
    ):
        value = optional_int(fight.get(source_key))
        if value is not None:
            flags[normalized_key] = bool(value)
    return flags


def _numbered_stats(source: Mapping[str, object], prefix: str, start: int, end: int) -> Dict[str, int]:
    values: Dict[str, int] = {}
    for index in range(start, end + 1):
        key = f'{prefix}{index}'
        value = optional_int(source.get(key))
        if value is not None:
            values[str(index)] = value
    return values


def _compact_stats(source: Mapping[str, object], mapping: Mapping[str, str]) -> Dict[str, JSONValue]:
    stats: Dict[str, JSONValue] = {}
    for normalized_key, source_key in mapping.items():
        value = _normalized_scalar(source.get(source_key))
        if value is not None:
            stats[normalized_key] = value
    return stats


def _normalized_scalar(value: object) -> JSONValue:
    if value is None or isinstance(value, bool):
        return value if isinstance(value, bool) else None
    int_value = optional_int(value)
    if int_value is not None:
        return int_value
    float_value = optional_float(value)
    if float_value is not None:
        return float_value
    return optional_str(value)

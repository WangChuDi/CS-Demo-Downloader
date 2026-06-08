"""Normalized demo metadata models shared by platform downloaders."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from .utils import redact_url


JSONValue = Union[None, bool, int, float, str, List["JSONValue"], Dict[str, "JSONValue"]]
JSONObject = Dict[str, JSONValue]
METADATA_SCHEMA_VERSION = "1.1"


@dataclass
class MatchTeam:
    """Normalized team/side score information."""

    name: Optional[str] = None
    team_id: Optional[str] = None
    player_ids: List[str] = field(default_factory=list)
    side: Optional[str] = None
    first_half_side: Optional[str] = None
    second_half_side: Optional[str] = None
    score: Optional[int] = None
    origin_elo: Optional[int] = None
    change_elo: Optional[int] = None
    half_scores: Dict[str, int] = field(default_factory=dict)
    raw: JSONObject = field(default_factory=dict)

    def to_dict(self, redact_sensitive_urls: bool = False) -> JSONObject:
        return {
            "name": self.name,
            "team_id": self.team_id,
            "player_ids": list(self.player_ids),
            "side": self.side,
            "first_half_side": self.first_half_side,
            "second_half_side": self.second_half_side,
            "score": self.score,
            "origin_elo": self.origin_elo,
            "change_elo": self.change_elo,
            "half_scores": dict(self.half_scores),
            "raw": _redact_json(self.raw) if redact_sensitive_urls else dict(self.raw),
        }


@dataclass
class MatchPlayer:
    """Normalized player row with common scoreboard fields and raw stats."""

    player_id: Optional[str] = None
    steam_id: Optional[str] = None
    name: Optional[str] = None
    profile: JSONObject = field(default_factory=dict)
    team_index: Optional[int] = None
    side: Optional[str] = None
    ladder_stats: JSONObject = field(default_factory=dict)
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    rating: Optional[float] = None
    swing_score: Optional[float] = None
    adr: Optional[float] = None
    rws: Optional[float] = None
    kast: Optional[float] = None
    headshots: Optional[int] = None
    headshot_rate: Optional[float] = None
    first_kills: Optional[int] = None
    first_deaths: Optional[int] = None
    awp_kills: Optional[int] = None
    multi_kill_count: Optional[int] = None
    multi_kills: Dict[str, int] = field(default_factory=dict)
    clutch_count: Optional[int] = None
    clutches: Dict[str, int] = field(default_factory=dict)
    bomb_plants: Optional[int] = None
    bomb_defuses: Optional[int] = None
    side_stats: JSONObject = field(default_factory=dict)
    utility_stats: JSONObject = field(default_factory=dict)
    impact_stats: JSONObject = field(default_factory=dict)
    award_flags: JSONObject = field(default_factory=dict)
    platform_stats: JSONObject = field(default_factory=dict)
    raw: JSONObject = field(default_factory=dict)

    def to_dict(self, redact_sensitive_urls: bool = False) -> JSONObject:
        return {
            "player_id": self.player_id,
            "steam_id": self.steam_id,
            "name": self.name,
            "profile": _redact_json(self.profile) if redact_sensitive_urls else dict(self.profile),
            "team_index": self.team_index,
            "side": self.side,
            "ladder_stats": dict(self.ladder_stats),
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "rating": self.rating,
            "swing_score": self.swing_score,
            "adr": self.adr,
            "rws": self.rws,
            "kast": self.kast,
            "headshots": self.headshots,
            "headshot_rate": self.headshot_rate,
            "first_kills": self.first_kills,
            "first_deaths": self.first_deaths,
            "awp_kills": self.awp_kills,
            "multi_kill_count": self.multi_kill_count,
            "multi_kills": dict(self.multi_kills),
            "clutch_count": self.clutch_count,
            "clutches": dict(self.clutches),
            "bomb_plants": self.bomb_plants,
            "bomb_defuses": self.bomb_defuses,
            "side_stats": dict(self.side_stats),
            "utility_stats": dict(self.utility_stats),
            "impact_stats": dict(self.impact_stats),
            "award_flags": dict(self.award_flags),
            "platform_stats": _redact_json(self.platform_stats) if redact_sensitive_urls else dict(self.platform_stats),
            "raw": _redact_json(self.raw) if redact_sensitive_urls else dict(self.raw),
        }


@dataclass
class MatchMetadata:
    """Cross-platform normalized metadata for one demo/match."""

    platform: str
    match_id: str
    demo_url: Optional[str] = None
    demo_available: Optional[bool] = None
    map_name: Optional[str] = None
    map_label: Optional[str] = None
    location: Optional[str] = None
    match_winner: Optional[str] = None
    season: Optional[int] = None
    season_type: Optional[str] = None
    year: Optional[int] = None
    round_total: Optional[int] = None
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
    teams: List[MatchTeam] = field(default_factory=list)
    players: List[MatchPlayer] = field(default_factory=list)
    match_awards: JSONObject = field(default_factory=dict)
    demo_info: JSONObject = field(default_factory=dict)
    round_results: List[JSONObject] = field(default_factory=list)
    platform_match: JSONObject = field(default_factory=dict)
    raw_summary: JSONObject = field(default_factory=dict)
    raw_detail: JSONObject = field(default_factory=dict)
    schema_version: str = METADATA_SCHEMA_VERSION
    exported_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    demo: JSONObject = field(default_factory=dict)
    rounds: List[JSONObject] = field(default_factory=list)

    def __post_init__(self):
        if self.duration_seconds is None and self.started_at is not None and self.ended_at is not None:
            duration = self.ended_at - self.started_at
            if duration >= 0:
                self.duration_seconds = duration

    def to_dict(self, redact_sensitive_urls: bool = False) -> JSONObject:
        demo_url = redact_url(self.demo_url) if redact_sensitive_urls and self.demo_url else self.demo_url
        demo = _metadata_demo_payload(self, demo_url, redact_sensitive_urls)
        return {
            "schema_version": self.schema_version,
            "exported_at": self.exported_at,
            "platform": self.platform,
            "match_id": self.match_id,
            "demo_url": demo_url,
            "demo_available": self.demo_available,
            "demo": demo,
            "map_name": self.map_name,
            "map_label": self.map_label,
            "location": self.location,
            "match_winner": self.match_winner,
            "season": self.season,
            "season_type": self.season_type,
            "year": self.year,
            "round_total": self.round_total,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "teams": [team.to_dict(redact_sensitive_urls) for team in self.teams],
            "players": [player.to_dict(redact_sensitive_urls) for player in self.players],
            "match_awards": dict(self.match_awards),
            "demo_info": _redact_json(self.demo_info) if redact_sensitive_urls else dict(self.demo_info),
            "round_results": [_redact_json(item) for item in self.round_results] if redact_sensitive_urls else [dict(item) for item in self.round_results],
            "rounds": [_redact_json(item) for item in self.rounds] if redact_sensitive_urls else [dict(item) for item in self.rounds],
            "platform_match": _redact_json(self.platform_match) if redact_sensitive_urls else dict(self.platform_match),
            "raw_summary": _redact_json(self.raw_summary) if redact_sensitive_urls else dict(self.raw_summary),
            "raw_detail": _redact_json(self.raw_detail) if redact_sensitive_urls else dict(self.raw_detail),
        }


def metadata_list_to_dicts(
    matches: List[MatchMetadata],
    redact_sensitive_urls: bool = False,
    include_raw: bool = True,
) -> List[JSONObject]:
    """Serialize metadata objects for API/CLI output."""
    output: List[JSONObject] = []
    exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for match in matches:
        item = match.to_dict(redact_sensitive_urls=redact_sensitive_urls)
        if item.get("exported_at") is None:
            item["exported_at"] = exported_at
        if not include_raw:
            item.pop("raw_summary", None)
            item.pop("raw_detail", None)
            teams = item.get("teams")
            if isinstance(teams, list):
                for team in teams:
                    if isinstance(team, dict):
                        team.pop("raw", None)
            players = item.get("players")
            if isinstance(players, list):
                for player in players:
                    if isinstance(player, dict):
                        player.pop("raw", None)
        output.append(item)
    return output


def _metadata_demo_payload(match: MatchMetadata, demo_url: Optional[str], redact_sensitive_urls: bool) -> JSONObject:
    demo: JSONObject = dict(match.demo)
    demo.setdefault("url", demo_url)
    demo.setdefault("available", match.demo_available)
    if match.demo_info:
        demo.setdefault("info", _redact_json(match.demo_info) if redact_sensitive_urls else dict(match.demo_info))
    if redact_sensitive_urls:
        redacted = _redact_json(demo)
        return redacted if isinstance(redacted, dict) else {}
    return demo


def json_object(value: object) -> JSONObject:
    """Return a JSON object if the value is dict-like, otherwise an empty object."""
    if not isinstance(value, dict):
        return {}
    result: JSONObject = {}
    for key, item in value.items():
        normalized = to_json_value(item)
        if normalized is not None or item is None:
            result[str(key)] = normalized
    return result


def to_json_value(value: object) -> JSONValue:
    """Best-effort conversion of decoded JSON-like Python values to JSONValue."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}
    return str(value)


def optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_int(value: object) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def optional_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _redact_json(value: JSONValue) -> JSONValue:
    if isinstance(value, str):
        if value.startswith("http://") or value.startswith("https://"):
            return redact_url(value)
        return value
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_json(item) for key, item in value.items()}
    return value

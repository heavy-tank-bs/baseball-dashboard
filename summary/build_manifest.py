from __future__ import annotations

import csv
import importlib.util
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_DIR = ROOT / "summary"
GENERATED_DIR = ROOT / "generated"
RAW_DATA_DIR = ROOT / "元データ"
MANIFEST_PATH = SUMMARY_DIR / "manifest.js"
BATTER_MANIFEST_PATH = SUMMARY_DIR / "batter_manifest.js"
PLAYER_TOTALS_PATH = SUMMARY_DIR / "player_totals.json"
BATTER_TOTALS_PATH = SUMMARY_DIR / "batter_totals.json"
PARK_FACTORS_PATH = SUMMARY_DIR / "park_factors.json"
WOBA_CONSTANTS_PATH = SUMMARY_DIR / "woba_constants.json"
GAME_DECISIONS_CACHE_PATH = SUMMARY_DIR / "game_decisions_cache.json"
GAME_BATTING_CACHE_PATH = SUMMARY_DIR / "game_batting_cache.json"
PITCHER_MANIFEST_DETAIL_SUFFIX = "-dashboard-detail.json"
DASHBOARD_SCRIPT = (
    Path.home()
    / ".codex"
    / "skills"
    / "sportsnavi-pitch-dashboard"
    / "scripts"
    / "build_dashboard.py"
)

TEAM_ORDER = [
    "巨人",
    "阪神",
    "DeNA",
    "広島",
    "ヤクルト",
    "中日",
    "ソフトバンク",
    "日本ハム",
    "ロッテ",
    "オリックス",
    "西武",
    "東北楽天",
]

TEAM_ALIASES = {
    "楽天": "東北楽天",
}

TEAM_MATCHUP_NAMES = {
    "広島東洋カープ": "広島",
    "阪神タイガース": "阪神",
    "横浜DeNAベイスターズ": "DeNA",
    "読売ジャイアンツ": "巨人",
    "東京ヤクルトスワローズ": "ヤクルト",
    "中日ドラゴンズ": "中日",
    "福岡ソフトバンクホークス": "ソフトバンク",
    "北海道日本ハムファイターズ": "日本ハム",
    "千葉ロッテマリーンズ": "ロッテ",
    "オリックス・バファローズ": "オリックス",
    "埼玉西武ライオンズ": "西武",
    "東北楽天ゴールデンイーグルス": "東北楽天",
}

TEAM_LEAGUES = {
    "巨人": "セ",
    "阪神": "セ",
    "DeNA": "セ",
    "広島": "セ",
    "ヤクルト": "セ",
    "中日": "セ",
    "ソフトバンク": "パ",
    "日本ハム": "パ",
    "ロッテ": "パ",
    "オリックス": "パ",
    "西武": "パ",
    "東北楽天": "パ",
}

SPORTSNAVI_GAME_STATS_URL = "https://baseball.yahoo.co.jp/npb/game/{game_id}/stats"
SPORTSNAVI_JINA_GAME_STATS_URL = "https://r.jina.ai/http://baseball.yahoo.co.jp/npb/game/{game_id}/stats"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
DECISION_KEY_MAP = {"勝": "wins", "敗": "losses", "S": "saves", "Ｓ": "saves", "H": "holds", "Ｈ": "holds"}
GAME_DECISION_CACHE_VERSION = 2

PAGE_PATTERN = re.compile(r"^(?P<prefix>.+)-dashboard-(?P<page>\d+)\.png$")
JSON_PATTERN = re.compile(r"^(?P<prefix>.+)-dashboard\.json$")
GAME_CONTEXT_PATTERN = re.compile(r"^sportsnavi_game_context_(?P<season>\d{4})\.json$")
RAW_PITCHER_STATS_PATTERN = re.compile(r"^(?P<season>\d{4})_投手成績\.csv$")
RAW_BATTER_STATS_PATTERN = re.compile(r"^(?P<season>\d{4})_打撃成績\.csv$")
RAW_OUT_RATE_PATTERN = re.compile(r"^アウト比率_(?P<season>\d{4})\.csv$")
PITCH_COLOR_FALLBACK = ["#0F2340", "#355C8C", "#6A89B4", "#C8A55A", "#D6C192", "#9D8B75", "#7D97B5"]
EMPTY_HEATMAP = [[0 for _ in range(5)] for _ in range(5)]
INTENTIONAL_WALK_TERMS = ("\u7533\u544a\u656c\u9060", "\u656c\u9060", "\u6545\u610f\u56db\u7403", "\u6545\u610f\u56db")
OUTCOME_META = [
    ("grounders", "ゴロ", "#0F2340"),
    ("flyballs", "フライ", "#355C8C"),
    ("swingingStrikeouts", "空三振", "#6A89B4"),
    ("lookingStrikeouts", "見三振", "#C8A55A"),
    ("sacrificeBunts", "犠打", "#D6C192"),
    ("interference", "守備妨害", "#9D8B75"),
]
WOBA_CONSTANTS_BY_YEAR = {
    # Fallback constants for years without project-specific Sports Navi weights.
    "2026": {
        "source": "https://www.fangraphs.com/tools/guts",
        "provisional": True,
        "wOBA": 0.318,
        "wOBAScale": 1.280,
        "wBB": 0.711,
        "wHBP": 0.743,
        "w1B": 0.909,
        "w2B": 1.293,
        "w3B": 1.638,
        "wHR": 2.110,
    }
}
_PROJECT_WOBA_CONSTANTS_BY_YEAR: dict[str, dict] | None = None
SOURCE_TEAM_NAME_MAP = {
    "giants": "巨人",
    "tigers": "阪神",
    "baystars": "DeNA",
    "dragons": "中日",
    "swallows": "ヤクルト",
    "carp": "広島",
    "hawks": "ソフトバンク",
    "fighters": "日本ハム",
    "marines": "ロッテ",
    "lions": "西武",
    "eagles": "東北楽天",
    "orix": "オリックス",
    "g": "巨人",
    "t": "阪神",
    "yb": "DeNA",
    "d": "中日",
    "s": "ヤクルト",
    "c": "広島",
    "h": "ソフトバンク",
    "f": "日本ハム",
    "m": "ロッテ",
    "l": "西武",
    "e": "東北楽天",
    "bs": "オリックス",
}


def load_dashboard_module():
    spec = importlib.util.spec_from_file_location("pitch_dashboard_build", DASHBOARD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DASHBOARD = load_dashboard_module()
PITCH_COLORS = list(getattr(DASHBOARD, "PITCH_COLORS", PITCH_COLOR_FALLBACK))
COUNT_BUCKETS = list(getattr(DASHBOARD, "COUNT_BUCKETS", []))
HEATMAP_WIDTH = float(getattr(DASHBOARD, "HEATMAP_WIDTH", 54.0))
HEATMAP_HEIGHT = float(getattr(DASHBOARD, "HEATMAP_HEIGHT", 63.0))
INNING_SLOTS = list(range(1, int(getattr(DASHBOARD, "MAX_SCORE_INNINGS", 12)) + 1))


def team_sort_key(team: str) -> tuple[int, str]:
    team = TEAM_ALIASES.get(team, team)
    try:
        return TEAM_ORDER.index(team), team
    except ValueError:
        return len(TEAM_ORDER), team


def normalize_team_name(team: str) -> str:
    return TEAM_ALIASES.get(team, team)


def normalize_matchup_team_name(team: str) -> str:
    normalized = (team or "").strip()
    if not normalized:
        return ""
    if normalized in TEAM_MATCHUP_NAMES:
        return TEAM_MATCHUP_NAMES[normalized]
    return normalize_team_name(normalized)


def parse_matchup_teams(matchup: str) -> tuple[str, str]:
    if "vs" not in (matchup or ""):
        return "", ""
    left, right = matchup.split("vs", 1)
    return normalize_matchup_team_name(left), normalize_matchup_team_name(right)


def site_path(path: Path) -> str:
    return f"../{path.relative_to(ROOT).as_posix()}"


def safe_load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def team_league(team: str) -> str:
    return TEAM_LEAGUES.get(normalize_team_name(team), "")


def parse_int(value) -> int:
    if value in (None, ""):
        return 0
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def parse_float(value) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_percent(value) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    if text.endswith("%"):
        text = text[:-1]
    return parse_float(text)


def innings_to_outs(value) -> int:
    if value in (None, ""):
        return 0
    text = str(value).strip()
    if not text or text == "-":
        return 0
    sign = -1 if text.startswith("-") else 1
    if sign < 0:
        text = text[1:]
    whole, dot, fraction = text.partition(".")
    outs = parse_int(whole) * 3
    if dot and fraction:
        remainder = 0
        for char in fraction:
            if char.isdigit():
                remainder = int(char)
                break
        outs += min(remainder, 2)
    return outs * sign


def outs_to_innings_notation(outs: int) -> str:
    whole, remainder = divmod(max(int(outs), 0), 3)
    return str(whole) if remainder == 0 else f"{whole}.{remainder}"


def outs_to_ip(outs: int) -> float:
    return max(int(outs), 0) / 3


def round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def normalize_source_team_name(team: str) -> str:
    normalized = str(team or "").strip()
    if not normalized:
        return ""
    mapped = SOURCE_TEAM_NAME_MAP.get(normalized.lower(), normalized)
    return normalize_team_name(mapped)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    return []


def season_from_filename(path: Path, pattern: re.Pattern[str]) -> str:
    match = pattern.match(path.name)
    return match.group("season") if match else ""


def lookup_out_rate_override(
    out_rate_index: dict[tuple[str, str, str], dict[str, float | None]],
    player_name: str,
    uniform_number: str,
    team: str,
) -> dict[str, float | None] | None:
    name = str(player_name or "").strip()
    number = str(uniform_number or "").strip()
    normalized_team = normalize_source_team_name(team)
    for key in (
        (name, number, normalized_team),
        (name, number, ""),
        (name, "", normalized_team),
        (name, "", ""),
    ):
        row = out_rate_index.get(key)
        if row:
            return row
    return None


def load_raw_pitcher_stat_rows(excluded_years: set[str]) -> list[tuple[str, dict[str, str]]]:
    if not RAW_DATA_DIR.exists():
        return []
    rows: list[tuple[str, dict[str, str]]] = []
    for path in sorted(RAW_DATA_DIR.iterdir()):
        season = season_from_filename(path, RAW_PITCHER_STATS_PATTERN)
        if not season or season in excluded_years:
            continue
        deduped: dict[tuple[str, str, str], dict[str, str]] = {}
        for row in load_csv_rows(path):
            key = (
                str(row.get("選手名") or "").strip(),
                str(row.get("背番号") or "").strip(),
                str(row.get("チーム名") or row.get("チームコード") or "").strip().lower(),
            )
            previous = deduped.get(key)
            if previous is None or parse_int(row.get("投球回_アウト数")) >= parse_int(previous.get("投球回_アウト数")):
                deduped[key] = row
        rows.extend((season, row) for row in deduped.values())
    return rows


def raw_pitcher_at_bats(row: dict[str, str]) -> int:
    explicit_at_bats = parse_int(row.get("打数") or row.get("被打数"))
    if explicit_at_bats:
        return explicit_at_bats
    batters = parse_int(row.get("打者"))
    if not batters:
        return 0
    non_at_bats = sum(
        parse_int(row.get(key))
        for key in ("与四球", "与死球", "犠打", "犠飛", "打撃妨害", "守備妨害")
    )
    return max(batters - non_at_bats, 0)


def load_raw_batter_stat_rows(excluded_years: set[str]) -> list[tuple[str, dict[str, str]]]:
    if not RAW_DATA_DIR.exists():
        return []
    rows: list[tuple[str, dict[str, str]]] = []
    for path in sorted(RAW_DATA_DIR.iterdir()):
        season = season_from_filename(path, RAW_BATTER_STATS_PATTERN)
        if not season or season in excluded_years:
            continue
        deduped: dict[tuple[str, str, str], dict[str, str]] = {}
        for row in load_csv_rows(path):
            key = (
                str(row.get("選手名") or "").strip(),
                str(row.get("背番号") or "").strip(),
                str(row.get("team") or "").strip().lower(),
            )
            previous = deduped.get(key)
            if previous is None or parse_int(row.get("打席")) >= parse_int(previous.get("打席")):
                deduped[key] = row
        rows.extend((season, row) for row in deduped.values())
    return rows


def load_raw_out_rate_index(excluded_years: set[str]) -> dict[str, dict[tuple[str, str, str], dict[str, float | None]]]:
    if not RAW_DATA_DIR.exists():
        return {}
    seasons: dict[str, dict[tuple[str, str, str], dict[str, float | None]]] = {}
    for path in sorted(RAW_DATA_DIR.iterdir()):
        season = season_from_filename(path, RAW_OUT_RATE_PATTERN)
        if not season or season in excluded_years:
            continue
        season_rows: dict[tuple[str, str, str], dict[str, float | None]] = {}
        for row in load_csv_rows(path):
            player_name = str(row.get("選手名") or "").strip()
            uniform_number = str(row.get("背番号") or "").strip()
            team = normalize_source_team_name(row.get("チームコード") or "")
            if not player_name:
                continue
            season_rows[(player_name, uniform_number, team)] = {
                "groundOutRate": parse_percent(row.get(f"{season}ゴロアウト率")),
                "flyOutRate": parse_percent(row.get(f"{season}フライアウト率")),
            }
        if season_rows:
            seasons[season] = season_rows
    return seasons


def get_woba_constants(year: str) -> dict | None:
    project_constants = load_project_woba_constants_by_year()
    if year in project_constants:
        constants = dict(project_constants[year])
        constants["constantsYear"] = constants.get("constantsYear") or year
        return constants
    if not WOBA_CONSTANTS_BY_YEAR:
        return None
    selected_year = year if year in WOBA_CONSTANTS_BY_YEAR else max(WOBA_CONSTANTS_BY_YEAR)
    constants = dict(WOBA_CONSTANTS_BY_YEAR[selected_year])
    constants["constantsYear"] = selected_year
    return constants


def load_project_woba_constants_by_year() -> dict[str, dict]:
    global _PROJECT_WOBA_CONSTANTS_BY_YEAR
    if _PROJECT_WOBA_CONSTANTS_BY_YEAR is not None:
        return _PROJECT_WOBA_CONSTANTS_BY_YEAR
    payload = safe_load_json(WOBA_CONSTANTS_PATH) if WOBA_CONSTANTS_PATH.exists() else None
    by_year = payload.get("byYear") if isinstance(payload, dict) else None
    constants_by_year: dict[str, dict] = {}
    if isinstance(by_year, dict):
        for year, constants in by_year.items():
            if isinstance(constants, dict):
                constants_by_year[str(year)] = dict(constants)
    _PROJECT_WOBA_CONSTANTS_BY_YEAR = constants_by_year
    return constants_by_year


def calculate_woba(stats: dict, constants: dict | None) -> float | None:
    if not constants:
        return None
    denominator = (
        parse_int(stats.get("atBats"))
        + parse_int(stats.get("unintentionalWalks"))
        + parse_int(stats.get("hitByPitch"))
        + parse_int(stats.get("sacFlies"))
    )
    if denominator <= 0:
        return None
    numerator = (
        constants["wBB"] * parse_int(stats.get("unintentionalWalks"))
        + constants["wHBP"] * parse_int(stats.get("hitByPitch"))
        + constants["w1B"] * parse_int(stats.get("singles"))
        + constants["w2B"] * parse_int(stats.get("doubles"))
        + constants["w3B"] * parse_int(stats.get("triples"))
        + constants["wHR"] * parse_int(stats.get("homeRuns"))
    )
    return numerator / denominator


def build_park_factor_index(park_factors: dict) -> dict[str, dict[str, dict]]:
    by_season = park_factors.get("bySeason") or {}
    index: dict[str, dict[str, dict]] = {}
    for season, payload in by_season.items():
        team_rows = payload.get("teams") or []
        season_index = {
            normalize_team_name(row.get("team") or ""): row
            for row in team_rows
            if normalize_team_name(row.get("team") or "")
        }
        if season_index:
            index[season] = season_index
    return index


def weighted_park_factor(
    plate_appearances_by_team: dict[str, int],
    park_factor_rows: dict[str, dict],
) -> tuple[float | None, float | None]:
    total_pa = 0
    weighted_raw_factor = 0.0

    for team, plate_appearances in plate_appearances_by_team.items():
        pa = max(parse_int(plate_appearances), 0)
        if pa <= 0:
            continue
        team_row = park_factor_rows.get(normalize_team_name(team)) or {}
        raw_factor = team_row.get("homeParkFactor")
        if raw_factor in (None, ""):
            raw_factor = 100.0
        weighted_raw_factor += float(raw_factor) * pa
        total_pa += pa

    if total_pa <= 0:
        return None, None

    raw_factor = weighted_raw_factor / total_pa
    effective_factor = 100.0 + ((raw_factor - 100.0) / 2.0)
    return raw_factor, effective_factor


def month_key_from_date(value: str | None) -> str:
    text_value = str(value or "").strip()
    if re.match(r"^\d{4}-\d{2}", text_value):
        return text_value[:7]
    return ""


def month_label(month_key: str) -> str:
    parts = str(month_key or "").split("-", 1)
    month_number = parse_int(parts[1]) if len(parts) == 2 else 0
    return f"{month_number}月" if month_number else str(month_key or "-")


def build_pitcher_monthly_splits(
    entries: list[dict],
    game_decisions: dict[str, dict],
    game_contexts: dict[str, dict] | None = None,
) -> dict[tuple[str, str], list[dict]]:
    league_totals: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "outs": 0,
            "earnedRuns": 0,
            "homeRuns": 0,
            "unintentionalWalks": 0,
            "hitByPitch": 0,
            "strikeouts": 0,
        }
    )
    players: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    game_contexts = game_contexts or {}
    context_game_ids = context_intentional_walk_game_ids(game_contexts)
    context_intentional_walks_by_entry = build_pitcher_context_intentional_walks(entries, game_contexts)

    def empty_bucket(entry: dict, year: str, month: str, pitcher_key: str, league: str) -> dict:
        return {
            "year": year,
            "month": month,
            "monthLabel": month_label(month),
            "_bucketKey": pitcher_key,
            "pitcherId": entry.get("pitcherId") or "",
            "player": entry.get("player", ""),
            "league": league,
            "teams": set(),
            "games": 0,
            "wins": 0,
            "losses": 0,
            "saves": 0,
            "holds": 0,
            "outs": 0,
            "batters": 0,
            "pitches": 0,
            "hits": 0,
            "homeRuns": 0,
            "strikeouts": 0,
            "walks": 0,
            "unintentionalWalks": 0,
            "intentionalWalks": 0,
            "hitByPitch": 0,
            "balks": 0,
            "runs": 0,
            "earnedRuns": 0,
            "atBats": 0,
            "singles": 0,
            "doubles": 0,
            "triples": 0,
            "grounders": 0,
            "flyBalls": 0,
            "swingMisses": 0,
            "lookingStrikeouts": 0,
            "swingingStrikeouts": 0,
            "sacrificeBunts": 0,
            "sacrificeFlies": 0,
            "interference": 0,
            "hasPitchCount": False,
        }

    def finalize_bucket(bucket: dict, fip_constant: float | None) -> dict:
        outs = bucket["outs"]
        ip = outs_to_ip(outs)
        teams = sorted(bucket["teams"], key=team_sort_key)
        at_bats = bucket["atBats"]
        batting_average = bucket["hits"] / at_bats if at_bats else None
        babip_denominator = bucket["atBats"] - bucket["strikeouts"] - bucket["homeRuns"] + bucket["sacrificeFlies"]
        babip_allowed = ((bucket["hits"] - bucket["homeRuns"]) / babip_denominator) if babip_denominator > 0 else None
        era = 9 * bucket["earnedRuns"] / ip if ip else None
        whip = (bucket["hits"] + bucket["walks"]) / ip if ip else None
        k_per_9 = 27 * bucket["strikeouts"] / outs if outs else None
        bb_per_9 = 27 * bucket["walks"] / outs if outs else None
        h_per_9 = 27 * bucket["hits"] / outs if outs else None
        hr_per_9 = 27 * bucket["homeRuns"] / outs if outs else None
        k_bb = bucket["strikeouts"] / bucket["walks"] if bucket["walks"] else None
        go_fo = bucket["grounders"] / bucket["flyBalls"] if bucket["flyBalls"] else None
        out_event_total = (
            bucket["grounders"]
            + bucket["flyBalls"]
            + bucket["lookingStrikeouts"]
            + bucket["swingingStrikeouts"]
            + bucket["sacrificeBunts"]
            + bucket["interference"]
        )
        ground_out_rate = bucket["grounders"] / out_event_total * 100 if out_event_total else None
        fly_out_rate = bucket["flyBalls"] / out_event_total * 100 if out_event_total else None
        if go_fo is None and ground_out_rate is not None and fly_out_rate not in (None, 0):
            go_fo = ground_out_rate / fly_out_rate
        whiff_rate = bucket["swingMisses"] / bucket["pitches"] * 100 if bucket["hasPitchCount"] and bucket["pitches"] else None
        fip = (
            (((13 * bucket["homeRuns"]) + (3 * (bucket["unintentionalWalks"] + bucket["hitByPitch"])) - (2 * bucket["strikeouts"])) / ip) + fip_constant
            if ip and fip_constant is not None
            else None
        )
        return {
            "year": bucket["year"],
            "month": bucket["month"],
            "monthLabel": bucket["monthLabel"],
            "pitcherId": bucket["pitcherId"],
            "player": bucket["player"],
            "team": teams[0] if len(teams) == 1 else " / ".join(teams),
            "teams": teams,
            "league": bucket["league"],
            "games": bucket["games"],
            "wins": bucket["wins"],
            "losses": bucket["losses"],
            "saves": bucket["saves"],
            "holds": bucket["holds"],
            "innings": outs_to_innings_notation(outs),
            "inningsOuts": outs,
            "batters": bucket["batters"],
            "pitches": bucket["pitches"] if bucket["hasPitchCount"] else None,
            "hasPitchCount": bool(bucket["hasPitchCount"]),
            "hits": bucket["hits"],
            "homeRuns": bucket["homeRuns"],
            "strikeouts": bucket["strikeouts"],
            "walks": bucket["walks"],
            "unintentionalWalks": bucket["unintentionalWalks"],
            "intentionalWalks": bucket["intentionalWalks"],
            "hitByPitch": bucket["hitByPitch"],
            "balks": bucket["balks"],
            "runs": bucket["runs"],
            "earnedRuns": bucket["earnedRuns"],
            "atBats": bucket["atBats"],
            "singles": bucket["singles"],
            "doubles": bucket["doubles"],
            "triples": bucket["triples"],
            "grounders": bucket["grounders"],
            "flyBalls": bucket["flyBalls"],
            "swingMisses": bucket["swingMisses"],
            "lookingStrikeouts": bucket["lookingStrikeouts"],
            "swingingStrikeouts": bucket["swingingStrikeouts"],
            "sacrificeBunts": bucket["sacrificeBunts"],
            "sacrificeFlies": bucket["sacrificeFlies"],
            "interference": bucket["interference"],
            "era": round_or_none(era, 2),
            "whip": round_or_none(whip, 2),
            "kPer9": round_or_none(k_per_9, 2),
            "bbPer9": round_or_none(bb_per_9, 2),
            "hPer9": round_or_none(h_per_9, 2),
            "hrPer9": round_or_none(hr_per_9, 2),
            "kBb": round_or_none(k_bb, 2),
            "fip": round_or_none(fip, 2),
            "fipConstant": round_or_none(fip_constant, 4),
            "battingAverageAllowed": round_or_none(batting_average, 3),
            "babipAllowed": round_or_none(babip_allowed, 3),
            "goFo": round_or_none(go_fo, 2),
            "groundOutRate": round_or_none(ground_out_rate, 1),
            "flyOutRate": round_or_none(fly_out_rate, 1),
            "whiffRate": round_or_none(whiff_rate, 1),
        }

    for entry in entries:
        date = entry.get("date") or ""
        year = str(date)[:4] or "unknown"
        month = month_key_from_date(date)
        if not month:
            continue
        statline = entry.get("statline") or {}
        dashboard = entry.get("dashboard") or {}
        league = entry.get("league") or team_league(entry.get("team", ""))
        pitcher_key = entry.get("pitcherId") or f"{entry.get('team', '')}::{entry.get('player', '')}"
        outs = innings_to_outs(statline.get("innings"))
        pitch_rows = dashboard.get("pitchMix") or []
        outcome_rows = {row.get("id"): parse_int(row.get("count")) for row in (dashboard.get("outcomes", {}).get("rows") or [])}
        if str(entry.get("gameId") or "") in context_game_ids:
            intentional_walks = max(parse_int(context_intentional_walks_by_entry.get(entry["id"])), 0)
        else:
            intentional_walks = max(parse_int(dashboard.get("intentionalWalks")), 0)
        sacrifice_flies = max(parse_int(dashboard.get("sacrificeFlies")), 0)
        unintentional_walks = max(parse_int(statline.get("bb")) - intentional_walks, 0)

        league_bucket = league_totals[(year, league)]
        league_bucket["outs"] += outs
        league_bucket["earnedRuns"] += parse_int(statline.get("er"))
        league_bucket["homeRuns"] += parse_int(statline.get("hr"))
        league_bucket["unintentionalWalks"] += unintentional_walks
        league_bucket["hitByPitch"] += parse_int(statline.get("hbp"))
        league_bucket["strikeouts"] += parse_int(statline.get("k"))

        month_bucket = players[(year, pitcher_key)].setdefault(month, empty_bucket(entry, year, month, pitcher_key, league))
        if entry.get("team"):
            month_bucket["teams"].add(entry["team"])
        decision_row = resolve_game_decision(entry, game_decisions)
        month_bucket["games"] += 1
        month_bucket["wins"] += parse_int(decision_row.get("wins"))
        month_bucket["losses"] += parse_int(decision_row.get("losses"))
        month_bucket["saves"] += parse_int(decision_row.get("saves"))
        month_bucket["holds"] += parse_int(decision_row.get("holds"))
        month_bucket["outs"] += outs
        month_bucket["batters"] += parse_int(statline.get("batters"))
        pitch_count = parse_int(statline.get("pitches"))
        month_bucket["pitches"] += pitch_count
        month_bucket["hasPitchCount"] = month_bucket["hasPitchCount"] or pitch_count > 0
        month_bucket["hits"] += parse_int(statline.get("hits"))
        month_bucket["homeRuns"] += parse_int(statline.get("hr"))
        month_bucket["strikeouts"] += parse_int(statline.get("k"))
        month_bucket["walks"] += parse_int(statline.get("bb"))
        month_bucket["unintentionalWalks"] += unintentional_walks
        month_bucket["intentionalWalks"] += intentional_walks
        month_bucket["hitByPitch"] += parse_int(statline.get("hbp"))
        month_bucket["balks"] += parse_int(statline.get("balk"))
        month_bucket["runs"] += parse_int(statline.get("runs"))
        month_bucket["earnedRuns"] += parse_int(statline.get("er"))
        month_bucket["atBats"] += sum(parse_int(row.get("atBats")) for row in pitch_rows)
        month_bucket["singles"] += sum(parse_int(row.get("singles")) for row in pitch_rows)
        month_bucket["doubles"] += sum(parse_int(row.get("doubles")) for row in pitch_rows)
        month_bucket["triples"] += sum(parse_int(row.get("triples")) for row in pitch_rows)
        month_bucket["grounders"] += sum(parse_int(row.get("grounders")) for row in pitch_rows)
        month_bucket["flyBalls"] += sum(parse_int(row.get("flyBalls")) for row in pitch_rows)
        month_bucket["swingMisses"] += sum(parse_int(row.get("whiffCount")) for row in pitch_rows)
        month_bucket["lookingStrikeouts"] += outcome_rows.get("lookingStrikeouts", 0)
        month_bucket["swingingStrikeouts"] += outcome_rows.get("swingingStrikeouts", 0)
        month_bucket["sacrificeBunts"] += outcome_rows.get("sacrificeBunts", 0)
        month_bucket["sacrificeFlies"] += sacrifice_flies
        month_bucket["interference"] += outcome_rows.get("interference", 0)

    league_constants: dict[tuple[str, str], float | None] = {}
    for (year, league), stats in league_totals.items():
        ip = outs_to_ip(stats["outs"])
        era = 9 * stats["earnedRuns"] / ip if ip else None
        component = (
            ((13 * stats["homeRuns"]) + (3 * (stats["unintentionalWalks"] + stats["hitByPitch"])) - (2 * stats["strikeouts"])) / ip
            if ip
            else None
        )
        league_constants[(year, league)] = (era - component) if era is not None and component is not None else None

    monthly_rows: dict[tuple[str, str], list[dict]] = {}
    for key, month_buckets in players.items():
        rows = []
        for month in sorted(month_buckets):
            bucket = month_buckets[month]
            rows.append(finalize_bucket(bucket, league_constants.get((bucket["year"], bucket["league"]))))
        monthly_rows[key] = rows
    return monthly_rows


def build_batter_monthly_splits(
    entries: list[dict],
    batting_stats_by_game: dict[str, dict[str, dict]],
    batter_entries: list[dict],
    park_factors: dict,
    game_contexts: dict[str, dict] | None = None,
) -> dict[tuple[str, str], list[dict]]:
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: True)
    classify_plate_appearance_result = getattr(DASHBOARD, "classify_plate_appearance_result", lambda value: None)
    game_dates: dict[str, str] = {}
    players: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    sacrifice_flies_by_player: dict[tuple[str, str, str], int] = defaultdict(int)
    intentional_walks_by_player: dict[tuple[str, str, str], int] = defaultdict(int)
    scoring_position_by_player: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"atBats": 0, "hits": 0})
    game_contexts = game_contexts or {}
    context_game_ids = context_intentional_walk_game_ids(game_contexts)

    def empty_bucket(year: str, month: str, team: str, league: str, batter_id: str, player_name: str, bucket_key: str) -> dict:
        return {
            "year": year,
            "month": month,
            "monthLabel": month_label(month),
            "batterId": batter_id,
            "player": player_name,
            "_bucketKey": bucket_key,
            "teams": set([team] if team else []),
            "league": league,
            "games": 0,
            "plateAppearances": 0,
            "atBats": 0,
            "runs": 0,
            "hits": 0,
            "singles": 0,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "runsBattedIn": 0,
            "walks": 0,
            "unintentionalWalks": 0,
            "intentionalWalks": 0,
            "hitByPitch": 0,
            "sacBunts": 0,
            "sacFlies": 0,
            "steals": 0,
            "strikeouts": 0,
            "scoringPositionAtBats": 0,
            "scoringPositionHits": 0,
            "_plateAppearancesByTeam": {},
        }

    def finalize_bucket(bucket: dict, park_factor_index: dict[str, dict], league_contexts: dict[tuple[str, str, str], dict]) -> dict:
        teams = sorted(bucket["teams"], key=team_sort_key)
        total_bases = bucket["singles"] + bucket["doubles"] * 2 + bucket["triples"] * 3 + bucket["homeRuns"] * 4
        batting_average = bucket["hits"] / bucket["atBats"] if bucket["atBats"] else None
        on_base_denominator = bucket["atBats"] + bucket["walks"] + bucket["hitByPitch"] + bucket["sacFlies"]
        on_base_percentage = (
            (bucket["hits"] + bucket["walks"] + bucket["hitByPitch"]) / on_base_denominator
            if on_base_denominator > 0
            else None
        )
        slugging = total_bases / bucket["atBats"] if bucket["atBats"] else None
        iso_discipline = (on_base_percentage - batting_average) if on_base_percentage is not None and batting_average is not None else None
        iso_power = (slugging - batting_average) if slugging is not None and batting_average is not None else None
        ops = (on_base_percentage + slugging) if on_base_percentage is not None and slugging is not None else None
        babip_denominator = bucket["atBats"] - bucket["strikeouts"] - bucket["homeRuns"] + bucket["sacFlies"]
        babip = ((bucket["hits"] - bucket["homeRuns"]) / babip_denominator) if babip_denominator > 0 else None
        scoring_position_batting_average = (
            bucket["scoringPositionHits"] / bucket["scoringPositionAtBats"]
            if bucket["scoringPositionAtBats"]
            else None
        )
        constants = get_woba_constants(bucket["year"])
        league_context = league_contexts.get((bucket["year"], bucket["league"], bucket["month"])) or {}
        player_woba = calculate_woba(bucket, constants)
        raw_park_factor, effective_park_factor = weighted_park_factor(
            bucket["_plateAppearancesByTeam"],
            park_factor_index.get(bucket["year"], {}),
        )
        league_woba = league_context.get("woba")
        league_runs_per_pa = league_context.get("runsPerPlateAppearance")
        woba_scale = league_context.get("wobaScale") or (constants.get("wOBAScale") if constants else None)
        runs_above_average_per_pa = (
            (player_woba - league_woba) / woba_scale
            if player_woba is not None and league_woba is not None and woba_scale not in (None, 0)
            else None
        )
        wrc = (
            ((runs_above_average_per_pa + league_runs_per_pa) * bucket["plateAppearances"])
            if runs_above_average_per_pa is not None and league_runs_per_pa is not None and bucket["plateAppearances"] > 0
            else None
        )
        park_adjustment = (
            league_runs_per_pa - ((effective_park_factor / 100.0) * league_runs_per_pa)
            if league_runs_per_pa is not None and effective_park_factor is not None
            else None
        )
        wrc_plus = (
            ((((runs_above_average_per_pa + league_runs_per_pa) + park_adjustment) / league_runs_per_pa) * 100)
            if runs_above_average_per_pa is not None
            and league_runs_per_pa not in (None, 0)
            and park_adjustment is not None
            else None
        )
        return {
            "year": bucket["year"],
            "month": bucket["month"],
            "monthLabel": bucket["monthLabel"],
            "batterId": bucket["batterId"],
            "player": bucket["player"],
            "team": teams[0] if len(teams) == 1 else " / ".join(teams),
            "teams": teams,
            "league": bucket["league"],
            "games": bucket["games"],
            "plateAppearances": bucket["plateAppearances"],
            "atBats": bucket["atBats"],
            "runs": bucket["runs"],
            "hits": bucket["hits"],
            "singles": bucket["singles"],
            "doubles": bucket["doubles"],
            "triples": bucket["triples"],
            "homeRuns": bucket["homeRuns"],
            "runsBattedIn": bucket["runsBattedIn"],
            "walks": bucket["walks"],
            "unintentionalWalks": bucket["unintentionalWalks"],
            "intentionalWalks": bucket["intentionalWalks"],
            "hitByPitch": bucket["hitByPitch"],
            "sacBunts": bucket["sacBunts"],
            "sacFlies": bucket["sacFlies"],
            "steals": bucket["steals"],
            "strikeouts": bucket["strikeouts"],
            "scoringPositionAtBats": bucket["scoringPositionAtBats"],
            "scoringPositionHits": bucket["scoringPositionHits"],
            "battingAverage": round_or_none(batting_average, 3),
            "scoringPositionBattingAverage": round_or_none(scoring_position_batting_average, 3),
            "onBasePercentage": round_or_none(on_base_percentage, 3),
            "isoDiscipline": round_or_none(iso_discipline, 3),
            "sluggingPercentage": round_or_none(slugging, 3),
            "isoPower": round_or_none(iso_power, 3),
            "babip": round_or_none(babip, 3),
            "ops": round_or_none(ops, 3),
            "wrc": round_or_none(wrc, 1),
            "wrcPlus": round_or_none(wrc_plus, 1),
            "parkFactor": round_or_none(raw_park_factor, 1),
            "effectiveParkFactor": round_or_none(effective_park_factor, 1),
        }

    for entry in entries:
        game_id = entry.get("gameId") or ""
        date = entry.get("date") or ""
        if game_id and date:
            game_dates.setdefault(game_id, date)

    for entry in batter_entries:
        date = entry.get("date") or ""
        year = str(date)[:4]
        month = month_key_from_date(date)
        if not year or not month:
            continue
        team = entry.get("team") or ""
        batter_id = entry.get("batterId") or ""
        player_name = entry.get("player") or ""
        bucket_key = batter_id or f"{team}::{player_name}"
        plate_rows = ((entry.get("dashboard") or {}).get("plateAppearances") or [])
        sacrifice_flies_by_player[(year, bucket_key, month)] += sum(
            1
            for plate in plate_rows
            if (plate.get("result") or "")
            and not is_ab_result(plate.get("result") or "")
            and classify_plate_appearance_result(plate.get("result") or "") == "flyballs"
        )
        if str(entry.get("gameId") or "") not in context_game_ids:
            intentional_walks_by_player[(year, bucket_key, month)] += sum(
                1 for plate in plate_rows if is_intentional_walk_text(plate.get("result"))
            )
        scoring_position_stats = build_scoring_position_statline(plate_rows)
        scoring_position_bucket = scoring_position_by_player[(year, bucket_key, month)]
        scoring_position_bucket["atBats"] += scoring_position_stats["atBats"]
        scoring_position_bucket["hits"] += scoring_position_stats["hits"]

    add_context_batter_intentional_walks(intentional_walks_by_player, game_contexts, monthly=True)

    for game_id, teams in batting_stats_by_game.items():
        date = game_dates.get(game_id, "")
        year = date[:4]
        month = month_key_from_date(date)
        if not year or not month:
            continue
        for team, rows in teams.items():
            league = team_league(team)
            for key, stats in rows.items():
                if key != (stats.get("playerId") or stats.get("player")):
                    continue
                batter_id = stats.get("playerId") or ""
                player_name = stats.get("player") or ""
                player_key = batter_id or f"{team}::{player_name}"
                bucket = players[(year, player_key)].setdefault(
                    month,
                    empty_bucket(year, month, team, league, batter_id, player_name, player_key),
                )
                bucket["teams"].add(team)
                bucket["games"] += 1
                bucket["plateAppearances"] += parse_int(stats.get("plateAppearances"))
                bucket["atBats"] += parse_int(stats.get("ab"))
                bucket["runs"] += parse_int(stats.get("runs"))
                bucket["hits"] += parse_int(stats.get("hits"))
                bucket["singles"] += parse_int(stats.get("singles"))
                bucket["doubles"] += parse_int(stats.get("doubles"))
                bucket["triples"] += parse_int(stats.get("triples"))
                bucket["homeRuns"] += parse_int(stats.get("homeRuns"))
                bucket["runsBattedIn"] += parse_int(stats.get("rbi"))
                bucket["walks"] += parse_int(stats.get("walks"))
                bucket["hitByPitch"] += parse_int(stats.get("hitByPitch"))
                bucket["sacBunts"] += parse_int(stats.get("sacBunts"))
                bucket["steals"] += parse_int(stats.get("steals"))
                bucket["strikeouts"] += parse_int(stats.get("strikeouts"))
                bucket["_plateAppearancesByTeam"][team] = (
                    bucket["_plateAppearancesByTeam"].get(team, 0) + parse_int(stats.get("plateAppearances"))
                )

    finalized_buckets: list[dict] = []
    for year_and_key, month_buckets in players.items():
        year, player_key = year_and_key
        for month, bucket in month_buckets.items():
            bucket["teams"] = sorted(bucket["teams"], key=team_sort_key)
            bucket["sacFlies"] = sacrifice_flies_by_player.get((year, player_key, month), 0)
            bucket["intentionalWalks"] = intentional_walks_by_player.get((year, player_key, month), 0)
            bucket["unintentionalWalks"] = max(bucket["walks"] - bucket["intentionalWalks"], 0)
            scoring_position_stats = scoring_position_by_player.get((year, player_key, month), {})
            bucket["scoringPositionAtBats"] = parse_int(scoring_position_stats.get("atBats"))
            bucket["scoringPositionHits"] = parse_int(scoring_position_stats.get("hits"))
            finalized_buckets.append(bucket)

    league_buckets: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {
            "plateAppearances": 0,
            "runs": 0,
            "atBats": 0,
            "singles": 0,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "unintentionalWalks": 0,
            "hitByPitch": 0,
            "sacFlies": 0,
        }
    )
    for bucket in finalized_buckets:
        league_key = (bucket["year"], bucket["league"], bucket["month"])
        league_bucket = league_buckets[league_key]
        league_bucket["plateAppearances"] += bucket["plateAppearances"]
        league_bucket["runs"] += bucket["runs"]
        league_bucket["atBats"] += bucket["atBats"]
        league_bucket["singles"] += bucket["singles"]
        league_bucket["doubles"] += bucket["doubles"]
        league_bucket["triples"] += bucket["triples"]
        league_bucket["homeRuns"] += bucket["homeRuns"]
        league_bucket["unintentionalWalks"] += bucket["unintentionalWalks"]
        league_bucket["hitByPitch"] += bucket["hitByPitch"]
        league_bucket["sacFlies"] += bucket["sacFlies"]

    league_contexts: dict[tuple[str, str, str], dict] = {}
    for (year, league, month), stats in league_buckets.items():
        constants = get_woba_constants(year)
        league_contexts[(year, league, month)] = {
            "woba": calculate_woba(stats, constants),
            "runsPerPlateAppearance": (stats["runs"] / stats["plateAppearances"]) if stats["plateAppearances"] else None,
            "wobaScale": constants.get("wOBAScale") if constants else None,
        }

    park_factor_index = build_park_factor_index(park_factors)
    monthly_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for bucket in sorted(finalized_buckets, key=lambda item: (item["year"], item["month"], team_sort_key(item["teams"][0] if item["teams"] else ""), item["player"])):
        key = (bucket["year"], bucket["_bucketKey"])
        monthly_rows[key].append(finalize_bucket(bucket, park_factor_index, league_contexts))

    return dict(monthly_rows)


def is_intentional_walk_text(value: str | None) -> bool:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda raw: (raw or "").split("[", 1)[0].strip())
    normalized = normalize_result(value or "")
    return any(term in normalized for term in INTENTIONAL_WALK_TERMS)


def text(node) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True).replace("\xa0", " ")


def extract_game_id(prefix: str) -> str:
    head = str(prefix or "").split("-", 1)[0]
    return head if head.isdigit() else ""


def pa_index_sort_key(value) -> tuple[int, str]:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text), text
    return 10**9, text


def pitcher_appearance_order(payload: dict | None) -> int:
    pitches = (payload or {}).get("pitches") or []
    order, _ = min((pa_index_sort_key(row.get("pa_index")) for row in pitches), default=(10**9, ""))
    return order


def load_game_decisions_cache() -> dict:
    if not GAME_DECISIONS_CACHE_PATH.exists():
        return {"games": {}}
    try:
        data = json.loads(GAME_DECISIONS_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"games": {}}
    if not isinstance(data, dict):
        return {"games": {}}
    games = data.get("games")
    if not isinstance(games, dict):
        return {"games": {}}
    return data


def load_game_batting_cache() -> dict:
    if not GAME_BATTING_CACHE_PATH.exists():
        return {"games": {}}
    try:
        data = json.loads(GAME_BATTING_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"games": {}}
    if not isinstance(data, dict):
        return {"games": {}}
    games = data.get("games")
    if not isinstance(games, dict):
        return {"games": {}}
    return data


def save_game_decisions_cache(cache: dict) -> None:
    cache["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    GAME_DECISIONS_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_game_batting_cache(cache: dict) -> None:
    cache["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    GAME_BATTING_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_empty_decision_bucket(player_id: str, player_name: str) -> dict:
    return {
        "pitcherId": player_id,
        "player": player_name,
        "wins": 0,
        "losses": 0,
        "saves": 0,
        "holds": 0,
    }


def parse_game_decisions_from_html(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    decisions: dict[str, dict] = {}
    for row in soup.select("table.bb-scoreTable tr"):
        cells = row.select("th,td")
        if len(cells) < 2:
            continue
        marker = text(cells[0])
        decision_key = DECISION_KEY_MAP.get(marker)
        if not decision_key:
            continue
        player_link = cells[1].select_one("a[href*='/npb/player/']")
        player_name = text(player_link) or text(cells[1])
        href = player_link.get("href", "") if player_link else ""
        match = re.search(r"/npb/player/(\d+)/top", href)
        player_id = match.group(1) if match else ""
        key = player_id or player_name
        bucket = decisions.setdefault(key, build_empty_decision_bucket(player_id, player_name))
        bucket[decision_key] += 1
    return decisions


def parse_game_decisions_from_jina(text_body: str) -> dict[str, dict]:
    decisions: dict[str, dict] = {}
    pattern = re.compile(r"^\|\s*(勝|敗|S|Ｓ|H|Ｈ)\s*\|\s*\[([^\]]+)\]\(https://baseball\.yahoo\.co\.jp/npb/player/(\d+)/top\)")
    for line in text_body.splitlines():
        match = pattern.search(line.strip())
        if not match:
            continue
        marker, player_name, player_id = match.groups()
        decision_key = DECISION_KEY_MAP.get(marker)
        if not decision_key:
            continue
        key = player_id or player_name
        bucket = decisions.setdefault(key, build_empty_decision_bucket(player_id, player_name))
        bucket[decision_key] += 1
    return decisions


def fetch_game_decisions(session: requests.Session, game_id: str) -> dict[str, dict]:
    url = SPORTSNAVI_GAME_STATS_URL.format(game_id=game_id)
    resp = session.get(url, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    decisions = parse_game_decisions_from_html(resp.text)
    if decisions:
        return decisions

    jina_resp = session.get(SPORTSNAVI_JINA_GAME_STATS_URL.format(game_id=game_id), timeout=30)
    jina_resp.raise_for_status()
    return parse_game_decisions_from_jina(jina_resp.text)


def load_or_update_game_decisions(entries: list[dict]) -> dict[str, dict]:
    cache = load_game_decisions_cache()
    games = cache.setdefault("games", {})
    target_ids = sorted({entry.get("gameId") for entry in entries if entry.get("gameId")})
    cache_stale = cache.get("decisionParserVersion") != GAME_DECISION_CACHE_VERSION
    missing_ids = [
        game_id
        for game_id in target_ids
        if cache_stale or game_id not in games or not isinstance(games.get(game_id), dict) or not games.get(game_id)
    ]
    if missing_ids:
        session = requests.Session()
        for game_id in missing_ids:
            try:
                games[game_id] = fetch_game_decisions(session, game_id)
            except Exception as exc:
                print(f"warning: failed to fetch game decisions for {game_id}: {exc}")
                games[game_id] = {}
        cache["decisionParserVersion"] = GAME_DECISION_CACHE_VERSION
        save_game_decisions_cache(cache)
    return games


def load_or_update_game_batting_stats(entries: list[dict]) -> dict[str, dict[str, dict]]:
    cache = load_game_batting_cache()
    games = cache.setdefault("games", {})
    target_ids = sorted({entry.get("gameId") for entry in entries if entry.get("gameId")})
    missing_ids = []
    for game_id in target_ids:
        cached = games.get(game_id)
        if not isinstance(cached, dict) or not cached:
            missing_ids.append(game_id)
            continue
        sample_team = next(iter(cached.values()), None)
        sample_row = next(iter(sample_team.values()), None) if isinstance(sample_team, dict) and sample_team else None
        if not isinstance(sample_row, dict) or "plateAppearances" not in sample_row:
            missing_ids.append(game_id)
    if missing_ids:
        session = requests.Session()
        for game_id in missing_ids:
            try:
                games[game_id] = fetch_game_batting_stats(session, game_id)
            except Exception as exc:
                print(f"warning: failed to fetch batting stats for {game_id}: {exc}")
                games[game_id] = {}
        save_game_batting_cache(cache)
    return games


def parse_game_batting_stats_from_html(html: str) -> dict[str, dict[str, dict]]:
    soup = BeautifulSoup(html, "html.parser")
    batting_tables = soup.select("table.bb-statsTable")
    score_tables = soup.select("table.bb-teamScoreTable")
    team_names: list[str] = []
    classify_hit_type = getattr(DASHBOARD, "classify_hit_type", lambda value: None)

    for table in score_tables:
        first_row = table.select_one("tr")
        cells = first_row.select("th,td") if first_row else []
        if cells:
            team_names.append(normalize_matchup_team_name(text(cells[0])))

    stats_by_team: dict[str, dict[str, dict]] = {}
    for team_name, table in zip(team_names, batting_tables):
        header_cells = table.select("tr")[0].select("th,td")
        headers = [text(cell) for cell in header_cells]
        header_map = {label: idx for idx, label in enumerate(headers)}
        team_rows: dict[str, dict] = {}
        for order, row in enumerate(table.select("tr")[1:], start=1):
            cells = row.select("th,td")
            if not cells:
                continue
            player_link = row.select_one("a[href*='/npb/player/']")
            player_name = text(player_link) or (text(cells[header_map["選手名"]]) if "選手名" in header_map else "")
            if not player_name:
                continue
            href = player_link.get("href", "") if player_link else ""
            match = re.search(r"/npb/player/(\d+)/top", href)
            player_id = match.group(1) if match else ""
            detail_items: list[str] = []
            for cell in cells[14:]:
                details = [text(node) for node in cell.select(".bb-statsTable__dataDetail")]
                if details:
                    detail_items.extend([detail for detail in details if detail])
                    continue
                cell_text = text(cell)
                if cell_text:
                    detail_items.append(cell_text)
            doubles = sum(1 for detail in detail_items if classify_hit_type(detail) == "doubles")
            triples = sum(1 for detail in detail_items if classify_hit_type(detail) == "triples")
            home_runs = parse_int(text(cells[header_map["本塁打"]])) if "本塁打" in header_map else 0
            hits = parse_int(text(cells[header_map["安打"]])) if "安打" in header_map else 0
            stats = {
                "order": order,
                "player": player_name,
                "playerId": player_id,
                "ab": parse_int(text(cells[header_map["打数"]])) if "打数" in header_map else 0,
                "runs": parse_int(text(cells[header_map["得点"]])) if "得点" in header_map else 0,
                "hits": hits,
                "rbi": parse_int(text(cells[header_map["打点"]])) if "打点" in header_map else 0,
                "walks": parse_int(text(cells[header_map["四球"]])) if "四球" in header_map else 0,
                "hitByPitch": parse_int(text(cells[header_map["死球"]])) if "死球" in header_map else 0,
                "sacBunts": parse_int(text(cells[header_map["犠打"]])) if "犠打" in header_map else 0,
                "steals": parse_int(text(cells[header_map["盗塁"]])) if "盗塁" in header_map else 0,
                "strikeouts": parse_int(text(cells[header_map["三振"]])) if "三振" in header_map else 0,
                "homeRuns": home_runs,
                "doubles": doubles,
                "triples": triples,
                "singles": max(hits - doubles - triples - home_runs, 0),
                "plateAppearances": len(detail_items),
            }
            team_rows[player_id or player_name] = stats
            if player_id:
                team_rows[player_name] = stats
        stats_by_team[team_name] = team_rows
    return stats_by_team


def fetch_game_batting_stats(session: requests.Session, game_id: str) -> dict[str, dict[str, dict]]:
    response = session.get(SPORTSNAVI_GAME_STATS_URL.format(game_id=game_id), headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    return parse_game_batting_stats_from_html(response.text)


def infer_title(prefix: str, date: str, payload: dict | None) -> tuple[str, str]:
    if payload:
        pitcher = payload.get("statline", {}).get("player") or ""
        matchup = payload.get("metadata", {}).get("matchup") or ""
        if pitcher:
            return pitcher, matchup

    tail = prefix
    if tail.startswith(f"{date}-"):
        tail = tail[len(date) + 1 :]
    return tail.replace("-", " "), ""


def make_pitch_color_map(pitch_mix: list[dict]) -> dict[str, str]:
    return {
        row["pitchType"]: PITCH_COLORS[idx % len(PITCH_COLORS)]
        for idx, row in enumerate(pitch_mix)
    }


def build_pitch_chart(rows: list[dict], pitch_color_map: dict[str, str]) -> dict[str, list[dict]]:
    final_by_pa: dict[str, tuple[int, int]] = {}
    chart = {"right": [], "left": []}

    for row in rows:
        pa_index = row.get("pa_index") or ""
        try:
            seq = int(row.get("seq") or 0)
        except (TypeError, ValueError):
            seq = 0
        try:
            pitch_no = int(row.get("pitchNo") or 0)
        except (TypeError, ValueError):
            pitch_no = 0
        current = final_by_pa.get(pa_index)
        if current is None or seq >= current[0]:
            final_by_pa[pa_index] = (seq, pitch_no)

    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    parse_speed = getattr(DASHBOARD, "parse_speed", lambda value: value)

    for row in sorted(rows, key=lambda item: int(item.get("pitchNo") or 0)):
        hand = row.get("batter_hand")
        if hand not in ("右", "左"):
            continue
        left = row.get("left")
        top = row.get("top")
        if left is None or top is None:
            continue
        pa_index = row.get("pa_index") or ""
        try:
            seq = int(row.get("seq") or 0)
        except (TypeError, ValueError):
            seq = 0
        try:
            pitch_no = int(row.get("pitchNo") or 0)
        except (TypeError, ValueError):
            pitch_no = 0
        chart_key = "right" if hand == "右" else "left"
        chart[chart_key].append(
            {
                "left": round(float(left), 2),
                "top": round(float(top), 2),
                "pitchType": row.get("pitchType") or "-",
                "color": pitch_color_map.get(row.get("pitchType") or "", PITCH_COLORS[0]),
                "speed": parse_speed(row.get("speed")),
                "speedLabel": row.get("speed") or "",
                "result": normalize_result(row.get("result") or ""),
                "pitchNo": pitch_no,
                "seq": seq,
                "batter": row.get("batter") or "",
                "isFinalPitch": final_by_pa.get(pa_index) == (seq, pitch_no),
            }
        )

    return {
        "right": chart["right"],
        "left": chart["left"],
        "bounds": {
            "width": HEATMAP_WIDTH,
            "height": HEATMAP_HEIGHT,
        },
    }


def serialize_stat_summary(label: int, stats: dict) -> dict:
    summary = DASHBOARD.summarize_stat_row(stats)
    max_speed = f"{max(stats['speeds']):.1f}" if stats["speeds"] else "-"
    return {
        "inning": label,
        "count": stats["count"],
        "avgSpeed": summary["avg_speed"],
        "maxSpeed": max_speed,
        "speedTotal": round_or_none(sum(stats["speeds"]), 1),
        "speedCount": len(stats["speeds"]),
        "whiffCount": summary["whiff_count"],
        "whiff": round(summary["whiff"], 1) if summary["whiff"] is not None else None,
        "atBats": summary["at_bats"],
        "singles": summary["singles"],
        "doubles": summary["doubles"],
        "triples": summary["triples"],
        "homeRuns": summary["home_runs"],
        "grounders": summary["grounders"],
        "flyBalls": summary["flyballs"],
        "strikeouts": summary["strikeouts"],
        "hitRate": round(summary["hit_rate"], 3) if summary["hit_rate"] is not None else None,
    }


def build_inning_summary(rows: list[dict], pitch_types: list[str]) -> dict:
    parse_inning = getattr(DASHBOARD, "parse_inning")
    parse_speed = getattr(DASHBOARD, "parse_speed")
    is_swing_miss_result = getattr(DASHBOARD, "is_swing_miss_result")
    record_ab_result = getattr(DASHBOARD, "record_ab_result")
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    build_stat_bucket = getattr(DASHBOARD, "build_stat_bucket")

    all_buckets = defaultdict(build_stat_bucket)
    pitch_buckets = {pitch_type: defaultdict(build_stat_bucket) for pitch_type in pitch_types}

    for row in rows:
        inning = parse_inning(row.get("pa_index"))
        if inning not in INNING_SLOTS:
            continue
        pitch_type = row.get("pitchType")
        speed = parse_speed(row.get("speed"))
        targets = [all_buckets[inning]]
        if pitch_type in pitch_buckets:
            targets.append(pitch_buckets[pitch_type][inning])
        for stats in targets:
            stats["count"] += 1
            if speed is not None:
                stats["speeds"].append(speed)
            if is_swing_miss_result(row.get("result")):
                stats["swing_miss"] += 1

    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        inning = parse_inning(final.get("pa_index"))
        if inning not in INNING_SLOTS:
            continue
        record_ab_result(all_buckets[inning], final.get("result"))
        pitch_type = final.get("pitchType")
        if pitch_type in pitch_buckets:
            record_ab_result(pitch_buckets[pitch_type][inning], final.get("result"))

    return {
        "all": [serialize_stat_summary(inning, all_buckets.get(inning, build_stat_bucket())) for inning in INNING_SLOTS],
        "byPitchType": {
            pitch_type: [serialize_stat_summary(inning, pitch_buckets[pitch_type].get(inning, build_stat_bucket())) for inning in INNING_SLOTS]
            for pitch_type in pitch_types
        },
    }


def build_velocity_summary(rows: list[dict], pitch_color_map: dict[str, str]) -> dict:
    parse_inning = getattr(DASHBOARD, "parse_inning", lambda value: None)
    parse_speed = getattr(DASHBOARD, "parse_speed", lambda value: None)
    safe_int = getattr(DASHBOARD, "safe_int", lambda value, default=0: default)

    ordered = sorted(rows, key=lambda row: safe_int(row.get("pitchNo"), 0))
    inning_starts: dict[int, int] = {}
    speed_rows = []

    for row in ordered:
        pitch_no = safe_int(row.get("pitchNo"), 0)
        inning = parse_inning(row.get("pa_index"))
        if inning is not None and inning not in inning_starts:
            inning_starts[inning] = pitch_no

        speed = parse_speed(row.get("speed"))
        pitch_type = row.get("pitchType")
        if speed is None or not pitch_type:
            continue

        speed_rows.append(
            {
                "pitchNo": pitch_no,
                "speed": speed,
                "inning": inning,
                "pitchType": pitch_type,
                "color": pitch_color_map.get(pitch_type, PITCH_COLORS[0]),
            }
        )

    return {
        "rows": speed_rows,
        "markers": [
            {"inning": inning, "pitchNo": pitch_no}
            for inning, pitch_no in sorted(inning_starts.items())
        ],
    }


def classify_outcome_result(result: str) -> str | None:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    grounder_words = tuple(getattr(DASHBOARD, "GROUNDER_WORDS", ("ゴロ", "併打")))
    fly_words = tuple(getattr(DASHBOARD, "FLY_WORDS", ("飛", "直", "ライナー")))

    primary = normalize_result(result)
    if not primary:
        return None
    if "見三振" in primary:
        return "lookingStrikeouts"
    if "空三振" in primary or "バ三振" in primary:
        return "swingingStrikeouts"
    if primary.endswith("犠打"):
        return "sacrificeBunts"
    if "守備妨害" in primary:
        return "interference"
    if any(word in primary for word in grounder_words):
        return "grounders"
    if any(word in primary for word in fly_words):
        return "flyballs"
    return None


def build_outcome_summary(rows: list[dict]) -> dict:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")

    counts = Counter()
    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        category = classify_outcome_result(final.get("result"))
        if category:
            counts[category] += 1

    total = sum(counts.values())
    summary_rows = [
        {
            "id": key,
            "label": label,
            "count": counts.get(key, 0),
            "ratio": round(counts.get(key, 0) / total * 100, 1) if total else 0.0,
            "color": color,
        }
        for key, label, color in OUTCOME_META
    ]
    return {
        "total": total,
        "rows": summary_rows,
    }


def count_intentional_walks(rows: list[dict]) -> int:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    total = 0
    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        if is_intentional_walk_text(final.get("result")):
            total += 1
    return total


def count_sacrifice_flies(rows: list[dict]) -> int:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: True)
    classify_plate_appearance_result = getattr(DASHBOARD, "classify_plate_appearance_result", lambda value: None)
    total = 0
    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        result = final.get("result") or ""
        if result and not is_ab_result(result) and classify_plate_appearance_result(result) == "flyballs":
            total += 1
    return total


def is_located_pitch(row: dict) -> bool:
    return parse_float(row.get("left")) is not None and parse_float(row.get("top")) is not None


def is_zone_pitch(row: dict) -> bool:
    left = parse_float(row.get("left"))
    top = parse_float(row.get("top"))
    if left is None or top is None:
        return False
    return (
        HEATMAP_WIDTH * 0.2 <= left <= HEATMAP_WIDTH * 0.8
        and HEATMAP_HEIGHT * 0.2 <= top <= HEATMAP_HEIGHT * 0.8
    )


def is_called_strike_result(result: str) -> bool:
    primary = DASHBOARD.normalize_result(result or "")
    return "見逃し" in primary or "見三振" in primary or primary == "ストライク"


def is_ball_result(result: str) -> bool:
    primary = DASHBOARD.normalize_result(result or "")
    return "ボール" in primary or "四球" in primary or "死球" in primary


def is_contact_result(result: str) -> bool:
    primary = DASHBOARD.normalize_result(result or "")
    if not primary or DASHBOARD.is_swing_miss_result(primary) or is_called_strike_result(primary) or is_ball_result(primary):
        return False
    return True


def is_swing_result(result: str) -> bool:
    return DASHBOARD.is_swing_miss_result(result or "") or is_contact_result(result or "")


def build_plate_discipline_bucket() -> dict:
    return {
        "pitches": 0,
        "located": 0,
        "zone": 0,
        "outZone": 0,
        "swings": 0,
        "whiffs": 0,
        "calledStrikes": 0,
        "zoneSwings": 0,
        "outZoneSwings": 0,
        "outZoneContacts": 0,
    }


def record_plate_discipline_pitch(bucket: dict, row: dict) -> None:
    result = row.get("result") or ""
    swing = is_swing_result(result)
    whiff = DASHBOARD.is_swing_miss_result(result)
    called_strike = is_called_strike_result(result)
    located = is_located_pitch(row)
    in_zone = is_zone_pitch(row) if located else False

    bucket["pitches"] += 1
    if swing:
        bucket["swings"] += 1
    if whiff:
        bucket["whiffs"] += 1
    if called_strike:
        bucket["calledStrikes"] += 1
    if not located:
        return

    bucket["located"] += 1
    if in_zone:
        bucket["zone"] += 1
        if swing:
            bucket["zoneSwings"] += 1
    else:
        bucket["outZone"] += 1
        if swing:
            bucket["outZoneSwings"] += 1
            if is_contact_result(result):
                bucket["outZoneContacts"] += 1


def finalize_plate_discipline_bucket(bucket: dict, overall_chase: float | None = None) -> dict:
    swings = parse_int(bucket.get("swings"))
    pitches = parse_int(bucket.get("pitches"))
    located = parse_int(bucket.get("located"))
    zone = parse_int(bucket.get("zone"))
    out_zone = parse_int(bucket.get("outZone"))
    out_zone_swings = parse_int(bucket.get("outZoneSwings"))
    chase = (out_zone_swings / out_zone * 100) if out_zone else None
    return {
        "swingCount": swings,
        "calledStrikeCount": parse_int(bucket.get("calledStrikes")),
        "locatedCount": located,
        "zoneCount": zone,
        "outZoneCount": out_zone,
        "zoneSwingCount": parse_int(bucket.get("zoneSwings")),
        "outZoneSwingCount": out_zone_swings,
        "outZoneContactCount": parse_int(bucket.get("outZoneContacts")),
        "whiffRate": round_or_none(parse_int(bucket.get("whiffs")) / swings * 100, 1) if swings else None,
        "csw": round_or_none((parse_int(bucket.get("whiffs")) + parse_int(bucket.get("calledStrikes"))) / pitches * 100, 1) if pitches else None,
        "zoneRate": round_or_none(zone / located * 100, 1) if located else None,
        "zSwing": round_or_none(parse_int(bucket.get("zoneSwings")) / zone * 100, 1) if zone else None,
        "oContact": round_or_none(parse_int(bucket.get("outZoneContacts")) / out_zone_swings * 100, 1) if out_zone_swings else None,
        "chase": round_or_none(chase, 1),
        "chasePlus": round_or_none((chase / overall_chase * 100), 0) if chase is not None and overall_chase else None,
    }


def build_pitch_discipline_summary(rows: list[dict], chase_plus_baseline: float | None = None) -> tuple[dict[str, dict], float | None]:
    by_pitch: dict[str, dict] = defaultdict(build_plate_discipline_bucket)
    overall = build_plate_discipline_bucket()
    for row in rows:
        pitch_type = row.get("pitchType") or "-"
        record_plate_discipline_pitch(overall, row)
        record_plate_discipline_pitch(by_pitch[pitch_type], row)
    overall_rates = finalize_plate_discipline_bucket(overall)
    overall_chase = overall_rates.get("chase")
    chase_baseline = chase_plus_baseline or overall_chase
    return {
        pitch_type: finalize_plate_discipline_bucket(bucket, chase_baseline)
        for pitch_type, bucket in by_pitch.items()
    }, chase_baseline


def build_league_chase_baselines(grouped_entries: dict[tuple[str, str, str], dict]) -> dict[str, float | None]:
    buckets: dict[str, dict] = defaultdict(build_plate_discipline_bucket)
    for (team, date, prefix) in grouped_entries:
        json_path = GENERATED_DIR / team / date / f"{prefix}-dashboard.json"
        payload = safe_load_json(json_path)
        if not payload:
            continue
        league = team_league(team)
        if not league:
            continue
        for row in payload.get("pitches") or []:
            record_plate_discipline_pitch(buckets[league], row)
            record_plate_discipline_pitch(buckets["NPB"], row)

    return {
        league: finalize_plate_discipline_bucket(bucket).get("chase")
        for league, bucket in buckets.items()
    }


def serialize_dashboard(payload: dict, chase_plus_baseline: float | None = None) -> dict:
    rows = payload.get("pitches") or []
    if not rows:
        return {}

    (
        total,
        pitch_counts,
        pitch_stats,
        heat_by_hand,
        inning_rows,
        count_mix_summary,
        finish_summary,
        _velocity_trend,
    ) = DASHBOARD.summarize(rows)

    discipline_by_pitch, chase_baseline = build_pitch_discipline_summary(rows, chase_plus_baseline)
    pitch_mix = []
    for idx, (pitch_type, count) in enumerate(pitch_counts.most_common()):
        stats = pitch_stats[pitch_type]
        summary = DASHBOARD.summarize_stat_row(stats)
        max_speed = f"{max(stats['speeds']):.1f}" if stats["speeds"] else "-"
        pitch_mix.append(
            {
                "pitchType": pitch_type,
                "count": count,
                "ratio": round(count / total * 100, 1) if total else 0.0,
                "avgSpeed": summary["avg_speed"],
                "maxSpeed": max_speed,
                "speedTotal": round_or_none(sum(stats["speeds"]), 1),
                "speedCount": len(stats["speeds"]),
                "whiffCount": summary["whiff_count"],
                "whiff": round(summary["whiff"], 1) if summary["whiff"] is not None else None,
                "atBats": summary["at_bats"],
                "singles": summary["singles"],
                "doubles": summary["doubles"],
                "triples": summary["triples"],
                "homeRuns": summary["home_runs"],
                "grounders": summary["grounders"],
                "flyBalls": summary["flyballs"],
                "strikeouts": summary["strikeouts"],
                "hitRate": round(summary["hit_rate"], 3) if summary["hit_rate"] is not None else None,
                "color": PITCH_COLORS[idx % len(PITCH_COLORS)],
                **discipline_by_pitch.get(pitch_type, {}),
            }
        )

    pitch_color_map = make_pitch_color_map(pitch_mix)
    bucket_counts, bucket_totals = count_mix_summary
    count_mix = []
    for bucket in COUNT_BUCKETS:
        total_bucket = bucket_totals[bucket]
        segments = []
        for pitch in pitch_mix:
            count = bucket_counts[bucket][pitch["pitchType"]]
            ratio = round(count / total_bucket * 100, 1) if total_bucket else 0.0
            segments.append(
                {
                    "pitchType": pitch["pitchType"],
                    "count": count,
                    "ratio": ratio,
                    "color": pitch_color_map[pitch["pitchType"]],
                }
            )
        count_mix.append({"bucket": bucket, "total": total_bucket, "segments": segments})

    finish_total, finish_stats = finish_summary
    finish_rows = []
    for pitch_type, stats in sorted(finish_stats.items(), key=lambda item: item[1]["count"], reverse=True):
        finish_rows.append(
            {
                "pitchType": pitch_type,
                "count": stats["count"],
                "ratio": round(stats["count"] / finish_total * 100, 1) if finish_total else 0.0,
                "looking": stats["looking"],
                "swinging": stats["swinging"],
                "color": pitch_color_map.get(pitch_type, PITCH_COLORS[0]),
            }
        )

    inning_summary = build_inning_summary(rows, [row["pitchType"] for row in pitch_mix])
    outcome_summary = build_outcome_summary(rows)
    velocity_summary = build_velocity_summary(rows, pitch_color_map)
    intentional_walks = count_intentional_walks(rows)
    sacrifice_flies = count_sacrifice_flies(rows)
    return {
        "totalPitches": total,
        "pitchMix": pitch_mix,
        "inningRows": inning_summary["all"],
        "inningSummary": inning_summary,
        "heatmaps": {
            "right": heat_by_hand.get("右").tolist() if "右" in heat_by_hand else EMPTY_HEATMAP,
            "left": heat_by_hand.get("左").tolist() if "左" in heat_by_hand else EMPTY_HEATMAP,
        },
        "pitchChart": build_pitch_chart(rows, pitch_color_map),
        "finish": {
            "total": finish_total,
            "rows": finish_rows,
        },
        "outcomes": outcome_summary,
        "intentionalWalks": intentional_walks,
        "sacrificeFlies": sacrifice_flies,
        "velocity": velocity_summary,
        "countMix": count_mix,
        "pitchColors": pitch_color_map,
        "metricBaselines": {
            "chase": round_or_none(chase_baseline, 1),
            "chaseScope": "league" if chase_plus_baseline else "game",
        },
    }


def build_batter_pitch_mix(rows: list[dict]) -> tuple[list[dict], dict[str, str]]:
    pitch_counts = Counter(row.get("pitchType") or "-" for row in rows if row.get("pitchType"))
    total = sum(pitch_counts.values())
    pitch_mix = [
        {
            "pitchType": pitch_type,
            "count": count,
            "ratio": round(count / total * 100, 1) if total else 0.0,
            "color": PITCH_COLORS[idx % len(PITCH_COLORS)],
        }
        for idx, (pitch_type, count) in enumerate(pitch_counts.most_common())
    ]
    return pitch_mix, make_pitch_color_map(pitch_mix)


def build_batter_statline_from_pas(plate_appearances: list[list[dict]]) -> dict:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: False)
    is_hit = getattr(DASHBOARD, "is_hit", lambda value: False)
    classify_hit_type = getattr(DASHBOARD, "classify_hit_type", lambda value: None)

    stats = {
        "ab": 0,
        "hits": 0,
        "homeRuns": 0,
        "rbi": 0,
        "walks": 0,
        "strikeouts": 0,
    }

    for pitches in plate_appearances:
        if not pitches:
            continue
        final = pitches[-1]
        result = final.get("result") or ""
        primary = normalize_result(result)
        if is_ab_result(result):
            stats["ab"] += 1
        if is_hit(result):
            stats["hits"] += 1
            if classify_hit_type(result) == "home_runs":
                stats["homeRuns"] += 1
        if "四球" in primary:
            stats["walks"] += 1
        if any(word in primary for word in ("空三振", "見三振", "バ三振", "振逃")):
            stats["strikeouts"] += 1

    return stats


def serialize_batter_plate_points(pitches: list[dict], pitch_color_map: dict[str, str]) -> list[dict]:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    parse_speed = getattr(DASHBOARD, "parse_speed", lambda value: value)
    points: list[dict] = []
    final_pitch = pitches[-1] if pitches else None

    for row in pitches:
        left = row.get("left")
        top = row.get("top")
        if left is None or top is None:
            continue
        points.append(
            {
                "left": round(float(left), 2),
                "top": round(float(top), 2),
                "pitchType": row.get("pitchType") or "-",
                "color": pitch_color_map.get(row.get("pitchType") or "", PITCH_COLORS[0]),
                "speed": parse_speed(row.get("speed")),
                "speedLabel": row.get("speed") or "-",
                "result": normalize_result(row.get("result") or ""),
                "pitchNo": parse_int(row.get("pitchNo")),
                "seq": parse_int(row.get("seq")),
                "pitcher": row.get("pitcher") or "",
                "isFinalPitch": row is final_pitch,
            }
        )
    return points


def extract_pitcher_id(payload: dict) -> str:
    for row in payload.get("pitches") or []:
        pitcher_id = row.get("pitcher_id")
        if pitcher_id:
            return str(pitcher_id)
    return ""


def resolve_game_decision(entry: dict, game_decisions: dict[str, dict]) -> dict:
    game_id = entry.get("gameId") or ""
    if not game_id:
        return {}
    decisions = game_decisions.get(game_id) or {}
    pitcher_id = entry.get("pitcherId") or ""
    if pitcher_id and pitcher_id in decisions:
        return decisions[pitcher_id]
    player_name = entry.get("player") or ""
    for bucket in decisions.values():
        if bucket.get("player") == player_name:
            return bucket
    return {}


def load_game_contexts() -> dict[str, dict]:
    contexts: dict[str, dict] = {}
    for path in sorted(SUMMARY_DIR.glob("sportsnavi_game_context_*.json")):
        match = GAME_CONTEXT_PATTERN.match(path.name)
        if not match:
            continue
        payload = safe_load_json(path)
        if not payload:
            continue
        contexts[match.group("season")] = payload
    return contexts


def build_park_factors(game_contexts: dict[str, dict]) -> dict:
    seasons = sorted(game_contexts)
    by_season: dict[str, dict] = {}

    for season in seasons:
        payload = game_contexts[season]
        games = payload.get("games") or []
        flattened_games = []

        for game in games:
            home_team = normalize_matchup_team_name(game.get("homeTeam") or "")
            away_team = normalize_matchup_team_name(game.get("awayTeam") or "")
            league = team_league(home_team) or team_league(away_team)
            stadium = game.get("stadium") or ""
            home_score = parse_int(game.get("homeScore"))
            away_score = parse_int(game.get("awayScore"))
            if not home_team or not away_team or not league or not stadium:
                continue
            if home_score is None or away_score is None:
                continue
            flattened_games.append(
                {
                    "gameId": game.get("gameId") or "",
                    "date": game.get("date") or "",
                    "league": league,
                    "stadium": stadium,
                    "homeTeam": home_team,
                    "awayTeam": away_team,
                    "homeScore": home_score,
                    "awayScore": away_score,
                    "totalRuns": home_score + away_score,
                }
            )

        league_buckets: dict[str, dict] = defaultdict(lambda: {"games": 0, "totalRuns": 0})
        stadium_buckets: dict[tuple[str, str], dict] = defaultdict(
            lambda: {
                "games": 0,
                "totalRuns": 0,
                "homeRuns": 0,
                "awayRuns": 0,
                "homeTeams": Counter(),
            }
        )
        team_buckets: dict[str, dict] = defaultdict(
            lambda: {
                "league": "",
                "homeGames": 0,
                "roadGames": 0,
                "homeTotalRuns": 0,
                "roadTotalRuns": 0,
                "venues": defaultdict(lambda: {"games": 0, "totalRuns": 0}),
            }
        )

        for game in flattened_games:
            league_bucket = league_buckets[game["league"]]
            league_bucket["games"] += 1
            league_bucket["totalRuns"] += game["totalRuns"]

            stadium_bucket = stadium_buckets[(game["league"], game["stadium"])]
            stadium_bucket["games"] += 1
            stadium_bucket["totalRuns"] += game["totalRuns"]
            stadium_bucket["homeRuns"] += game["homeScore"]
            stadium_bucket["awayRuns"] += game["awayScore"]
            stadium_bucket["homeTeams"][game["homeTeam"]] += 1

            home_bucket = team_buckets[game["homeTeam"]]
            home_bucket["league"] = team_league(game["homeTeam"])
            home_bucket["homeGames"] += 1
            home_bucket["homeTotalRuns"] += game["totalRuns"]
            home_bucket["venues"][game["stadium"]]["games"] += 1
            home_bucket["venues"][game["stadium"]]["totalRuns"] += game["totalRuns"]

            away_bucket = team_buckets[game["awayTeam"]]
            away_bucket["league"] = team_league(game["awayTeam"])
            away_bucket["roadGames"] += 1
            away_bucket["roadTotalRuns"] += game["totalRuns"]

        league_rows = []
        for league, stats in sorted(league_buckets.items()):
            runs_per_game = stats["totalRuns"] / stats["games"] if stats["games"] else None
            league_rows.append(
                {
                    "league": league,
                    "games": stats["games"],
                    "totalRuns": stats["totalRuns"],
                    "runsPerGame": round_or_none(runs_per_game, 3),
                }
            )

        stadium_rows = []
        for (league, stadium), stats in sorted(stadium_buckets.items()):
            league_stats = league_buckets.get(league) or {}
            stadium_rpg = stats["totalRuns"] / stats["games"] if stats["games"] else None
            league_rpg = (
                league_stats["totalRuns"] / league_stats["games"]
                if league_stats.get("games")
                else None
            )
            run_factor = ((stadium_rpg / league_rpg) * 100) if stadium_rpg and league_rpg else None
            home_teams = [team for team, _count in stats["homeTeams"].most_common()]
            stadium_rows.append(
                {
                    "league": league,
                    "stadium": stadium,
                    "games": stats["games"],
                    "homeTeams": home_teams,
                    "primaryHomeTeam": home_teams[0] if home_teams else "",
                    "totalRuns": stats["totalRuns"],
                    "runsPerGame": round_or_none(stadium_rpg, 3),
                    "leagueRunsPerGame": round_or_none(league_rpg, 3),
                    "runFactor": round_or_none(run_factor, 1),
                    "homeRuns": stats["homeRuns"],
                    "awayRuns": stats["awayRuns"],
                }
            )

        team_rows = []
        for team, stats in sorted(team_buckets.items(), key=lambda item: team_sort_key(item[0])):
            home_rpg = stats["homeTotalRuns"] / stats["homeGames"] if stats["homeGames"] else None
            road_rpg = stats["roadTotalRuns"] / stats["roadGames"] if stats["roadGames"] else None
            team_factor = ((home_rpg / road_rpg) * 100) if home_rpg and road_rpg else None
            venue_rows = [
                {
                    "stadium": stadium,
                    "games": venue_stats["games"],
                    "totalRuns": venue_stats["totalRuns"],
                    "runsPerGame": round_or_none(venue_stats["totalRuns"] / venue_stats["games"], 3)
                    if venue_stats["games"]
                    else None,
                }
                for stadium, venue_stats in sorted(
                    stats["venues"].items(),
                    key=lambda item: (-item[1]["games"], item[0]),
                )
            ]
            team_rows.append(
                {
                    "team": team,
                    "league": stats["league"],
                    "homeGames": stats["homeGames"],
                    "roadGames": stats["roadGames"],
                    "homeTotalRuns": stats["homeTotalRuns"],
                    "roadTotalRuns": stats["roadTotalRuns"],
                    "homeRunsPerGame": round_or_none(home_rpg, 3),
                    "roadRunsPerGame": round_or_none(road_rpg, 3),
                    "homeParkFactor": round_or_none(team_factor, 1),
                    "primaryStadium": venue_rows[0]["stadium"] if venue_rows else "",
                    "venueBreakdown": venue_rows,
                }
            )

        by_season[season] = {
            "games": len(flattened_games),
            "leagueAverages": league_rows,
            "stadiums": stadium_rows,
            "teams": team_rows,
        }

    return {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": sorted(f"sportsnavi_game_context_{season}.json" for season in seasons),
        "notes": {
            "runFactor": "100 is league-average runs per game for the same season and league.",
            "homeParkFactor": "100 compares a team's home-game run environment to that same team's road games.",
            "coverage": "Only completed games with both score and stadium available in sportsnavi_game_context files are included.",
        },
        "seasons": seasons,
        "bySeason": by_season,
    }


def build_annual_stat_bucket() -> dict:
    return {
        "count": 0,
        "speedTotal": 0.0,
        "speedCount": 0,
        "maxSpeed": None,
        "whiffCount": 0,
        "swingCount": 0,
        "calledStrikeCount": 0,
        "locatedCount": 0,
        "zoneCount": 0,
        "outZoneCount": 0,
        "zoneSwingCount": 0,
        "outZoneSwingCount": 0,
        "outZoneContactCount": 0,
        "atBats": 0,
        "singles": 0,
        "doubles": 0,
        "triples": 0,
        "homeRuns": 0,
        "grounders": 0,
        "flyBalls": 0,
        "strikeouts": 0,
        "sacrificeFlies": 0,
    }


def add_serialized_stat_row(bucket: dict, row: dict) -> None:
    count = parse_int(row.get("count"))
    bucket["count"] += count

    speed_count = parse_int(row.get("speedCount"))
    speed_total = parse_float(row.get("speedTotal"))
    if speed_count <= 0:
        avg_speed = parse_float(row.get("avgSpeed"))
        if avg_speed is not None and count:
            speed_count = count
            speed_total = avg_speed * count
    if speed_count > 0 and speed_total is not None:
        bucket["speedCount"] += speed_count
        bucket["speedTotal"] += speed_total

    max_speed = parse_float(row.get("maxSpeed"))
    if max_speed is not None:
        bucket["maxSpeed"] = max(max_speed, bucket["maxSpeed"] or max_speed)

    bucket["whiffCount"] += parse_int(row.get("whiffCount"))
    bucket["swingCount"] += parse_int(row.get("swingCount"))
    bucket["calledStrikeCount"] += parse_int(row.get("calledStrikeCount"))
    bucket["locatedCount"] += parse_int(row.get("locatedCount"))
    bucket["zoneCount"] += parse_int(row.get("zoneCount"))
    bucket["outZoneCount"] += parse_int(row.get("outZoneCount"))
    bucket["zoneSwingCount"] += parse_int(row.get("zoneSwingCount"))
    bucket["outZoneSwingCount"] += parse_int(row.get("outZoneSwingCount"))
    bucket["outZoneContactCount"] += parse_int(row.get("outZoneContactCount"))
    bucket["atBats"] += parse_int(row.get("atBats"))
    bucket["singles"] += parse_int(row.get("singles"))
    bucket["doubles"] += parse_int(row.get("doubles"))
    bucket["triples"] += parse_int(row.get("triples"))
    bucket["homeRuns"] += parse_int(row.get("homeRuns"))
    bucket["grounders"] += parse_int(row.get("grounders"))
    bucket["flyBalls"] += parse_int(row.get("flyBalls"))
    bucket["strikeouts"] += parse_int(row.get("strikeouts"))
    bucket["sacrificeFlies"] += parse_int(row.get("sacrificeFlies") or row.get("sacFlies"))


def serialize_annual_stat_bucket(stats: dict, total: int | None = None, chase_plus_baseline: float | None = None) -> dict:
    count = parse_int(stats.get("count"))
    speed_count = parse_int(stats.get("speedCount"))
    speed_total = parse_float(stats.get("speedTotal")) or 0.0
    avg_speed = (speed_total / speed_count) if speed_count else None
    hits = (
        parse_int(stats.get("singles"))
        + parse_int(stats.get("doubles"))
        + parse_int(stats.get("triples"))
        + parse_int(stats.get("homeRuns"))
    )
    at_bats = parse_int(stats.get("atBats"))
    whiff = parse_int(stats.get("whiffCount")) / count * 100 if count else None
    hit_rate = hits / at_bats if at_bats else None
    sacrifice_flies = parse_int(stats.get("sacrificeFlies"))
    babip_denominator = at_bats - parse_int(stats.get("strikeouts")) - parse_int(stats.get("homeRuns")) + sacrifice_flies
    babip_allowed = ((hits - parse_int(stats.get("homeRuns"))) / babip_denominator) if babip_denominator > 0 else None
    swings = parse_int(stats.get("swingCount"))
    called_strikes = parse_int(stats.get("calledStrikeCount"))
    located = parse_int(stats.get("locatedCount"))
    zone = parse_int(stats.get("zoneCount"))
    out_zone = parse_int(stats.get("outZoneCount"))
    zone_swings = parse_int(stats.get("zoneSwingCount"))
    out_zone_swings = parse_int(stats.get("outZoneSwingCount"))
    out_zone_contacts = parse_int(stats.get("outZoneContactCount"))
    chase = out_zone_swings / out_zone * 100 if out_zone else None
    row = {
        "count": count,
        "ratio": round_or_none(count / total * 100, 1) if total else 0.0,
        "avgSpeed": f"{avg_speed:.1f}" if avg_speed is not None else "-",
        "maxSpeed": f"{parse_float(stats.get('maxSpeed')):.1f}" if parse_float(stats.get("maxSpeed")) is not None else "-",
        "speedTotal": round_or_none(speed_total, 1) if speed_count else None,
        "speedCount": speed_count,
        "whiffCount": parse_int(stats.get("whiffCount")),
        "whiff": round_or_none(whiff, 1),
        "swingCount": swings,
        "calledStrikeCount": called_strikes,
        "locatedCount": located,
        "zoneCount": zone,
        "outZoneCount": out_zone,
        "zoneSwingCount": zone_swings,
        "outZoneSwingCount": out_zone_swings,
        "outZoneContactCount": out_zone_contacts,
        "whiffRate": round_or_none(parse_int(stats.get("whiffCount")) / swings * 100, 1) if swings else None,
        "csw": round_or_none((parse_int(stats.get("whiffCount")) + called_strikes) / count * 100, 1) if count else None,
        "zoneRate": round_or_none(zone / located * 100, 1) if located else None,
        "zSwing": round_or_none(zone_swings / zone * 100, 1) if zone else None,
        "oContact": round_or_none(out_zone_contacts / out_zone_swings * 100, 1) if out_zone_swings else None,
        "chase": round_or_none(chase, 1),
        "chasePlus": round_or_none(chase / chase_plus_baseline * 100, 0) if chase is not None and chase_plus_baseline else None,
        "atBats": at_bats,
        "singles": parse_int(stats.get("singles")),
        "doubles": parse_int(stats.get("doubles")),
        "triples": parse_int(stats.get("triples")),
        "homeRuns": parse_int(stats.get("homeRuns")),
        "grounders": parse_int(stats.get("grounders")),
        "flyBalls": parse_int(stats.get("flyBalls")),
        "strikeouts": parse_int(stats.get("strikeouts")),
        "sacrificeFlies": sacrifice_flies,
        "hitRate": round_or_none(hit_rate, 3),
        "babipAllowed": round_or_none(babip_allowed, 3),
    }
    return row


def build_serialized_pitch_stat_row(label: str, rows: list[dict], order: int = 0, total: int | None = None) -> dict:
    if not rows:
        row = serialize_annual_stat_bucket(build_annual_stat_bucket(), total)
        row.update({"label": label, "order": order})
        return row

    _total, pitch_counts, pitch_stats, *_rest = DASHBOARD.summarize(rows)
    bucket = build_annual_stat_bucket()
    for pitch_type, count in pitch_counts.items():
        stats = pitch_stats[pitch_type]
        summary = DASHBOARD.summarize_stat_row(stats)
        add_serialized_stat_row(
            bucket,
            {
                "count": count,
                "avgSpeed": summary["avg_speed"],
                "maxSpeed": f"{max(stats['speeds']):.1f}" if stats["speeds"] else "-",
                "speedTotal": round_or_none(sum(stats["speeds"]), 1),
                "speedCount": len(stats["speeds"]),
                "whiffCount": summary["whiff_count"],
                "atBats": summary["at_bats"],
                "singles": summary["singles"],
                "doubles": summary["doubles"],
                "triples": summary["triples"],
                "homeRuns": summary["home_runs"],
                "grounders": summary["grounders"],
                "flyBalls": summary["flyballs"],
                "strikeouts": summary["strikeouts"],
            },
        )
    bucket["sacrificeFlies"] += count_sacrifice_flies(rows)

    row = serialize_annual_stat_bucket(bucket, total)
    row.update({"label": label, "order": order})
    return row


def build_pitcher_batter_hand_rows(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        hand = row.get("batter_hand") or "-"
        groups[hand if hand in ("右", "左") else "-"].append(row)
    order_map = {"右": 0, "左": 1, "-": 2}
    total = len(rows)
    return [
        build_serialized_pitch_stat_row(label, groups[label], order_map.get(label, 99), total)
        for label in sorted(groups, key=lambda label: (order_map.get(label, 99), label))
    ]


def build_pitcher_inning_walk_rows(rows: list[dict]) -> list[dict]:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    parse_inning = getattr(DASHBOARD, "parse_inning", lambda value: None)
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    buckets = {inning: {"inning": inning, "walks": 0, "hitByPitch": 0, "walksAndHbp": 0} for inning in INNING_SLOTS}

    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        inning = parse_inning(final.get("pa_index"))
        if inning not in buckets:
            continue
        result = normalize_result(final.get("result") or "")
        if "四球" in result:
            buckets[inning]["walks"] += 1
            buckets[inning]["walksAndHbp"] += 1
        elif "死球" in result:
            buckets[inning]["hitByPitch"] += 1
            buckets[inning]["walksAndHbp"] += 1

    return [buckets[inning] for inning in INNING_SLOTS]


def build_pitcher_game_split_bucket(label: str, order: int = 0) -> dict:
    return {
        "label": label,
        "order": order,
        "games": 0,
        "outs": 0,
        "batters": 0,
        "pitches": 0,
        "hits": 0,
        "homeRuns": 0,
        "strikeouts": 0,
        "walks": 0,
        "hitByPitch": 0,
        "runs": 0,
        "earnedRuns": 0,
        "atBats": 0,
        "sacrificeFlies": 0,
    }


def record_pitcher_game_split(bucket: dict, entry: dict) -> None:
    statline = entry.get("statline") or {}
    dashboard = entry.get("dashboard") or {}
    pitch_rows = dashboard.get("pitchMix") or []
    bucket["games"] += 1
    bucket["outs"] += innings_to_outs(statline.get("innings"))
    bucket["batters"] += parse_int(statline.get("batters"))
    bucket["pitches"] += parse_int(statline.get("pitches"))
    bucket["hits"] += parse_int(statline.get("hits"))
    bucket["homeRuns"] += parse_int(statline.get("hr"))
    bucket["strikeouts"] += parse_int(statline.get("k"))
    bucket["walks"] += parse_int(statline.get("bb"))
    bucket["hitByPitch"] += parse_int(statline.get("hbp"))
    bucket["runs"] += parse_int(statline.get("runs"))
    bucket["earnedRuns"] += parse_int(statline.get("er"))
    bucket["atBats"] += sum(parse_int(row.get("atBats")) for row in pitch_rows)
    bucket["sacrificeFlies"] += parse_int(dashboard.get("sacrificeFlies"))


def finalize_pitcher_game_split_bucket(bucket: dict) -> dict:
    outs = parse_int(bucket.get("outs"))
    ip = outs_to_ip(outs)
    era = 9 * parse_int(bucket.get("earnedRuns")) / ip if ip else None
    whip = (parse_int(bucket.get("hits")) + parse_int(bucket.get("walks"))) / ip if ip else None
    batting_average = parse_int(bucket.get("hits")) / parse_int(bucket.get("atBats")) if parse_int(bucket.get("atBats")) else None
    babip_denominator = (
        parse_int(bucket.get("atBats"))
        - parse_int(bucket.get("strikeouts"))
        - parse_int(bucket.get("homeRuns"))
        + parse_int(bucket.get("sacrificeFlies"))
    )
    babip_allowed = (
        (parse_int(bucket.get("hits")) - parse_int(bucket.get("homeRuns"))) / babip_denominator
        if babip_denominator > 0
        else None
    )
    return {
        "label": bucket.get("label") or "-",
        "games": parse_int(bucket.get("games")),
        "innings": outs_to_innings_notation(outs),
        "inningsOuts": outs,
        "batters": parse_int(bucket.get("batters")),
        "pitches": parse_int(bucket.get("pitches")),
        "hits": parse_int(bucket.get("hits")),
        "homeRuns": parse_int(bucket.get("homeRuns")),
        "strikeouts": parse_int(bucket.get("strikeouts")),
        "walks": parse_int(bucket.get("walks")),
        "hitByPitch": parse_int(bucket.get("hitByPitch")),
        "runs": parse_int(bucket.get("runs")),
        "earnedRuns": parse_int(bucket.get("earnedRuns")),
        "sacrificeFlies": parse_int(bucket.get("sacrificeFlies")),
        "era": round_or_none(era, 2),
        "whip": round_or_none(whip, 2),
        "battingAverageAllowed": round_or_none(batting_average, 3),
        "babipAllowed": round_or_none(babip_allowed, 3),
    }


def season_dashboard_source(player_bucket: dict) -> dict:
    source = player_bucket.get("_seasonDashboardSource")
    if source is None:
        source = {
            "totalPitches": 0,
            "pitchTypes": defaultdict(build_annual_stat_bucket),
            "innings": defaultdict(build_annual_stat_bucket),
            "batterHands": defaultdict(build_annual_stat_bucket),
            "opponents": {},
            "stadiums": {},
            "inningRunsByDecision": defaultdict(lambda: defaultdict(int)),
            "inningWalksByDecision": defaultdict(lambda: defaultdict(int)),
            "outcomes": Counter(),
            "outcomeMeta": {},
            "finish": defaultdict(lambda: {"count": 0, "looking": 0, "swinging": 0}),
            "finishTotal": 0,
            "pitchColors": {},
            "metricBaselines": {},
            "recentGames": [],
            "hasData": False,
        }
        player_bucket["_seasonDashboardSource"] = source
    return source


def pitcher_decision_key(decision_row: dict) -> str:
    if parse_int((decision_row or {}).get("wins")) > 0:
        return "win"
    if parse_int((decision_row or {}).get("losses")) > 0:
        return "loss"
    return "noDecision"


def pitcher_innings_from_rows(rows: list[dict]) -> list[int]:
    parse_inning = getattr(DASHBOARD, "parse_inning", lambda value: None)
    innings = {
        inning
        for row in rows
        for inning in [parse_inning(row.get("pa_index"))]
        if inning in INNING_SLOTS
    }
    return sorted(innings)


def opponent_inning_scores(entry: dict, game_context: dict | None) -> dict[int, int]:
    opponent = matchup_opponent_team(entry.get("team") or "", entry.get("matchup") or "")
    scores = ((game_context or {}).get("inningScores") or {})
    rows = []
    for side in ("home", "away"):
        side_row = scores.get(side) or {}
        if normalize_matchup_team_name(side_row.get("team") or "") == normalize_matchup_team_name(opponent):
            rows = side_row.get("innings") or []
            break
    return {
        parse_int(row.get("inning")): parse_int(row.get("runs"))
        for row in rows
        if parse_int(row.get("inning")) in INNING_SLOTS and row.get("runs") is not None
    }


def allocate_inning_runs(candidate_runs: dict[int, int], pitcher_runs: int) -> dict[int, int]:
    pitcher_runs = max(parse_int(pitcher_runs), 0)
    if pitcher_runs <= 0:
        return {inning: 0 for inning in candidate_runs}

    positive = {inning: max(parse_int(runs), 0) for inning, runs in candidate_runs.items() if parse_int(runs) > 0}
    total_candidates = sum(positive.values())
    if not positive:
        return {}
    if total_candidates == pitcher_runs:
        return positive
    if len(positive) == 1:
        inning = next(iter(positive))
        return {inning: pitcher_runs}

    allocations = {}
    fractions = []
    allocated = 0
    for inning, runs in positive.items():
        raw = (runs / total_candidates) * pitcher_runs
        whole = int(raw)
        allocations[inning] = whole
        allocated += whole
        fractions.append((raw - whole, inning))

    for _fraction, inning in sorted(fractions, reverse=True)[: max(pitcher_runs - allocated, 0)]:
        allocations[inning] += 1
    return allocations


def add_season_dashboard_entry(player_bucket: dict, entry: dict, decision_row: dict | None = None, game_context: dict | None = None) -> None:
    dashboard = entry.get("dashboard") or {}
    pitch_mix = dashboard.get("pitchMix") or []
    if not pitch_mix:
        return

    source = season_dashboard_source(player_bucket)
    source["hasData"] = True
    total_pitches = parse_int(dashboard.get("totalPitches")) or sum(parse_int(row.get("count")) for row in pitch_mix)
    source["totalPitches"] += total_pitches

    for pitch_type, color in (dashboard.get("pitchColors") or {}).items():
        if pitch_type and color:
            source["pitchColors"].setdefault(pitch_type, color)

    chase_baseline = parse_float((dashboard.get("metricBaselines") or {}).get("chase"))
    if chase_baseline is not None:
        source["metricBaselines"].setdefault("chase", chase_baseline)

    for row in pitch_mix:
        pitch_type = row.get("pitchType") or "-"
        add_serialized_stat_row(source["pitchTypes"][pitch_type], row)
        if row.get("color"):
            source["pitchColors"].setdefault(pitch_type, row["color"])

    pitch_rows_raw = entry.get("_pitchRows") or []
    for row in build_pitcher_batter_hand_rows(pitch_rows_raw):
        hand = row.get("label") or "-"
        add_serialized_stat_row(source["batterHands"][hand], row)

    inning_rows = ((dashboard.get("inningSummary") or {}).get("all") or dashboard.get("inningRows") or [])
    for row in inning_rows:
        inning = parse_int(row.get("inning"))
        if inning <= 0:
            continue
        add_serialized_stat_row(source["innings"][inning], row)

    decision_key = pitcher_decision_key(decision_row or {})
    pitcher_innings = pitcher_innings_from_rows(pitch_rows_raw)
    candidate_runs = {
        inning: runs
        for inning, runs in opponent_inning_scores(entry, game_context).items()
        if inning in pitcher_innings and runs > 0
    }
    for inning, runs in allocate_inning_runs(candidate_runs, parse_int((entry.get("statline") or {}).get("runs"))).items():
        source["inningRunsByDecision"][decision_key][inning] += runs

    for row in build_pitcher_inning_walk_rows(pitch_rows_raw):
        inning = parse_int(row.get("inning"))
        if inning <= 0:
            continue
        source["inningWalksByDecision"][decision_key][inning] += parse_int(row.get("walksAndHbp"))

    opponent = matchup_opponent_team(entry.get("team") or "", entry.get("matchup") or "")
    opponent_label = opponent or "-"
    opponent_bucket = source["opponents"].setdefault(
        opponent_label,
        build_pitcher_game_split_bucket(opponent_label, team_sort_key(opponent_label)[0]),
    )
    record_pitcher_game_split(opponent_bucket, entry)

    stadium_label = (game_context or {}).get("stadium") or "-"
    stadium_bucket = source["stadiums"].setdefault(stadium_label, build_pitcher_game_split_bucket(stadium_label, 0))
    record_pitcher_game_split(stadium_bucket, entry)

    for row in (dashboard.get("outcomes", {}).get("rows") or []):
        outcome_id = row.get("id") or row.get("label") or "-"
        source["outcomes"][outcome_id] += parse_int(row.get("count"))
        source["outcomeMeta"].setdefault(
            outcome_id,
            {
                "label": row.get("label") or outcome_id,
                "color": row.get("color") or PITCH_COLORS[len(source["outcomeMeta"]) % len(PITCH_COLORS)],
            },
        )

    finish = dashboard.get("finish") or {}
    source["finishTotal"] += parse_int(finish.get("total"))
    for row in finish.get("rows") or []:
        pitch_type = row.get("pitchType") or "-"
        bucket = source["finish"][pitch_type]
        bucket["count"] += parse_int(row.get("count"))
        bucket["looking"] += parse_int(row.get("looking"))
        bucket["swinging"] += parse_int(row.get("swinging"))
        if row.get("color"):
            source["pitchColors"].setdefault(pitch_type, row["color"])

    source["recentGames"].append(build_recent_pitcher_game_row(entry))


def build_recent_pitcher_game_row(entry: dict) -> dict:
    statline = entry.get("statline") or {}
    outs = innings_to_outs(statline.get("innings"))
    ip = outs_to_ip(outs)
    earned_runs = parse_int(statline.get("er"))
    game_era = 9 * earned_runs / ip if ip else None
    return {
        "date": entry.get("date") or "",
        "team": entry.get("team") or "",
        "matchup": entry.get("matchup") or "",
        "gameId": entry.get("gameId") or "",
        "order": parse_int(entry.get("order")),
        "innings": statline.get("innings") or outs_to_innings_notation(outs),
        "inningsOuts": outs,
        "pitches": parse_int(statline.get("pitches")),
        "batters": parse_int(statline.get("batters")),
        "hits": parse_int(statline.get("hits")),
        "homeRuns": parse_int(statline.get("hr")),
        "strikeouts": parse_int(statline.get("k")),
        "walks": parse_int(statline.get("bb")),
        "hitByPitch": parse_int(statline.get("hbp")),
        "runs": parse_int(statline.get("runs")),
        "earnedRuns": earned_runs,
        "gameEra": round_or_none(game_era, 2),
    }


def build_recent_batter_game_row(entry: dict) -> dict:
    statline = entry.get("statline") or {}
    dashboard = entry.get("dashboard") or {}
    at_bats = parse_int(statline.get("ab"))
    hits = parse_int(statline.get("hits"))
    walks = parse_int(statline.get("walks"))
    plate_appearances = len(dashboard.get("plateAppearances") or [])
    batting_average = hits / at_bats if at_bats else None
    on_base_denominator = at_bats + walks
    on_base_percentage = (hits + walks) / on_base_denominator if on_base_denominator else None
    return {
        "date": entry.get("date") or "",
        "team": entry.get("team") or "",
        "matchup": entry.get("matchup") or "",
        "gameId": entry.get("gameId") or "",
        "order": parse_int(entry.get("order")),
        "plateAppearances": plate_appearances,
        "atBats": at_bats,
        "hits": hits,
        "homeRuns": parse_int(statline.get("homeRuns")),
        "runsBattedIn": parse_int(statline.get("rbi")),
        "walks": walks,
        "strikeouts": parse_int(statline.get("strikeouts")),
        "battingAverage": round_or_none(batting_average, 3),
        "onBasePercentage": round_or_none(on_base_percentage, 3),
    }


def finalize_season_dashboard(player: dict) -> dict | None:
    source = player.get("_seasonDashboardSource")
    if not source or not source.get("hasData"):
        return None

    total_pitches = parse_int(source.get("totalPitches"))
    metric_baselines = source.get("metricBaselines") or {}
    chase_baseline = parse_float(metric_baselines.get("chase"))
    pitch_rows = []
    for idx, (pitch_type, stats) in enumerate(
        sorted(source["pitchTypes"].items(), key=lambda item: (-parse_int(item[1].get("count")), item[0]))
    ):
        row = serialize_annual_stat_bucket(stats, total_pitches, chase_baseline)
        row.update(
            {
                "pitchType": pitch_type,
                "color": source["pitchColors"].get(pitch_type) or PITCH_COLORS[idx % len(PITCH_COLORS)],
            }
        )
        pitch_rows.append(row)

    inning_rows = []
    for inning in INNING_SLOTS:
        row = serialize_annual_stat_bucket(source["innings"].get(inning, build_annual_stat_bucket()))
        row["inning"] = inning
        inning_rows.append(row)

    hand_order = {"右": 0, "左": 1, "-": 2}
    batter_hand_rows = []
    for hand, stats in sorted(source["batterHands"].items(), key=lambda item: (hand_order.get(item[0], 99), item[0])):
        row = serialize_annual_stat_bucket(stats, total_pitches)
        row["label"] = hand
        batter_hand_rows.append(row)

    opponent_rows = [
        finalize_pitcher_game_split_bucket(bucket)
        for bucket in sorted(source["opponents"].values(), key=lambda row: (row.get("order", 0), row.get("label") or ""))
    ]
    stadium_rows = [
        finalize_pitcher_game_split_bucket(bucket)
        for bucket in sorted(source["stadiums"].values(), key=lambda row: (row.get("label") or ""))
    ]

    inning_walk_rows = []
    for inning in INNING_SLOTS:
        win = parse_int(source["inningWalksByDecision"]["win"].get(inning))
        loss = parse_int(source["inningWalksByDecision"]["loss"].get(inning))
        no_decision = parse_int(source["inningWalksByDecision"]["noDecision"].get(inning))
        inning_walk_rows.append(
            {
                "inning": inning,
                "win": win,
                "loss": loss,
                "noDecision": no_decision,
                "total": win + loss + no_decision,
            }
        )

    inning_run_rows = []
    for inning in INNING_SLOTS:
        win = parse_int(source["inningRunsByDecision"]["win"].get(inning))
        loss = parse_int(source["inningRunsByDecision"]["loss"].get(inning))
        no_decision = parse_int(source["inningRunsByDecision"]["noDecision"].get(inning))
        inning_run_rows.append(
            {
                "inning": inning,
                "win": win,
                "loss": loss,
                "noDecision": no_decision,
                "total": win + loss + no_decision,
            }
        )

    outcome_total = sum(source["outcomes"].values())
    known_outcome_meta = {key: (label, color) for key, label, color in OUTCOME_META}
    outcome_ids = [key for key, _label, _color in OUTCOME_META]
    outcome_ids.extend(key for key in source["outcomes"] if key not in outcome_ids)
    outcome_rows = []
    for idx, outcome_id in enumerate(outcome_ids):
        count = parse_int(source["outcomes"].get(outcome_id))
        if outcome_id in known_outcome_meta:
            label, color = known_outcome_meta[outcome_id]
        else:
            meta = source["outcomeMeta"].get(outcome_id) or {}
            label = meta.get("label") or outcome_id
            color = meta.get("color") or PITCH_COLORS[idx % len(PITCH_COLORS)]
        outcome_rows.append(
            {
                "id": outcome_id,
                "label": label,
                "count": count,
                "ratio": round_or_none(count / outcome_total * 100, 1) if outcome_total else 0.0,
                "color": color,
            }
        )

    finish_total = parse_int(source.get("finishTotal"))
    finish_rows = []
    for idx, (pitch_type, stats) in enumerate(
        sorted(source["finish"].items(), key=lambda item: (-parse_int(item[1].get("count")), item[0]))
    ):
        count = parse_int(stats.get("count"))
        finish_rows.append(
            {
                "pitchType": pitch_type,
                "count": count,
                "ratio": round_or_none(count / finish_total * 100, 1) if finish_total else 0.0,
                "looking": parse_int(stats.get("looking")),
                "swinging": parse_int(stats.get("swinging")),
                "color": source["pitchColors"].get(pitch_type) or PITCH_COLORS[idx % len(PITCH_COLORS)],
            }
        )

    recent_games = sorted(
        source["recentGames"],
        key=lambda row: (row.get("date") or "", row.get("gameId") or "", -parse_int(row.get("order"))),
        reverse=True,
    )[:6]

    return {
        "totalPitches": total_pitches,
        "pitchMix": pitch_rows,
        "metricBaselines": {
            "chase": round_or_none(chase_baseline, 1),
            "chaseScope": "league",
        },
        "inningRows": inning_rows,
        "batterHandRows": batter_hand_rows,
        "opponentRows": opponent_rows,
        "stadiumRows": stadium_rows,
        "inningRunRows": inning_run_rows,
        "inningRunRowsAvailable": any(row["total"] > 0 for row in inning_run_rows),
        "inningWalkRows": inning_walk_rows,
        "outcomes": {
            "total": outcome_total,
            "rows": outcome_rows,
        },
        "finish": {
            "total": finish_total,
            "rows": finish_rows,
        },
        "recentGames": recent_games,
    }


def parse_speed_number(value) -> float | None:
    if value in (None, ""):
        return None
    text_value = str(value).strip().replace("km/h", "")
    return parse_float(text_value)


def matchup_opponent_team(team: str, matchup: str) -> str:
    home_team, away_team = parse_matchup_teams(matchup or "")
    normalized_team = normalize_team_name(team)
    if normalized_team == home_team:
        return away_team
    if normalized_team == away_team:
        return home_team
    return ""


def build_game_context_index(game_contexts: dict[str, dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for payload in game_contexts.values():
        for game in payload.get("games") or []:
            game_id = str(game.get("gameId") or "")
            if not game_id:
                continue
            index[game_id] = game
    return index


def context_intentional_walk_game_ids(game_contexts: dict[str, dict]) -> set[str]:
    game_ids: set[str] = set()
    for payload in game_contexts.values():
        for game in payload.get("games") or []:
            game_id = str(game.get("gameId") or "")
            if game_id and "intentionalWalks" in game:
                game_ids.add(game_id)
    return game_ids


def iter_context_intentional_walks(game_contexts: dict[str, dict]):
    for payload in game_contexts.values():
        for game in payload.get("games") or []:
            game_id = str(game.get("gameId") or "")
            if not game_id:
                continue
            date = str(game.get("date") or "")
            teams = ((game.get("intentionalWalks") or {}).get("teams") or {})
            for team_name, team_row in teams.items():
                batting_team = normalize_matchup_team_name(team_row.get("team") or team_name)
                for player_row in team_row.get("players") or []:
                    player_id = str(player_row.get("playerId") or "").strip()
                    player_name = str(player_row.get("player") or "").strip()
                    events = player_row.get("events") or []
                    if not events:
                        events = [
                            {"inning": None, "detail": detail}
                            for detail in (player_row.get("details") or [])
                        ]
                    if not events:
                        events = [
                            {"inning": None, "detail": ""}
                            for _ in range(parse_int(player_row.get("intentionalWalks")))
                        ]
                    for event in events:
                        yield {
                            "gameId": game_id,
                            "date": date,
                            "game": game,
                            "team": batting_team,
                            "player": player_name,
                            "playerId": player_id,
                            "inning": parse_int(event.get("inning")),
                            "detail": event.get("detail") or "",
                        }


def context_batter_bucket_key(event: dict) -> str:
    return event.get("playerId") or f"{event.get('team', '')}::{event.get('player', '')}"


def add_context_batter_intentional_walks(target: dict, game_contexts: dict[str, dict], monthly: bool = False) -> None:
    for event in iter_context_intentional_walks(game_contexts):
        year = str(event.get("date") or "")[:4]
        if not year:
            continue
        player_key = context_batter_bucket_key(event)
        if monthly:
            month = month_key_from_date(event.get("date"))
            if month:
                target[(year, player_key, month)] += 1
        else:
            target[(year, player_key)] += 1


def pa_index_half(value) -> str:
    text = str(value or "").strip()
    return text[2:3] if len(text) >= 3 and text[:3].isdigit() else ""


def context_batting_half(game: dict, batting_team: str) -> str:
    home_team = normalize_matchup_team_name(game.get("homeTeam") or "")
    away_team = normalize_matchup_team_name(game.get("awayTeam") or "")
    normalized_team = normalize_matchup_team_name(batting_team)
    if normalized_team == away_team:
        return "1"
    if normalized_team == home_team:
        return "2"
    return ""


def context_pitching_team(game: dict, batting_team: str) -> str:
    home_team = normalize_matchup_team_name(game.get("homeTeam") or "")
    away_team = normalize_matchup_team_name(game.get("awayTeam") or "")
    normalized_team = normalize_matchup_team_name(batting_team)
    if normalized_team == away_team:
        return home_team
    if normalized_team == home_team:
        return away_team
    return ""


def logged_pitch_row_walks(rows: list[dict]) -> int:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    total = 0
    for pitches in build_plate_appearances(rows).values():
        final = pitches[-1]
        if "四球" in normalize_result(final.get("result") or ""):
            total += 1
    return total


def pitcher_has_context_event_inning(entry: dict, event: dict) -> bool:
    inning = parse_int(event.get("inning"))
    if inning <= 0:
        return True
    batting_half = context_batting_half(event.get("game") or {}, event.get("team") or "")
    parse_inning = getattr(DASHBOARD, "parse_inning", lambda value: None)
    for row in entry.get("_pitchRows") or []:
        if parse_inning(row.get("pa_index")) != inning:
            continue
        if batting_half and pa_index_half(row.get("pa_index")) != batting_half:
            continue
        return True
    return False


def build_pitcher_context_intentional_walks(entries: list[dict], game_contexts: dict[str, dict]) -> dict[str, int]:
    by_game_team: dict[tuple[str, str], list[dict]] = defaultdict(list)
    surplus_by_entry: dict[str, int] = {}
    assigned: dict[str, int] = defaultdict(int)

    for entry in entries:
        game_id = str(entry.get("gameId") or "")
        team = normalize_matchup_team_name(entry.get("team") or "")
        if not game_id or not team:
            continue
        by_game_team[(game_id, team)].append(entry)
        official_walks = parse_int((entry.get("statline") or {}).get("bb"))
        surplus_by_entry[entry["id"]] = max(official_walks - logged_pitch_row_walks(entry.get("_pitchRows") or []), 0)

    for event in iter_context_intentional_walks(game_contexts):
        pitching_team = context_pitching_team(event.get("game") or {}, event.get("team") or "")
        candidates = [
            entry
            for entry in by_game_team.get((event["gameId"], pitching_team), [])
            if surplus_by_entry.get(entry["id"], 0) - assigned.get(entry["id"], 0) > 0
        ]
        inning_candidates = [entry for entry in candidates if pitcher_has_context_event_inning(entry, event)]
        selected = min(
            inning_candidates or candidates,
            key=lambda entry: (entry.get("order", 10**9), entry.get("player") or ""),
            default=None,
        )
        if selected:
            assigned[selected["id"]] += 1
    return dict(assigned)


def build_batter_split_bucket(label: str, order: int = 0) -> dict:
    return {
        "label": label,
        "order": order,
        "plateAppearances": 0,
        "atBats": 0,
        "hits": 0,
        "singles": 0,
        "doubles": 0,
        "triples": 0,
        "homeRuns": 0,
        "walks": 0,
        "hitByPitch": 0,
        "sacBunts": 0,
        "sacFlies": 0,
        "strikeouts": 0,
    }


def record_batter_plate_result(bucket: dict, result: str) -> None:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: False)
    classify_hit_type = getattr(DASHBOARD, "classify_hit_type", lambda value: None)
    classify_plate_appearance_result = getattr(DASHBOARD, "classify_plate_appearance_result", lambda value: None)

    primary = normalize_result(result or "")
    if not primary:
        return

    bucket["plateAppearances"] += 1
    if "四球" in primary:
        bucket["walks"] += 1
    if "死球" in primary:
        bucket["hitByPitch"] += 1
    if any(word in primary for word in ("空三振", "見三振", "バ三振", "振逃")):
        bucket["strikeouts"] += 1
    if primary.endswith("犠打"):
        bucket["sacBunts"] += 1
    if (not is_ab_result(primary)) and classify_plate_appearance_result(primary) == "flyballs":
        bucket["sacFlies"] += 1

    if not is_ab_result(primary):
        return

    bucket["atBats"] += 1
    hit_type = classify_hit_type(primary)
    if not hit_type:
        return
    bucket["hits"] += 1
    if hit_type == "home_runs":
        bucket["homeRuns"] += 1
    else:
        bucket[hit_type] += 1


def half_inning_key(value: str | None) -> str:
    text = str(value or "").strip()
    return text[:3] if len(text) >= 3 and text[:3].isdigit() else text


def force_batter_to_first(bases: list[bool]) -> list[bool]:
    first, second, third = bases
    return [True, first or second, third or (first and second)]


def advance_bases(bases: list[bool], count: int, batter_base: int | None = None) -> list[bool]:
    next_bases = [False, False, False]
    for index, occupied in enumerate(bases):
        if not occupied:
            continue
        next_index = index + count
        if next_index < 3:
            next_bases[next_index] = True
    if batter_base is not None and 0 <= batter_base < 3:
        next_bases[batter_base] = True
    return next_bases


def remove_lead_forced_runner(bases: list[bool]) -> list[bool]:
    next_bases = list(bases)
    for index in range(3):
        if next_bases[index]:
            next_bases[index] = False
            break
    return next_bases


def update_scoring_position_base_state(bases: list[bool], result: str | None) -> list[bool]:
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    classify_hit_type = getattr(DASHBOARD, "classify_hit_type", lambda value: None)

    primary = normalize_result(result or "")
    if not primary:
        return list(bases)

    hit_type = classify_hit_type(primary)
    if hit_type == "home_runs":
        return [False, False, False]
    if hit_type == "triples":
        return advance_bases(bases, 3, 2)
    if hit_type == "doubles":
        return advance_bases(bases, 2, 1)
    if hit_type == "singles":
        return advance_bases(bases, 1, 0)

    if "四球" in primary or "死球" in primary or "打撃妨害" in primary:
        return force_batter_to_first(bases)
    if "失" in primary or "野選" in primary or "振逃" in primary:
        return force_batter_to_first(bases)
    if "犠打" in primary:
        return advance_bases(bases, 1)
    if "犠飛" in primary:
        next_bases = list(bases)
        next_bases[2] = False
        return next_bases
    if "併打" in primary:
        return remove_lead_forced_runner(bases)
    return list(bases)


def build_scoring_position_by_pa(rows: list[dict]) -> dict[str, bool]:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    grouped_pas = build_plate_appearances(rows)
    ordered_pas = sorted(
        grouped_pas.values(),
        key=lambda pitches: (pa_index_sort_key(pitches[0].get("pa_index")), parse_int(pitches[0].get("seq"))),
    )
    base_state = [False, False, False]
    current_half = None
    scoring_position_by_pa: dict[str, bool] = {}

    for pitches in ordered_pas:
        if not pitches:
            continue
        final = pitches[-1]
        pa_index = str(final.get("pa_index") or "")
        half_key = half_inning_key(pa_index)
        if half_key != current_half:
            base_state = [False, False, False]
            current_half = half_key
        scoring_position_by_pa[pa_index] = bool(base_state[1] or base_state[2])
        base_state = update_scoring_position_base_state(base_state, final.get("result"))

    return scoring_position_by_pa


def build_scoring_position_statline(plate_rows: list[dict]) -> dict[str, int]:
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: False)
    is_hit = getattr(DASHBOARD, "is_hit", lambda value: False)
    stats = {"atBats": 0, "hits": 0}
    for plate in plate_rows:
        if not plate.get("scoringPosition"):
            continue
        result = plate.get("result") or ""
        if not is_ab_result(result):
            continue
        stats["atBats"] += 1
        if is_hit(result):
            stats["hits"] += 1
    return stats


def finalize_batter_split_bucket(bucket: dict) -> dict:
    total_bases = (
        bucket["singles"]
        + (2 * bucket["doubles"])
        + (3 * bucket["triples"])
        + (4 * bucket["homeRuns"])
    )
    avg = bucket["hits"] / bucket["atBats"] if bucket["atBats"] else None
    obp_denominator = bucket["atBats"] + bucket["walks"] + bucket["hitByPitch"] + bucket["sacFlies"]
    obp = (
        (bucket["hits"] + bucket["walks"] + bucket["hitByPitch"]) / obp_denominator
        if obp_denominator
        else None
    )
    slg = total_bases / bucket["atBats"] if bucket["atBats"] else None
    ops = (obp + slg) if obp is not None and slg is not None else None
    return {
        "label": bucket["label"],
        "plateAppearances": bucket["plateAppearances"],
        "atBats": bucket["atBats"],
        "hits": bucket["hits"],
        "singles": bucket["singles"],
        "doubles": bucket["doubles"],
        "triples": bucket["triples"],
        "homeRuns": bucket["homeRuns"],
        "walks": bucket["walks"],
        "hitByPitch": bucket["hitByPitch"],
        "sacBunts": bucket["sacBunts"],
        "sacFlies": bucket["sacFlies"],
        "strikeouts": bucket["strikeouts"],
        "battingAverage": round_or_none(avg, 3),
        "onBasePercentage": round_or_none(obp, 3),
        "sluggingPercentage": round_or_none(slg, 3),
        "ops": round_or_none(ops, 3),
    }


def build_batter_season_dashboard(
    batter_entries: list[dict],
    game_contexts: dict[str, dict],
) -> dict[tuple[str, str], dict]:
    game_context_index = build_game_context_index(game_contexts)
    dashboards: dict[tuple[str, str], dict] = {}

    def source_for(entry: dict) -> dict:
        year = (entry.get("date") or "")[:4]
        team = entry.get("team") or ""
        player_name = entry.get("player") or ""
        batter_id = entry.get("batterId") or ""
        bucket_key = (year, batter_id or f"{team}::{player_name}")
        source = dashboards.get(bucket_key)
        if source is None:
            source = {
                "totalPlateAppearances": 0,
                "byOpponent": {},
                "byStadium": {},
                "byPitchType": {},
                "byVelocity": {},
                "byPitcherHand": {},
                "byBattingOrder": {},
                "byPlateAppearance": {},
                "byStrikeCount": {},
                "recentGames": [],
            }
            dashboards[bucket_key] = source
        return source

    def add_to_group(groups: dict, key: str, label: str, order: int, result: str) -> None:
        if not label:
            label = "-"
        bucket = groups.setdefault(key or label, build_batter_split_bucket(label, order))
        record_batter_plate_result(bucket, result)

    for entry in batter_entries:
        year = (entry.get("date") or "")[:4]
        if not year:
            continue
        source = source_for(entry)
        team = entry.get("team") or ""
        opponent = matchup_opponent_team(team, entry.get("matchup") or "")
        game_context = game_context_index.get(str(entry.get("gameId") or "")) or {}
        stadium = game_context.get("stadium") or "-"
        batting_order = parse_int(entry.get("order"))
        order_label = f"{batting_order}番" if 1 <= batting_order <= 9 else "途中出場"

        source["recentGames"].append(build_recent_batter_game_row(entry))

        for plate_index, plate in enumerate(((entry.get("dashboard") or {}).get("plateAppearances") or []), start=1):
            result = plate.get("result") or ""
            if not result:
                continue
            source["totalPlateAppearances"] += 1
            speed = parse_speed_number(plate.get("speed"))
            velocity_label = "150km/h以上" if speed is not None and speed >= 150 else "150km/h未満"
            pitcher_hand = plate.get("pitcherHand") or "-"
            plate_label = "5打席目以上" if plate_index >= 5 else f"{plate_index}打席目"
            strike_count = parse_int(plate.get("strikes"))
            strike_label = f"{min(strike_count, 2)}ストライク"

            add_to_group(source["byOpponent"], opponent, opponent or "-", team_sort_key(opponent)[0], result)
            add_to_group(source["byStadium"], stadium, stadium, 0, result)
            add_to_group(source["byPitchType"], plate.get("pitchType") or "-", plate.get("pitchType") or "-", 0, result)
            add_to_group(source["byVelocity"], velocity_label, velocity_label, 0 if velocity_label == "150km/h以上" else 1, result)
            add_to_group(source["byPitcherHand"], pitcher_hand, pitcher_hand, 0 if pitcher_hand == "右" else 1, result)
            add_to_group(source["byBattingOrder"], order_label, order_label, batting_order if 1 <= batting_order <= 9 else 99, result)
            add_to_group(source["byPlateAppearance"], plate_label, plate_label, 5 if plate_index >= 5 else plate_index, result)
            add_to_group(source["byStrikeCount"], strike_label, strike_label, min(strike_count, 2), result)

    finalized: dict[tuple[str, str], dict] = {}
    for bucket_key, source in dashboards.items():
        dashboard = {"totalPlateAppearances": source["totalPlateAppearances"]}
        for key in (
            "byOpponent",
            "byStadium",
            "byPitchType",
            "byVelocity",
            "byPitcherHand",
            "byBattingOrder",
            "byPlateAppearance",
            "byStrikeCount",
        ):
            rows = sorted(source[key].values(), key=lambda row: (row["order"], row["label"]))
            dashboard[key] = [finalize_batter_split_bucket(row) for row in rows]
        dashboard["recentGames"] = sorted(
            source["recentGames"],
            key=lambda row: (row.get("date") or "", row.get("gameId") or "", -parse_int(row.get("order"))),
            reverse=True,
        )[:6]
        finalized[bucket_key] = dashboard
    return finalized


def build_player_totals(entries: list[dict], game_decisions: dict[str, dict], game_contexts: dict[str, dict]) -> dict:
    monthly_splits_by_player = build_pitcher_monthly_splits(entries, game_decisions, game_contexts)
    game_context_index = build_game_context_index(game_contexts)
    context_game_ids = context_intentional_walk_game_ids(game_contexts)
    context_intentional_walks_by_entry = build_pitcher_context_intentional_walks(entries, game_contexts)
    league_totals: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "games": 0,
            "outs": 0,
            "earnedRuns": 0,
            "homeRuns": 0,
            "walks": 0,
            "unintentionalWalks": 0,
            "intentionalWalks": 0,
            "hitByPitch": 0,
            "strikeouts": 0,
        }
    )
    players: dict[tuple[str, str], dict] = {}
    years = set()

    for entry in entries:
        statline = entry.get("statline") or {}
        dashboard = entry.get("dashboard") or {}
        year = str(entry.get("date", ""))[:4] or "unknown"
        league = entry.get("league") or team_league(entry.get("team", ""))
        pitcher_id = entry.get("pitcherId") or f"{entry.get('team', '')}::{entry.get('player', '')}"
        outs = innings_to_outs(statline.get("innings"))
        pitch_rows = dashboard.get("pitchMix") or []
        outcome_rows = {row.get("id"): parse_int(row.get("count")) for row in (dashboard.get("outcomes", {}).get("rows") or [])}
        if str(entry.get("gameId") or "") in context_game_ids:
            intentional_walks = max(parse_int(context_intentional_walks_by_entry.get(entry["id"])), 0)
        else:
            intentional_walks = max(parse_int(dashboard.get("intentionalWalks")), 0)
        sacrifice_flies = max(parse_int(dashboard.get("sacrificeFlies")), 0)
        unintentional_walks = max(parse_int(statline.get("bb")) - intentional_walks, 0)
        years.add(year)

        league_bucket = league_totals[(year, league)]
        league_bucket["games"] += 1
        league_bucket["outs"] += outs
        league_bucket["earnedRuns"] += parse_int(statline.get("er"))
        league_bucket["homeRuns"] += parse_int(statline.get("hr"))
        league_bucket["walks"] += parse_int(statline.get("bb"))
        league_bucket["unintentionalWalks"] += unintentional_walks
        league_bucket["intentionalWalks"] += intentional_walks
        league_bucket["hitByPitch"] += parse_int(statline.get("hbp"))
        league_bucket["strikeouts"] += parse_int(statline.get("k"))

        player_bucket = players.setdefault(
            (year, pitcher_id),
            {
                "year": year,
                "_bucketKey": pitcher_id,
                "pitcherId": entry.get("pitcherId") or "",
                "player": entry.get("player", ""),
                "league": league,
                "teams": [],
                "games": 0,
                "wins": 0,
                "losses": 0,
                "saves": 0,
                "holds": 0,
                "outs": 0,
                "batters": 0,
                "pitches": 0,
                "hits": 0,
                "homeRuns": 0,
                "strikeouts": 0,
                "walks": 0,
                "unintentionalWalks": 0,
                "intentionalWalks": 0,
                "hitByPitch": 0,
                "balks": 0,
                "runs": 0,
                "earnedRuns": 0,
                "atBats": 0,
                "singles": 0,
                "doubles": 0,
                "triples": 0,
                "grounders": 0,
                "flyBalls": 0,
                "swingMisses": 0,
                "lookingStrikeouts": 0,
                "swingingStrikeouts": 0,
                "sacrificeBunts": 0,
                "sacrificeFlies": 0,
                "interference": 0,
                "battingAverageAllowedOverride": None,
                "groundOutRateOverride": None,
                "flyOutRateOverride": None,
                "hasPitchCount": False,
            },
        )

        decision_row = resolve_game_decision(entry, game_decisions)
        game_context = game_context_index.get(str(entry.get("gameId") or "")) or {}
        if entry.get("team") and entry["team"] not in player_bucket["teams"]:
            player_bucket["teams"].append(entry["team"])
        add_season_dashboard_entry(player_bucket, entry, decision_row, game_context)

        player_bucket["games"] += 1
        player_bucket["wins"] += parse_int(decision_row.get("wins"))
        player_bucket["losses"] += parse_int(decision_row.get("losses"))
        player_bucket["saves"] += parse_int(decision_row.get("saves"))
        player_bucket["holds"] += parse_int(decision_row.get("holds"))
        player_bucket["outs"] += outs
        player_bucket["batters"] += parse_int(statline.get("batters"))
        pitch_count = parse_int(statline.get("pitches"))
        player_bucket["pitches"] += pitch_count
        player_bucket["hasPitchCount"] = player_bucket["hasPitchCount"] or pitch_count > 0
        player_bucket["hits"] += parse_int(statline.get("hits"))
        player_bucket["homeRuns"] += parse_int(statline.get("hr"))
        player_bucket["strikeouts"] += parse_int(statline.get("k"))
        player_bucket["walks"] += parse_int(statline.get("bb"))
        player_bucket["unintentionalWalks"] += unintentional_walks
        player_bucket["intentionalWalks"] += intentional_walks
        player_bucket["hitByPitch"] += parse_int(statline.get("hbp"))
        player_bucket["balks"] += parse_int(statline.get("balk"))
        player_bucket["runs"] += parse_int(statline.get("runs"))
        player_bucket["earnedRuns"] += parse_int(statline.get("er"))
        player_bucket["atBats"] += sum(parse_int(row.get("atBats")) for row in pitch_rows)
        player_bucket["singles"] += sum(parse_int(row.get("singles")) for row in pitch_rows)
        player_bucket["doubles"] += sum(parse_int(row.get("doubles")) for row in pitch_rows)
        player_bucket["triples"] += sum(parse_int(row.get("triples")) for row in pitch_rows)
        player_bucket["grounders"] += sum(parse_int(row.get("grounders")) for row in pitch_rows)
        player_bucket["flyBalls"] += sum(parse_int(row.get("flyBalls")) for row in pitch_rows)
        player_bucket["swingMisses"] += sum(parse_int(row.get("whiffCount")) for row in pitch_rows)
        player_bucket["lookingStrikeouts"] += outcome_rows.get("lookingStrikeouts", 0)
        player_bucket["swingingStrikeouts"] += outcome_rows.get("swingingStrikeouts", 0)
        player_bucket["sacrificeBunts"] += outcome_rows.get("sacrificeBunts", 0)
        player_bucket["sacrificeFlies"] += sacrifice_flies
        player_bucket["interference"] += outcome_rows.get("interference", 0)

    raw_out_rate_index = load_raw_out_rate_index(years)
    for year, row in load_raw_pitcher_stat_rows(years):
        player_name = str(row.get("選手名") or "").strip()
        team = normalize_source_team_name(row.get("チーム名") or row.get("チームコード") or "")
        if not player_name or not team:
            continue
        league = team_league(team)
        outs = parse_int(row.get("投球回_アウト数")) or innings_to_outs(row.get("投球回"))
        walks = parse_int(row.get("与四球"))
        intentional_walks = parse_int(row.get("敬遠"))
        unintentional_walks = max(walks - intentional_walks, 0)
        years.add(year)

        league_bucket = league_totals[(year, league)]
        league_bucket["games"] += parse_int(row.get("試合"))
        league_bucket["outs"] += outs
        league_bucket["earnedRuns"] += parse_int(row.get("自責点"))
        league_bucket["homeRuns"] += parse_int(row.get("被本塁打"))
        league_bucket["walks"] += walks
        league_bucket["unintentionalWalks"] += unintentional_walks
        league_bucket["intentionalWalks"] += intentional_walks
        league_bucket["hitByPitch"] += parse_int(row.get("与死球"))
        league_bucket["strikeouts"] += parse_int(row.get("奪三振"))

        bucket_key = (year, f"{team}::{player_name}")
        player_bucket = players.setdefault(
            bucket_key,
            {
                "year": year,
                "_bucketKey": bucket_key[1],
                "pitcherId": "",
                "player": player_name,
                "league": league,
                "teams": [],
                "games": 0,
                "wins": 0,
                "losses": 0,
                "saves": 0,
                "holds": 0,
                "outs": 0,
                "batters": 0,
                "pitches": 0,
                "hits": 0,
                "homeRuns": 0,
                "strikeouts": 0,
                "walks": 0,
                "unintentionalWalks": 0,
                "intentionalWalks": 0,
                "hitByPitch": 0,
                "balks": 0,
                "runs": 0,
                "earnedRuns": 0,
                "atBats": 0,
                "singles": 0,
                "doubles": 0,
                "triples": 0,
                "grounders": 0,
                "flyBalls": 0,
                "swingMisses": 0,
                "lookingStrikeouts": 0,
                "swingingStrikeouts": 0,
                "sacrificeBunts": 0,
                "sacrificeFlies": 0,
                "interference": 0,
                "battingAverageAllowedOverride": None,
                "groundOutRateOverride": None,
                "flyOutRateOverride": None,
                "hasPitchCount": False,
            },
        )
        if team not in player_bucket["teams"]:
            player_bucket["teams"].append(team)

        player_bucket["games"] += parse_int(row.get("試合"))
        player_bucket["wins"] += parse_int(row.get("勝利"))
        player_bucket["losses"] += parse_int(row.get("敗北"))
        player_bucket["saves"] += parse_int(row.get("セーブ"))
        player_bucket["holds"] += parse_int(row.get("ホールド"))
        player_bucket["outs"] += outs
        player_bucket["batters"] += parse_int(row.get("打者"))
        player_bucket["hits"] += parse_int(row.get("被安打"))
        player_bucket["homeRuns"] += parse_int(row.get("被本塁打"))
        player_bucket["strikeouts"] += parse_int(row.get("奪三振"))
        player_bucket["walks"] += walks
        player_bucket["unintentionalWalks"] += unintentional_walks
        player_bucket["intentionalWalks"] += intentional_walks
        player_bucket["hitByPitch"] += parse_int(row.get("与死球"))
        player_bucket["balks"] += parse_int(row.get("ボーク"))
        player_bucket["runs"] += parse_int(row.get("失点"))
        player_bucket["earnedRuns"] += parse_int(row.get("自責点"))
        player_bucket["atBats"] += raw_pitcher_at_bats(row)
        batting_average_allowed = parse_float(row.get("被打率"))
        if batting_average_allowed is not None:
            player_bucket["battingAverageAllowedOverride"] = batting_average_allowed
        out_rate_override = lookup_out_rate_override(
            raw_out_rate_index.get(year, {}),
            player_name,
            str(row.get("背番号") or ""),
            row.get("チーム名") or row.get("チームコード") or "",
        )
        if out_rate_override:
            if out_rate_override.get("groundOutRate") is not None:
                player_bucket["groundOutRateOverride"] = out_rate_override["groundOutRate"]
            if out_rate_override.get("flyOutRate") is not None:
                player_bucket["flyOutRateOverride"] = out_rate_override["flyOutRate"]

    league_rows = []
    league_constants: dict[tuple[str, str], float | None] = {}
    for (year, league), stats in sorted(league_totals.items()):
        ip = outs_to_ip(stats["outs"])
        era = 9 * stats["earnedRuns"] / ip if ip else None
        component = (
            ((13 * stats["homeRuns"]) + (3 * (stats["unintentionalWalks"] + stats["hitByPitch"])) - (2 * stats["strikeouts"])) / ip
            if ip
            else None
        )
        constant = (era - component) if era is not None and component is not None else None
        league_constants[(year, league)] = constant
        league_rows.append(
            {
                "year": year,
                "league": league,
                "games": stats["games"],
                "innings": outs_to_innings_notation(stats["outs"]),
                "inningsOuts": stats["outs"],
                "earnedRuns": stats["earnedRuns"],
                "homeRuns": stats["homeRuns"],
                "walks": stats["walks"],
                "unintentionalWalks": stats["unintentionalWalks"],
                "intentionalWalks": stats["intentionalWalks"],
                "hitByPitch": stats["hitByPitch"],
                "strikeouts": stats["strikeouts"],
                "era": round_or_none(era, 2),
                "fipConstant": round_or_none(constant, 4),
            }
        )

    player_rows = []
    for player in players.values():
        outs = player["outs"]
        ip = outs_to_ip(outs)
        at_bats = player["atBats"]
        batting_average = player["hits"] / at_bats if at_bats else None
        batting_average = (
            player["battingAverageAllowedOverride"]
            if player.get("battingAverageAllowedOverride") is not None
            else batting_average
        )
        babip_denominator = player["atBats"] - player["strikeouts"] - player["homeRuns"] + player["sacrificeFlies"]
        babip_allowed = ((player["hits"] - player["homeRuns"]) / babip_denominator) if babip_denominator > 0 else None
        era = 9 * player["earnedRuns"] / ip if ip else None
        whip = (player["hits"] + player["walks"]) / ip if ip else None
        k_per_9 = 27 * player["strikeouts"] / outs if outs else None
        bb_per_9 = 27 * player["walks"] / outs if outs else None
        h_per_9 = 27 * player["hits"] / outs if outs else None
        hr_per_9 = 27 * player["homeRuns"] / outs if outs else None
        k_bb = player["strikeouts"] / player["walks"] if player["walks"] else None
        go_fo = player["grounders"] / player["flyBalls"] if player["flyBalls"] else None
        out_event_total = (
            player["grounders"]
            + player["flyBalls"]
            + player["lookingStrikeouts"]
            + player["swingingStrikeouts"]
            + player["sacrificeBunts"]
            + player["interference"]
        )
        ground_out_rate = player["grounders"] / out_event_total * 100 if out_event_total else None
        fly_out_rate = player["flyBalls"] / out_event_total * 100 if out_event_total else None
        if player.get("groundOutRateOverride") is not None:
            ground_out_rate = player["groundOutRateOverride"]
        if player.get("flyOutRateOverride") is not None:
            fly_out_rate = player["flyOutRateOverride"]
        if go_fo is None and ground_out_rate is not None and fly_out_rate not in (None, 0):
            go_fo = ground_out_rate / fly_out_rate
        whiff_rate = player["swingMisses"] / player["pitches"] * 100 if player.get("hasPitchCount") and player["pitches"] else None
        fip_constant = league_constants.get((player["year"], player["league"]))
        fip = (
            (((13 * player["homeRuns"]) + (3 * (player["unintentionalWalks"] + player["hitByPitch"])) - (2 * player["strikeouts"])) / ip) + fip_constant
            if ip and fip_constant is not None
            else None
        )

        teams = sorted(player["teams"], key=team_sort_key)
        player_row = {
            "year": player["year"],
            "pitcherId": player["pitcherId"],
            "player": player["player"],
            "team": teams[0] if len(teams) == 1 else " / ".join(teams),
            "teams": teams,
            "league": player["league"],
            "games": player["games"],
            "wins": player["wins"],
            "losses": player["losses"],
            "saves": player["saves"],
            "holds": player["holds"],
            "innings": outs_to_innings_notation(outs),
            "inningsOuts": outs,
            "batters": player["batters"],
            "pitches": player["pitches"] if player.get("hasPitchCount") else None,
            "hasPitchCount": bool(player.get("hasPitchCount")),
            "hits": player["hits"],
            "homeRuns": player["homeRuns"],
            "strikeouts": player["strikeouts"],
            "walks": player["walks"],
            "unintentionalWalks": player["unintentionalWalks"],
            "intentionalWalks": player["intentionalWalks"],
            "hitByPitch": player["hitByPitch"],
            "balks": player["balks"],
            "runs": player["runs"],
            "earnedRuns": player["earnedRuns"],
            "atBats": player["atBats"],
            "singles": player["singles"],
            "doubles": player["doubles"],
            "triples": player["triples"],
            "grounders": player["grounders"],
            "flyBalls": player["flyBalls"],
            "swingMisses": player["swingMisses"],
            "lookingStrikeouts": player["lookingStrikeouts"],
            "swingingStrikeouts": player["swingingStrikeouts"],
            "sacrificeBunts": player["sacrificeBunts"],
            "sacrificeFlies": player["sacrificeFlies"],
            "interference": player["interference"],
            "era": round_or_none(era, 2),
            "whip": round_or_none(whip, 2),
            "kPer9": round_or_none(k_per_9, 2),
            "bbPer9": round_or_none(bb_per_9, 2),
            "hPer9": round_or_none(h_per_9, 2),
            "hrPer9": round_or_none(hr_per_9, 2),
            "kBb": round_or_none(k_bb, 2),
            "fip": round_or_none(fip, 2),
            "fipConstant": round_or_none(fip_constant, 4),
            "battingAverageAllowed": round_or_none(batting_average, 3),
            "babipAllowed": round_or_none(babip_allowed, 3),
            "goFo": round_or_none(go_fo, 2),
            "groundOutRate": round_or_none(ground_out_rate, 1),
            "flyOutRate": round_or_none(fly_out_rate, 1),
            "whiffRate": round_or_none(whiff_rate, 1),
            "monthlySplits": monthly_splits_by_player.get((player["year"], player["_bucketKey"]), []),
        }
        season_dashboard = finalize_season_dashboard(player)
        if season_dashboard:
            player_row["seasonDashboard"] = season_dashboard
        player_rows.append(player_row)

    player_rows.sort(key=lambda row: (row["year"], team_sort_key(row["team"].split(" / ")[0]), row["player"]))
    return {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "generated/*/*/*-dashboard.json + summary/sportsnavi_game_context_*.json + 元データ/*_投手成績.csv",
        "years": sorted(years),
        "notes": {
            "fip": "FIP uses uBB derived from Sports Navi intentional-walk context when available.",
        },
        "leagueStats": league_rows,
        "players": player_rows,
    }


def build_batter_totals(
    entries: list[dict],
    batting_stats_by_game: dict[str, dict[str, dict]],
    batter_entries: list[dict],
    park_factors: dict,
    game_contexts: dict[str, dict],
) -> dict:
    monthly_splits_by_player = build_batter_monthly_splits(entries, batting_stats_by_game, batter_entries, park_factors, game_contexts)
    season_dashboards_by_player = build_batter_season_dashboard(batter_entries, game_contexts)
    is_ab_result = getattr(DASHBOARD, "is_ab_result", lambda value: True)
    classify_plate_appearance_result = getattr(DASHBOARD, "classify_plate_appearance_result", lambda value: None)
    players: dict[tuple[str, str], dict] = {}
    years: set[str] = set()
    game_dates: dict[str, str] = {}
    sacrifice_flies_by_player: dict[tuple[str, str], int] = defaultdict(int)
    intentional_walks_by_player: dict[tuple[str, str], int] = defaultdict(int)
    scoring_position_by_player: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"atBats": 0, "hits": 0})
    plate_discipline_by_player: dict[tuple[str, str], dict] = defaultdict(build_plate_discipline_bucket)
    context_game_ids = context_intentional_walk_game_ids(game_contexts)

    for entry in entries:
        game_id = entry.get("gameId") or ""
        date = entry.get("date") or ""
        if game_id and date:
            game_dates.setdefault(game_id, date)

    for entry in batter_entries:
        year = (entry.get("date") or "")[:4]
        if not year:
            continue
        team = entry.get("team") or ""
        batter_id = entry.get("batterId") or ""
        player_name = entry.get("player") or ""
        bucket_key = (year, batter_id or f"{team}::{player_name}")
        plate_rows = ((entry.get("dashboard") or {}).get("plateAppearances") or [])
        discipline_bucket = plate_discipline_by_player[bucket_key]
        for plate in plate_rows:
            for point in plate.get("points") or []:
                record_plate_discipline_pitch(discipline_bucket, point)
        sacrifice_flies_by_player[bucket_key] += sum(
            1
            for plate in plate_rows
            if (plate.get("result") or "")
            and not is_ab_result(plate.get("result") or "")
            and classify_plate_appearance_result(plate.get("result") or "") == "flyballs"
        )
        if str(entry.get("gameId") or "") not in context_game_ids:
            intentional_walks_by_player[bucket_key] += sum(
                1 for plate in plate_rows if is_intentional_walk_text(plate.get("result"))
            )
        scoring_position_stats = build_scoring_position_statline(plate_rows)
        scoring_position_bucket = scoring_position_by_player[bucket_key]
        scoring_position_bucket["atBats"] += scoring_position_stats["atBats"]
        scoring_position_bucket["hits"] += scoring_position_stats["hits"]

    add_context_batter_intentional_walks(intentional_walks_by_player, game_contexts)

    for game_id, teams in batting_stats_by_game.items():
        date = game_dates.get(game_id, "")
        year = date[:4]
        if not year:
            continue
        years.add(year)
        for team, rows in teams.items():
            league = team_league(team)
            for key, stats in rows.items():
                if key != (stats.get("playerId") or stats.get("player")):
                    continue
                batter_id = stats.get("playerId") or ""
                player_name = stats.get("player") or ""
                bucket_key = (year, batter_id or f"{team}::{player_name}")
                bucket = players.setdefault(
                    bucket_key,
                    {
                        "year": year,
                        "batterId": batter_id,
                        "player": player_name,
                        "_bucketKey": bucket_key,
                        "teams": set(),
                        "league": league,
                        "games": 0,
                        "plateAppearances": 0,
                        "atBats": 0,
                        "runs": 0,
                        "hits": 0,
                        "singles": 0,
                        "doubles": 0,
                        "triples": 0,
                        "homeRuns": 0,
                        "runsBattedIn": 0,
                        "walks": 0,
                        "unintentionalWalks": 0,
                        "intentionalWalks": 0,
                        "hitByPitch": 0,
                        "sacBunts": 0,
                        "sacFlies": 0,
                        "steals": 0,
                        "strikeouts": 0,
                        "scoringPositionAtBats": 0,
                        "scoringPositionHits": 0,
                        "_plateAppearancesByTeam": {},
                    },
                )
                bucket["teams"].add(team)
                bucket["games"] += 1
                bucket["plateAppearances"] += parse_int(stats.get("plateAppearances"))
                bucket["atBats"] += parse_int(stats.get("ab"))
                bucket["runs"] += parse_int(stats.get("runs"))
                bucket["hits"] += parse_int(stats.get("hits"))
                bucket["singles"] += parse_int(stats.get("singles"))
                bucket["doubles"] += parse_int(stats.get("doubles"))
                bucket["triples"] += parse_int(stats.get("triples"))
                bucket["homeRuns"] += parse_int(stats.get("homeRuns"))
                bucket["runsBattedIn"] += parse_int(stats.get("rbi"))
                bucket["walks"] += parse_int(stats.get("walks"))
                bucket["hitByPitch"] += parse_int(stats.get("hitByPitch"))
                bucket["sacBunts"] += parse_int(stats.get("sacBunts"))
                bucket["steals"] += parse_int(stats.get("steals"))
                bucket["strikeouts"] += parse_int(stats.get("strikeouts"))
                bucket["_plateAppearancesByTeam"][team] = (
                    bucket["_plateAppearancesByTeam"].get(team, 0) + parse_int(stats.get("plateAppearances"))
                )

    for year, row in load_raw_batter_stat_rows(years):
        player_name = str(row.get("選手名") or "").strip()
        team = normalize_source_team_name(row.get("team") or "")
        if not player_name or not team:
            continue
        league = team_league(team)
        batter_id = ""
        bucket_key = (year, batter_id or f"{team}::{player_name}")
        hits = parse_int(row.get("安打"))
        doubles = parse_int(row.get("二塁打"))
        triples = parse_int(row.get("三塁打"))
        home_runs = parse_int(row.get("本塁打"))
        plate_appearances = parse_int(row.get("打席"))
        years.add(year)
        sacrifice_flies_by_player[bucket_key] += parse_int(row.get("犠飛"))
        intentional_walks_by_player[bucket_key] += parse_int(row.get("故意四"))
        bucket = players.setdefault(
            bucket_key,
            {
                "year": year,
                "batterId": batter_id,
                "player": player_name,
                "_bucketKey": bucket_key,
                "teams": set(),
                "league": league,
                "games": 0,
                "plateAppearances": 0,
                "atBats": 0,
                "runs": 0,
                "hits": 0,
                "singles": 0,
                "doubles": 0,
                "triples": 0,
                "homeRuns": 0,
                "runsBattedIn": 0,
                "walks": 0,
                "unintentionalWalks": 0,
                "intentionalWalks": 0,
                "hitByPitch": 0,
                "sacBunts": 0,
                "sacFlies": 0,
                "steals": 0,
                "strikeouts": 0,
                "scoringPositionAtBats": 0,
                "scoringPositionHits": 0,
                "_plateAppearancesByTeam": {},
            },
        )
        bucket["teams"].add(team)
        bucket["games"] += parse_int(row.get("試合"))
        bucket["plateAppearances"] += plate_appearances
        bucket["atBats"] += parse_int(row.get("打数"))
        bucket["runs"] += parse_int(row.get("得点"))
        bucket["hits"] += hits
        bucket["singles"] += max(hits - doubles - triples - home_runs, 0)
        bucket["doubles"] += doubles
        bucket["triples"] += triples
        bucket["homeRuns"] += home_runs
        bucket["runsBattedIn"] += parse_int(row.get("打点"))
        bucket["walks"] += parse_int(row.get("四球"))
        bucket["hitByPitch"] += parse_int(row.get("死球"))
        bucket["sacBunts"] += parse_int(row.get("犠打"))
        bucket["steals"] += parse_int(row.get("盗塁"))
        bucket["strikeouts"] += parse_int(row.get("三振"))
        bucket["_plateAppearancesByTeam"][team] = (
            bucket["_plateAppearancesByTeam"].get(team, 0) + plate_appearances
        )

    park_factor_index = build_park_factor_index(park_factors)
    finalized_players = []
    for player in players.values():
        teams = sorted(player["teams"], key=team_sort_key)
        player["teams"] = teams
        player["sacFlies"] = sacrifice_flies_by_player.get(player["_bucketKey"], 0)
        player["intentionalWalks"] = intentional_walks_by_player.get(player["_bucketKey"], 0)
        player["unintentionalWalks"] = max(player["walks"] - player["intentionalWalks"], 0)
        scoring_position_stats = scoring_position_by_player.get(player["_bucketKey"], {})
        player["scoringPositionAtBats"] = parse_int(scoring_position_stats.get("atBats"))
        player["scoringPositionHits"] = parse_int(scoring_position_stats.get("hits"))
        plate_discipline = finalize_plate_discipline_bucket(
            plate_discipline_by_player.get(player["_bucketKey"], build_plate_discipline_bucket())
        )
        player["ballZoneSwingRate"] = plate_discipline.get("chase")
        player["ballZonePitchCount"] = plate_discipline.get("outZoneCount", 0)
        player["ballZoneSwingCount"] = plate_discipline.get("outZoneSwingCount", 0)
        finalized_players.append(player)

    league_buckets: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "plateAppearances": 0,
            "runs": 0,
            "atBats": 0,
            "singles": 0,
            "doubles": 0,
            "triples": 0,
            "homeRuns": 0,
            "unintentionalWalks": 0,
            "hitByPitch": 0,
            "sacFlies": 0,
        }
    )
    for player in finalized_players:
        league_key = (player["year"], player["league"])
        bucket = league_buckets[league_key]
        bucket["plateAppearances"] += player["plateAppearances"]
        bucket["runs"] += player["runs"]
        bucket["atBats"] += player["atBats"]
        bucket["singles"] += player["singles"]
        bucket["doubles"] += player["doubles"]
        bucket["triples"] += player["triples"]
        bucket["homeRuns"] += player["homeRuns"]
        bucket["unintentionalWalks"] += player["unintentionalWalks"]
        bucket["hitByPitch"] += player["hitByPitch"]
        bucket["sacFlies"] += player["sacFlies"]

    league_contexts: dict[tuple[str, str], dict] = {}
    league_context_rows = []
    for (year, league), stats in sorted(league_buckets.items()):
        constants = get_woba_constants(year)
        league_woba = calculate_woba(stats, constants)
        league_runs_per_pa = (stats["runs"] / stats["plateAppearances"]) if stats["plateAppearances"] else None
        league_contexts[(year, league)] = {
            "woba": league_woba,
            "runsPerPlateAppearance": league_runs_per_pa,
            "wobaScale": constants.get("wOBAScale") if constants else None,
        }
        league_context_rows.append(
            {
                "year": year,
                "league": league,
                "plateAppearances": stats["plateAppearances"],
                "runs": stats["runs"],
                "runsPerPlateAppearance": round_or_none(league_runs_per_pa, 3),
                "woba": round_or_none(league_woba, 3),
                "wobaScale": constants.get("wOBAScale") if constants else None,
                "constantsYear": constants.get("constantsYear") if constants else None,
                "provisional": bool(constants.get("provisional")) if constants else False,
            }
        )

    rows = []
    for player in finalized_players:
        teams = player["teams"]
        total_bases = player["singles"] + player["doubles"] * 2 + player["triples"] * 3 + player["homeRuns"] * 4
        batting_average = player["hits"] / player["atBats"] if player["atBats"] else None
        scoring_position_batting_average = (
            player["scoringPositionHits"] / player["scoringPositionAtBats"]
            if player["scoringPositionAtBats"]
            else None
        )
        on_base_denominator = player["atBats"] + player["walks"] + player["hitByPitch"] + player["sacFlies"]
        on_base_percentage = (
            (player["hits"] + player["walks"] + player["hitByPitch"]) / on_base_denominator
            if on_base_denominator > 0
            else None
        )
        slugging = total_bases / player["atBats"] if player["atBats"] else None
        iso_discipline = (on_base_percentage - batting_average) if on_base_percentage is not None and batting_average is not None else None
        iso_power = (slugging - batting_average) if slugging is not None and batting_average is not None else None
        ops = (on_base_percentage + slugging) if on_base_percentage is not None and slugging is not None else None
        babip_denominator = player["atBats"] - player["strikeouts"] - player["homeRuns"] + player["sacFlies"]
        babip = (
            (player["hits"] - player["homeRuns"]) / babip_denominator
            if babip_denominator > 0
            else None
        )
        constants = get_woba_constants(player["year"])
        league_context = league_contexts.get((player["year"], player["league"])) or {}
        player_woba = calculate_woba(player, constants)
        raw_park_factor, effective_park_factor = weighted_park_factor(
            player["_plateAppearancesByTeam"],
            park_factor_index.get(player["year"], {}),
        )
        league_woba = league_context.get("woba")
        league_runs_per_pa = league_context.get("runsPerPlateAppearance")
        woba_scale = league_context.get("wobaScale") or (constants.get("wOBAScale") if constants else None)
        runs_above_average_per_pa = (
            (player_woba - league_woba) / woba_scale
            if player_woba is not None and league_woba is not None and woba_scale not in (None, 0)
            else None
        )
        wrc = (
            ((runs_above_average_per_pa + league_runs_per_pa) * player["plateAppearances"])
            if runs_above_average_per_pa is not None and league_runs_per_pa is not None and player["plateAppearances"] > 0
            else None
        )
        park_adjustment = (
            league_runs_per_pa - ((effective_park_factor / 100.0) * league_runs_per_pa)
            if league_runs_per_pa is not None and effective_park_factor is not None
            else None
        )
        wrc_plus = (
            ((((runs_above_average_per_pa + league_runs_per_pa) + park_adjustment) / league_runs_per_pa) * 100)
            if runs_above_average_per_pa is not None
            and league_runs_per_pa not in (None, 0)
            and park_adjustment is not None
            else None
        )
        player_row = {
            "year": player["year"],
            "batterId": player["batterId"],
            "player": player["player"],
            "team": teams[0] if len(teams) == 1 else " / ".join(teams),
            "teams": teams,
            "league": player["league"],
            "games": player["games"],
            "plateAppearances": player["plateAppearances"],
            "atBats": player["atBats"],
            "runs": player["runs"],
            "hits": player["hits"],
            "singles": player["singles"],
            "doubles": player["doubles"],
            "triples": player["triples"],
            "homeRuns": player["homeRuns"],
            "runsBattedIn": player["runsBattedIn"],
            "walks": player["walks"],
            "unintentionalWalks": player["unintentionalWalks"],
            "intentionalWalks": player["intentionalWalks"],
            "hitByPitch": player["hitByPitch"],
            "sacBunts": player["sacBunts"],
            "sacFlies": player["sacFlies"],
            "steals": player["steals"],
            "strikeouts": player["strikeouts"],
            "scoringPositionAtBats": player["scoringPositionAtBats"],
            "scoringPositionHits": player["scoringPositionHits"],
            "battingAverage": round_or_none(batting_average, 3),
            "scoringPositionBattingAverage": round_or_none(scoring_position_batting_average, 3),
            "ballZoneSwingRate": player.get("ballZoneSwingRate"),
            "ballZonePitchCount": player.get("ballZonePitchCount", 0),
            "ballZoneSwingCount": player.get("ballZoneSwingCount", 0),
            "onBasePercentage": round_or_none(on_base_percentage, 3),
            "isoDiscipline": round_or_none(iso_discipline, 3),
            "sluggingPercentage": round_or_none(slugging, 3),
            "isoPower": round_or_none(iso_power, 3),
            "babip": round_or_none(babip, 3),
            "ops": round_or_none(ops, 3),
            "wrc": round_or_none(wrc, 1),
            "wrcPlus": round_or_none(wrc_plus, 1),
            "parkFactor": round_or_none(raw_park_factor, 1),
            "effectiveParkFactor": round_or_none(effective_park_factor, 1),
            "monthlySplits": monthly_splits_by_player.get(player["_bucketKey"], []),
        }
        season_dashboard = season_dashboards_by_player.get(player["_bucketKey"])
        if season_dashboard:
            player_row["seasonDashboard"] = season_dashboard
        rows.append(player_row)

    rows.sort(key=lambda row: (row["year"], team_sort_key(row["team"].split(" / ")[0]), row["player"]))
    return {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "Sports Navi game batting tables and intentional-walk context for games present under generated/*/*/*-dashboard.json + 元データ/*_打撃成績.csv",
        "notes": {
            "uBB": "Unintentional walks are derived from Sports Navi intentional-walk context when available.",
            "obp": "OBP remains the official BB-based formula rather than a uBB-based variant.",
            "wrcPlus": "wRC+ は対象試合の league R/PA と team park factor の半分補正を使った暫定値です。",
        },
        "metricContexts": {
            "wobaConstants": [
                {
                    "year": year,
                    "constantsYear": (constants or {}).get("constantsYear"),
                    "source": (constants or {}).get("source"),
                    "provisional": bool((constants or {}).get("provisional")),
                    "wOBA": (constants or {}).get("wOBA"),
                    "wOBAScale": (constants or {}).get("wOBAScale"),
                    "wBB": (constants or {}).get("wBB"),
                    "wHBP": (constants or {}).get("wHBP"),
                    "w1B": (constants or {}).get("w1B"),
                    "w2B": (constants or {}).get("w2B"),
                    "w3B": (constants or {}).get("w3B"),
                    "wHR": (constants or {}).get("wHR"),
                    "denominator": (constants or {}).get("denominator"),
                    "games": (constants or {}).get("games"),
                    "parsedPlateAppearances": (constants or {}).get("parsedPlateAppearances"),
                    "eventCounts": (constants or {}).get("eventCounts"),
                }
                for year in sorted(years)
                for constants in [get_woba_constants(year)]
            ],
            "leagues": league_context_rows,
        },
        "years": sorted(years),
        "players": rows,
    }


def collect_batter_entries(batting_stats_by_game: dict[str, dict[str, dict]]) -> list[dict]:
    build_plate_appearances = getattr(DASHBOARD, "build_plate_appearances")
    normalize_result = getattr(DASHBOARD, "normalize_result", lambda value: (value or "").split("[", 1)[0].strip())
    parse_inning = getattr(DASHBOARD, "parse_inning", lambda value: None)
    advance_count = getattr(DASHBOARD, "advance_count", lambda balls, strikes, result: (balls, strikes))
    grouped_games: dict[tuple[str, str, str], dict] = {}
    entries: list[dict] = []

    if not GENERATED_DIR.exists():
        return []

    for team_dir in sorted(GENERATED_DIR.iterdir(), key=lambda path: team_sort_key(path.name)):
        if not team_dir.is_dir():
            continue
        pitcher_team = normalize_team_name(team_dir.name)
        for date_dir in sorted(team_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for json_path in sorted(date_dir.glob("*-dashboard.json")):
                payload = safe_load_json(json_path)
                if not payload:
                    continue
                prefix = json_path.name.replace("-dashboard.json", "")
                game_id = extract_game_id(prefix)
                if not game_id:
                    continue
                metadata = payload.get("metadata", {})
                matchup = metadata.get("matchup") or ""
                home_team, away_team = parse_matchup_teams(matchup)
                if pitcher_team == home_team:
                    batting_team = away_team
                elif pitcher_team == away_team:
                    batting_team = home_team
                else:
                    continue
                if not batting_team:
                    continue
                key = (batting_team, date_dir.name, game_id)
                bucket = grouped_games.setdefault(
                    key,
                    {
                        "team": batting_team,
                        "date": date_dir.name,
                        "gameId": game_id,
                        "matchup": matchup,
                        "dateLabel": metadata.get("date_jp") or date_dir.name,
                        "payloads": [],
                    },
                )
                bucket["payloads"].append(payload)

    for (team, date, game_id), game in grouped_games.items():
        official_stats = (batting_stats_by_game.get(game_id) or {}).get(team, {})
        game_rows: list[dict] = []
        for payload in game["payloads"]:
            game_rows.extend(payload.get("pitches") or [])
        game_rows.sort(key=lambda row: (pa_index_sort_key(row.get("pa_index")), parse_int(row.get("seq"))))
        scoring_position_by_pa = build_scoring_position_by_pa(game_rows)

        batter_rows: dict[str, list[dict]] = defaultdict(list)
        for row in game_rows:
            batter_key = str(row.get("batter_id") or "").strip() or (row.get("batter") or "").strip()
            if batter_key:
                batter_rows[batter_key].append(row)

        for key, rows in batter_rows.items():
            rows.sort(key=lambda row: (pa_index_sort_key(row.get("pa_index")), parse_int(row.get("seq"))))
            first = rows[0]
            batter_id = str(first.get("batter_id") or "").strip()
            batter_name = (first.get("batter") or "").strip()
            batter_hand = first.get("batter_hand") or ""
            official = official_stats.get(batter_id) or official_stats.get(batter_name) or {}
            pitch_mix, pitch_color_map = build_batter_pitch_mix(rows)
            grouped_pas = build_plate_appearances(rows)
            ordered_pas = sorted(
                grouped_pas.values(),
                key=lambda pitches: (pa_index_sort_key(pitches[0].get("pa_index")), parse_int(pitches[0].get("seq"))),
            )
            fallback_statline = build_batter_statline_from_pas(ordered_pas)
            plate_rows = []

            for index, pitches in enumerate(ordered_pas, start=1):
                final = pitches[-1]
                balls = 0
                strikes = 0
                for pitch in pitches[:-1]:
                    balls, strikes = advance_count(balls, strikes, pitch.get("result") or "")
                plate_row = {
                    "id": final.get("pa_index") or f"{batter_id or batter_name}-{index}",
                    "label": f"{index}打席目",
                    "inning": parse_inning(final.get("pa_index")),
                    "result": normalize_result(final.get("result") or ""),
                    "pitchType": final.get("pitchType") or "-",
                    "speed": final.get("speed") or "-",
                    "pitcher": final.get("pitcher") or "",
                    "pitcherHand": final.get("pitcher_hand") or "",
                    "pitchNo": parse_int(final.get("pitchNo")),
                    "balls": balls,
                    "strikes": strikes,
                    "batterHand": batter_hand,
                    "points": serialize_batter_plate_points(pitches, pitch_color_map),
                }
                if scoring_position_by_pa.get(str(final.get("pa_index") or "")):
                    plate_row["scoringPosition"] = True
                plate_rows.append(plate_row)

            statline = {
                "ab": official.get("ab", fallback_statline["ab"]),
                "hits": official.get("hits", fallback_statline["hits"]),
                "homeRuns": official.get("homeRuns", fallback_statline["homeRuns"]),
                "rbi": official.get("rbi", fallback_statline["rbi"]),
                "walks": official.get("walks", fallback_statline["walks"]),
                "strikeouts": official.get("strikeouts", fallback_statline["strikeouts"]),
            }

            entries.append(
                {
                    "id": f"{team}-{date}-{game_id}-{batter_id or key}",
                    "team": team,
                    "league": team_league(team),
                    "date": date,
                    "prefix": f"{game_id}-{batter_id or key}",
                    "gameId": game_id,
                    "title": official.get("player") or batter_name,
                    "player": official.get("player") or batter_name,
                    "batterId": batter_id,
                    "batterHand": batter_hand,
                    "matchup": game["matchup"],
                    "dateLabel": game["dateLabel"],
                    "order": official.get("order", 999),
                    "statline": statline,
                    "dashboard": {
                        "pitchMix": pitch_mix,
                        "pitchColors": pitch_color_map,
                        "plateAppearances": plate_rows,
                        "bounds": {
                            "width": HEATMAP_WIDTH,
                            "height": HEATMAP_HEIGHT,
                        },
                    },
                }
            )

    entries.sort(key=lambda item: (team_sort_key(item["team"]), item.get("order", 999), item["player"]))
    entries.sort(key=lambda item: item["date"], reverse=True)
    return entries


def collect_entries() -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}

    if not GENERATED_DIR.exists():
        return []

    for team_dir in sorted(GENERATED_DIR.iterdir(), key=lambda path: team_sort_key(path.name)):
        if not team_dir.is_dir():
            continue
        for date_dir in sorted(team_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for json_path in sorted(date_dir.glob("*-dashboard.json")):
                match = JSON_PATTERN.match(json_path.name)
                if not match:
                    continue
                prefix = match.group("prefix")
                team_name = normalize_team_name(team_dir.name)
                key = (team_name, date_dir.name, prefix)
                grouped.setdefault(
                    key,
                    {
                        "id": f"{team_name}-{date_dir.name}-{prefix}",
                        "team": team_name,
                        "date": date_dir.name,
                        "prefix": prefix,
                        "pages": {},
                    },
                )
            for png_path in sorted(date_dir.glob("*-dashboard-*.png")):
                match = PAGE_PATTERN.match(png_path.name)
                if not match:
                    continue
                prefix = match.group("prefix")
                page_no = int(match.group("page"))
                team_name = normalize_team_name(team_dir.name)
                key = (team_name, date_dir.name, prefix)
                entry = grouped.setdefault(
                    key,
                    {
                        "id": f"{team_name}-{date_dir.name}-{prefix}",
                        "team": team_name,
                        "date": date_dir.name,
                        "prefix": prefix,
                        "pages": {},
                    },
                )
                entry["pages"][page_no] = site_path(png_path)

    league_chase_baselines = build_league_chase_baselines(grouped)
    entries: list[dict] = []
    for (team, date, prefix), entry in grouped.items():
        json_path = GENERATED_DIR / team / date / f"{prefix}-dashboard.json"
        if not json_path.exists():
            continue
        payload = safe_load_json(json_path)
        if not payload:
            continue

        page_items = [{"page": page_no, "path": path} for page_no, path in sorted(entry["pages"].items())]
        title, matchup = infer_title(prefix, date, payload)
        statline = payload.get("statline", {})
        metadata = payload.get("metadata", {})
        pitcher_id = extract_pitcher_id(payload)
        league = team_league(team)
        dashboard = serialize_dashboard(payload, league_chase_baselines.get(league) or league_chase_baselines.get("NPB"))

        entries.append(
            {
                "id": entry["id"],
                "team": team,
                "league": league,
                "date": date,
                "prefix": prefix,
                "gameId": extract_game_id(prefix),
                "order": pitcher_appearance_order(payload),
                "title": title,
                "player": statline.get("player", "") or title,
                "pitcherId": pitcher_id,
                "matchup": metadata.get("matchup") or matchup,
                "dateLabel": metadata.get("date_jp") or date,
                "pages": page_items,
                "statline": {
                    "era": statline.get("era", ""),
                    "innings": statline.get("innings", ""),
                    "pitches": statline.get("pitches", ""),
                    "batters": statline.get("batters", ""),
                    "hits": statline.get("hits", ""),
                    "hr": statline.get("hr", ""),
                    "k": statline.get("k", ""),
                    "bb": statline.get("bb", ""),
                    "hbp": statline.get("hbp", ""),
                    "balk": statline.get("balk", ""),
                    "er": statline.get("er", ""),
                    "runs": statline.get("runs", ""),
                },
                "dashboard": dashboard,
                "_pitchRows": payload.get("pitches") or [],
            }
        )

    entries.sort(key=lambda item: (team_sort_key(item["team"]), item.get("gameId") or "", item.get("order", 10**9), item["player"]))
    entries.sort(key=lambda item: item["date"], reverse=True)
    return entries


def pitcher_manifest_detail_path(entry: dict) -> Path:
    return GENERATED_DIR / entry["team"] / entry["date"] / f"{entry['prefix']}{PITCHER_MANIFEST_DETAIL_SUFFIX}"


def pitcher_manifest_entry(entry: dict) -> dict:
    public_entry = {
        key: value
        for key, value in entry.items()
        if not key.startswith("_") and key != "dashboard"
    }
    dashboard = entry.get("dashboard") or {}
    public_entry["detailPath"] = site_path(pitcher_manifest_detail_path(entry))
    public_entry["dashboard"] = {"pitchMix": dashboard.get("pitchMix") or []}
    return public_entry


def write_pitcher_manifest_details(entries: list[dict]) -> None:
    for entry in entries:
        detail_path = pitcher_manifest_detail_path(entry)
        detail_path.write_text(
            json.dumps(
                {
                    "id": entry["id"],
                    "dashboard": entry.get("dashboard") or {},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def build_manifest(entries: list[dict], entry_serializer=None) -> dict:
    team_counts = Counter(entry["team"] for entry in entries)
    date_counts = Counter(entry["date"] for entry in entries)
    player_counts = Counter(entry["player"] for entry in entries if entry.get("player"))
    serialize_entry = entry_serializer or (lambda entry: {key: value for key, value in entry.items() if not key.startswith("_")})

    teams = [
        {
            "name": team,
            "count": team_counts.get(team, 0),
            "hasData": team_counts.get(team, 0) > 0,
        }
        for team in sorted(set(TEAM_ORDER) | set(team_counts), key=team_sort_key)
    ]

    dates = [{"date": date, "count": count} for date, count in sorted(date_counts.items(), reverse=True)]
    players = [{"name": name, "count": count} for name, count in sorted(player_counts.items())]

    return {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "generatedRoot": "../generated",
        "entryCount": len(entries),
        "teamCount": sum(1 for team in teams if team["hasData"]),
        "dateCount": len(dates),
        "teams": teams,
        "dates": dates,
        "players": players,
        "entries": [serialize_entry(entry) for entry in entries],
    }


def main() -> None:
    entries = collect_entries()
    manifest = build_manifest(entries, pitcher_manifest_entry)
    write_pitcher_manifest_details(entries)
    game_decisions = load_or_update_game_decisions(entries)
    batting_stats_by_game = load_or_update_game_batting_stats(entries)
    game_contexts = load_game_contexts()
    park_factors = build_park_factors(game_contexts)
    batter_entries = collect_batter_entries(batting_stats_by_game)
    batter_manifest = build_manifest(batter_entries)
    player_totals = build_player_totals(entries, game_decisions, game_contexts)
    batter_totals = build_batter_totals(entries, batting_stats_by_game, batter_entries, park_factors, game_contexts)
    MANIFEST_PATH.write_text(
        "window.PITCH_DASHBOARD_MANIFEST = "
        + json.dumps(manifest, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    BATTER_MANIFEST_PATH.write_text(
        "window.BATTER_GAME_MANIFEST = "
        + json.dumps(batter_manifest, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    PLAYER_TOTALS_PATH.write_text(
        json.dumps(player_totals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    BATTER_TOTALS_PATH.write_text(
        json.dumps(batter_totals, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    PARK_FACTORS_PATH.write_text(
        json.dumps(park_factors, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {MANIFEST_PATH}")
    print(f"batter manifest: {BATTER_MANIFEST_PATH}")
    print(f"player totals: {PLAYER_TOTALS_PATH}")
    print(f"batter totals: {BATTER_TOTALS_PATH}")
    print(f"park factors: {PARK_FACTORS_PATH}")
    print(f"entries: {manifest['entryCount']}")
    print(f"batter entries: {batter_manifest['entryCount']}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_DIR = ROOT / "summary"
CONTEXT_TEMPLATE = SUMMARY_DIR / "sportsnavi_game_context_{season}.json"
EVENTS_TEMPLATE = SUMMARY_DIR / "sportsnavi_woba_events_{season}.json"
CONSTANTS_PATH = SUMMARY_DIR / "woba_constants.json"
TEXT_URL = "https://baseball.yahoo.co.jp/npb/game/{game_id}/text"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}

TEAM_ALIASES = {
    "福岡ソフトバンクホークス": "ソフトバンク",
    "北海道日本ハムファイターズ": "日本ハム",
    "東北楽天ゴールデンイーグルス": "東北楽天",
    "千葉ロッテマリーンズ": "ロッテ",
    "埼玉西武ライオンズ": "西武",
    "オリックス・バファローズ": "オリックス",
    "読売ジャイアンツ": "巨人",
    "阪神タイガース": "阪神",
    "横浜DeNAベイスターズ": "DeNA",
    "広島東洋カープ": "広島",
    "東京ヤクルトスワローズ": "ヤクルト",
    "中日ドラゴンズ": "中日",
    "楽天": "東北楽天",
}

TEAM_SCORE_LABELS = {
    "ソフトバンク": "ソ",
    "日本ハム": "日",
    "東北楽天": "楽",
    "ロッテ": "ロ",
    "西武": "西",
    "オリックス": "オ",
    "巨人": "巨",
    "阪神": "神",
    "DeNA": "デ",
    "広島": "広",
    "ヤクルト": "ヤ",
    "中日": "中",
}

EVENT_CATEGORIES = ("uBB", "HBP", "1B", "2B", "3B", "HR")
DENOMINATOR_EVENTS = set(EVENT_CATEGORIES) | {"OUT", "SF", "ROE"}


def text(node) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True).replace("\xa0", " ")


def parse_int(value) -> int:
    if value in (None, ""):
        return 0
    normalized = str(value).strip().replace(",", "")
    if not normalized or normalized == "-":
        return 0
    try:
        return int(float(normalized))
    except Exception:
        return 0


def normalize_team_name(team: str) -> str:
    normalized = (team or "").strip()
    return TEAM_ALIASES.get(normalized, normalized)


def game_side_team(game: dict, half: str) -> str:
    return normalize_team_name(game.get("awayTeam") if half == "表" else game.get("homeTeam"))


def score_label(team: str) -> str:
    return TEAM_SCORE_LABELS.get(normalize_team_name(team), normalize_team_name(team)[:1])


def parse_inning_head(label: str) -> tuple[int, str] | None:
    match = re.search(r"(\d+)回([表裏])", label or "")
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def parse_player_id(href: str) -> str:
    match = re.search(r"/npb/player/(\d+)/", href or "")
    return match.group(1) if match else ""


def bases_from_text(value: str, default: tuple[bool, bool, bool] | None = None) -> tuple[bool, bool, bool] | None:
    source = value or ""
    candidates: list[tuple[int, tuple[bool, bool, bool]]] = []
    for match in re.finditer(r"走者なし", source):
        candidates.append((match.start(), (False, False, False)))
    for match in re.finditer(r"満塁", source):
        candidates.append((match.start(), (True, True, True)))
    for match in re.finditer(r"(?<!が空いているため)(?<!が空いている)(?<!走者\s)([一二三]{1,3})塁", source):
        token = match.group(1)
        candidates.append((match.start(), ("一" in token, "二" in token, "三" in token)))
    if not candidates:
        return default
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def outs_from_text(value: str, default: int | None = None) -> int | None:
    source = value or ""
    candidates: list[tuple[int, int]] = []
    for token, outs in (
        ("無死", 0),
        ("ノーアウト", 0),
        ("一死", 1),
        ("二死", 2),
        ("0アウト", 0),
        ("1アウト", 1),
        ("2アウト", 2),
        ("3アウト", 3),
    ):
        for match in re.finditer(re.escape(token), source):
            candidates.append((match.start(), outs))
    if not candidates:
        return default
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def parse_state(value: str, current: tuple[int, tuple[bool, bool, bool]] | None = None) -> tuple[int, tuple[bool, bool, bool]] | None:
    default_outs = current[0] if current else None
    default_bases = current[1] if current else None
    outs = outs_from_text(value, default_outs)
    bases = bases_from_text(value, default_bases)
    if outs is None and bases is None:
        return None
    if outs == 3:
        return 3, (False, False, False)
    return outs if outs is not None else 0, bases if bases is not None else (False, False, False)


def state_key(state: tuple[int, tuple[bool, bool, bool]]) -> str:
    outs, bases = state
    return f"{outs}:{''.join('1' if base else '0' for base in bases)}"


def parse_score(text_value: str, home_team: str, away_team: str) -> tuple[int, int] | None:
    home_label = score_label(home_team)
    away_label = score_label(away_team)
    matches = list(re.finditer(r"([^\s\d]{1,4})\s+(\d{1,2})-(\d{1,2})\s+([^\s\d]{1,4})", text_value or ""))
    if not matches:
        return None
    left, left_score, right_score, right = matches[-1].groups()
    left_score_int = int(left_score)
    right_score_int = int(right_score)
    if left == home_label or right == away_label:
        return left_score_int, right_score_int
    if left == away_label or right == home_label:
        return right_score_int, left_score_int
    return left_score_int, right_score_int


def classify_event(result: str) -> str:
    value = result or ""
    if "敬遠" in value or "故意四" in value:
        return "IBB"
    if "死球" in value or "デッドボール" in value:
        return "HBP"
    if "フォアボール" in value or "四球" in value:
        return "uBB"
    if "ホームラン" in value or "本塁打" in value or re.search(r"[左右中]本", value):
        return "HR"
    if "三塁打" in value or "スリーベース" in value or re.search(r"[左右中]３", value):
        return "3B"
    if "二塁打" in value or "ツーベース" in value or re.search(r"[左右中]２", value):
        return "2B"
    if "ヒット" in value or "安打" in value or re.search(r"[左右中投捕一二三遊]安", value):
        return "1B"
    if "犠牲フライ" in value or "犠飛" in value:
        return "SF"
    if "送りバント" in value or "犠打" in value or "バントを成功" in value:
        return "SH"
    if "失策" in value or "エラー" in value or "悪送球" in value:
        return "ROE"
    if any(term in value for term in ("三振", "ゴロ", "フライ", "ライナー", "併殺", "併打", "邪飛", "アウト")):
        return "OUT"
    return "OTHER"


def advance_score_from_text(
    text_value: str,
    home_team: str,
    away_team: str,
    current_score: dict[str, int],
    batting_side: str,
) -> int:
    parsed = parse_score(text_value, home_team, away_team)
    if parsed is None:
        return 0
    previous = current_score["away" if batting_side == "away" else "home"]
    home_score, away_score = parsed
    current_score["home"] = home_score
    current_score["away"] = away_score
    latest = current_score["away" if batting_side == "away" else "home"]
    return max(latest - previous, 0)


def post_state_from_result(result: str, pre_state: tuple[int, tuple[bool, bool, bool]], event_type: str) -> tuple[int, tuple[bool, bool, bool]]:
    parsed = parse_state(result, pre_state)
    if parsed:
        return parsed
    outs, bases = pre_state
    if event_type == "HR":
        return outs, (False, False, False)
    if event_type in {"uBB", "IBB", "HBP"}:
        first, second, third = bases
        if first and second and third:
            return outs, (True, True, True)
        if first and second:
            return outs, (True, True, third)
        if first:
            return outs, (True, True, third)
        return outs, (True, second, third)
    if event_type == "1B":
        return outs, (True, False, False)
    if event_type == "2B":
        return outs, (False, True, False)
    if event_type == "3B":
        return outs, (False, False, True)
    if event_type in {"OUT", "SF", "SH"}:
        next_outs = min(outs + (2 if "併" in result else 1), 3)
        return next_outs, (False, False, False) if next_outs == 3 else bases
    return pre_state


def fetch_with_retry(session: requests.Session, url: str, attempts: int = 4, delay_seconds: float = 1.0) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error


def parse_game_text(game: dict, html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    home_team = normalize_team_name(game.get("homeTeam") or "")
    away_team = normalize_team_name(game.get("awayTeam") or "")
    current_score = {"home": 0, "away": 0}
    events: list[dict] = []

    for section in soup.select(".bb-liveText"):
        head = text(section.select_one(".bb-liveText__inning"))
        parsed_head = parse_inning_head(head)
        if not parsed_head:
            continue
        inning, half = parsed_head
        batting_side = "away" if half == "表" else "home"
        batting_team = game_side_team(game, half)
        half_events: list[dict] = []
        half_runs = 0

        for item in section.select(".bb-liveText__item"):
            batter_node = item.select_one(".bb-liveText__batter")
            if not batter_node:
                continue
            player_link = batter_node.select_one(".bb-liveText__player")
            if not player_link:
                continue
            batter_name = text(player_link)
            batter_id = parse_player_id(player_link.get("href", ""))
            order_label = text(batter_node.select_one(".bb-liveText__order"))
            pre_state_text = text(batter_node.select_one(".bb-liveText__state"))
            pre_state = parse_state(pre_state_text)
            if pre_state is None:
                continue

            summaries = [
                summary
                for summary in item.select(".bb-liveText__summary")
                if text(summary)
            ]
            if not summaries:
                continue
            final_index = len(summaries) - 1
            for index in range(len(summaries) - 1, -1, -1):
                classes = summaries[index].get("class") or []
                summary_text = text(summaries[index])
                if "bb-liveText__summary--change" in classes:
                    continue
                if any(skip in summary_text for skip in ("リクエスト", "リプレー検証", "コーチマウンド", "監督マウンド")):
                    continue
                final_index = index
                break

            current_state = pre_state
            runs_before = half_runs
            for summary in summaries[:final_index]:
                summary_text = text(summary)
                half_runs += advance_score_from_text(summary_text, home_team, away_team, current_score, batting_side)
                state_update = parse_state(summary_text, current_state)
                if state_update:
                    current_state = state_update
                    runs_before = half_runs

            final_text = text(summaries[final_index])
            event_type = classify_event(final_text)
            event_runs = advance_score_from_text(final_text, home_team, away_team, current_score, batting_side)
            half_runs += event_runs
            post_state = post_state_from_result(final_text, current_state, event_type)

            half_events.append(
                {
                    "gameId": str(game.get("gameId") or ""),
                    "date": game.get("date") or "",
                    "inning": inning,
                    "half": half,
                    "battingTeam": batting_team,
                    "batter": batter_name,
                    "batterId": batter_id,
                    "order": order_label,
                    "eventType": event_type,
                    "result": final_text,
                    "preState": state_key(current_state),
                    "postState": state_key(post_state),
                    "runsBefore": runs_before,
                    "runsOnPlay": event_runs,
                    "runsAfter": half_runs,
                }
            )

        for event in half_events:
            event["inningRuns"] = half_runs
        events.extend(half_events)

    return events


def build_run_expectancy(events: list[dict]) -> tuple[dict[str, float], dict[str, int]]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        state = event["preState"]
        if state.startswith("3:"):
            continue
        future_runs = event["inningRuns"] - event["runsBefore"]
        totals[state] += future_runs
        counts[state] += 1
    return {state: totals[state] / counts[state] for state in counts}, dict(counts)


def event_run_value(event: dict, run_expectancy: dict[str, float]) -> float | None:
    pre = run_expectancy.get(event["preState"])
    if pre is None:
        return None
    post = 0.0 if event["postState"].startswith("3:") else run_expectancy.get(event["postState"])
    if post is None:
        return None
    return event["runsOnPlay"] + post - pre


def calculate_constants_for_year(year: str, events: list[dict]) -> dict:
    run_expectancy, state_counts = build_run_expectancy(events)
    values: dict[str, list[float]] = defaultdict(list)
    counts = Counter()

    for event in events:
        event_type = event["eventType"]
        counts[event_type] += 1
        value = event_run_value(event, run_expectancy)
        if value is not None:
            values[event_type].append(value)

    out_values = values.get("OUT") or []
    out_value = sum(out_values) / len(out_values) if out_values else -0.27
    raw_weights: dict[str, float] = {}
    run_values: dict[str, float] = {"OUT": out_value}
    for category in EVENT_CATEGORIES:
        category_values = values.get(category) or []
        average = sum(category_values) / len(category_values) if category_values else 0.0
        run_values[category] = average
        raw_weights[category] = max(average - out_value, 0.0)

    denominator = sum(counts[event] for event in DENOMINATOR_EVENTS)
    on_base_numerator = counts["1B"] + counts["2B"] + counts["3B"] + counts["HR"] + counts["uBB"] + counts["HBP"]
    league_obp = on_base_numerator / denominator if denominator else 0.0
    unscaled_woba = (
        sum(raw_weights[category] * counts[category] for category in EVENT_CATEGORIES) / denominator
        if denominator
        else 0.0
    )
    woba_scale = league_obp / unscaled_woba if unscaled_woba else 1.0
    weights = {category: raw_weights[category] * woba_scale for category in EVENT_CATEGORIES}
    league_woba = (
        sum(weights[category] * counts[category] for category in EVENT_CATEGORIES) / denominator
        if denominator
        else None
    )

    return {
        "constantsYear": year,
        "source": f"Sports Navi text pages through {max((event['date'] for event in events), default='')}",
        "provisional": True,
        "wOBA": round(league_woba, 3) if league_woba is not None else None,
        "wOBAScale": round(woba_scale, 3),
        "wBB": round(weights["uBB"], 3),
        "wHBP": round(weights["HBP"], 3),
        "w1B": round(weights["1B"], 3),
        "w2B": round(weights["2B"], 3),
        "w3B": round(weights["3B"], 3),
        "wHR": round(weights["HR"], 3),
        "eventCounts": dict(sorted(counts.items())),
        "denominator": denominator,
        "leagueObp": round(league_obp, 3),
        "rawRunValues": {key: round(value, 4) for key, value in sorted(run_values.items())},
        "rawWeights": {key: round(value, 4) for key, value in sorted(raw_weights.items())},
        "stateSampleCounts": dict(sorted(state_counts.items())),
    }


def build_for_season(season: str, through_date: str | None = None, delay_seconds: float = 0.2) -> tuple[dict, list[dict]]:
    context_path = Path(str(CONTEXT_TEMPLATE).format(season=season))
    context = json.loads(context_path.read_text(encoding="utf-8"))
    games = [
        game
        for game in context.get("games") or []
        if str(game.get("date") or "").startswith(season)
        and (not through_date or str(game.get("date") or "") <= through_date)
    ]

    session = requests.Session()
    events: list[dict] = []
    fetch_errors: list[dict] = []
    for index, game in enumerate(games, start=1):
        game_id = str(game.get("gameId") or "")
        try:
            html = fetch_with_retry(session, TEXT_URL.format(game_id=game_id))
            events.extend(parse_game_text(game, html))
        except Exception as exc:
            fetch_errors.append({"gameId": game_id, "date": game.get("date"), "error": str(exc)})
        if index % 20 == 0:
            print(f"processed {index}/{len(games)} text pages")
        if delay_seconds:
            time.sleep(delay_seconds)

    constants = calculate_constants_for_year(season, events)
    constants["games"] = len(games)
    constants["parsedPlateAppearances"] = len(events)
    constants["fetchErrors"] = fetch_errors
    return constants, events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026")
    parser.add_argument("--through-date", default=None)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    constants, events = build_for_season(args.season, args.through_date, args.delay)
    payload = {
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "Sports Navi game text pages",
        "notes": {
            "scope": "Independent provisional wOBA constants from parsed Sports Navi text play-by-play.",
            "scale": "Raw linear weights are shifted by average OUT value and scaled to league OBP.",
            "limitations": "Rare plays and mid-plate-appearance runner events are parsed best-effort from Japanese text.",
        },
        "byYear": {args.season: constants},
    }
    CONSTANTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EVENTS_TEMPLATE.with_name(EVENTS_TEMPLATE.name.format(season=args.season)).write_text(
        json.dumps(
            {
                "updatedAt": payload["updatedAt"],
                "season": args.season,
                "eventCount": len(events),
                "events": events,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"constants: {CONSTANTS_PATH}")
    print(f"events: {EVENTS_TEMPLATE.with_name(EVENTS_TEMPLATE.name.format(season=args.season))}")
    print(f"plate appearances: {len(events)}")
    print(f"wOBA scale: {constants['wOBAScale']}")


if __name__ == "__main__":
    main()

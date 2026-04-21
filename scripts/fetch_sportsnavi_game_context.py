from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_DIR = ROOT / "summary"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}
SCHEDULE_URL = "https://baseball.yahoo.co.jp/npb/schedule/?date={date}"
STATS_URL = "https://baseball.yahoo.co.jp/npb/game/{game_id}/stats"

TEAM_NAME_MAP = {
    "ヤクルト": "東京ヤクルトスワローズ",
    "巨人": "読売ジャイアンツ",
    "阪神": "阪神タイガース",
    "中日": "中日ドラゴンズ",
    "広島": "広島東洋カープ",
    "DeNA": "横浜DeNAベイスターズ",
    "ソフトバンク": "福岡ソフトバンクホークス",
    "日本ハム": "北海道日本ハムファイターズ",
    "ロッテ": "千葉ロッテマリーンズ",
    "オリックス": "オリックス・バファローズ",
    "西武": "埼玉西武ライオンズ",
    "楽天": "東北楽天ゴールデンイーグルス",
}

INTENTIONAL_WALK_TERMS = ("申告敬遠", "敬遠", "故意四球")


def text(node) -> str:
    if node is None:
        return ""
    return node.get_text(" ", strip=True).replace("\xa0", " ")


def parse_int(value) -> int | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip().replace(",", "")
    if not normalized or normalized == "-":
        return None
    try:
        return int(float(normalized))
    except Exception:
        return None


def normalize_team_name(team: str) -> str:
    normalized = (team or "").strip()
    return TEAM_NAME_MAP.get(normalized, normalized)


def daterange(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def get_with_retry(session: requests.Session, url: str, attempts: int = 4, delay_seconds: float = 1.0) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as exc:  # pragma: no cover - network dependent
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(delay_seconds * attempt)
    assert last_error is not None
    raise last_error


def parse_schedule_page(html: str, schedule_date: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    for item in soup.select("li.bb-score__item"):
        content = item.select_one("a.bb-score__content")
        if content is None:
            continue

        match = re.search(r"/npb/game/(\d+)/", content.get("href", ""))
        if not match:
            continue

        rows.append(
            {
                "date": schedule_date,
                "gameId": match.group(1),
                "status": text(item.select_one("p.bb-score__link")),
                "stadium": text(item.select_one(".bb-score__venue")),
                "homeTeam": normalize_team_name(text(item.select_one(".bb-score__homeLogo"))),
                "awayTeam": normalize_team_name(text(item.select_one(".bb-score__awayLogo"))),
                "homeScore": parse_int(text(item.select_one(".bb-score__score--left"))),
                "awayScore": parse_int(text(item.select_one(".bb-score__score--right"))),
                "scheduleUrl": SCHEDULE_URL.format(date=schedule_date),
                "statsUrl": STATS_URL.format(game_id=match.group(1)),
            }
        )
        rows[-1]["totalRuns"] = (
            rows[-1]["homeScore"] + rows[-1]["awayScore"]
            if rows[-1]["homeScore"] is not None and rows[-1]["awayScore"] is not None
            else None
        )

    return rows


def is_intentional_walk(detail: str) -> bool:
    normalized = (detail or "").strip()
    return any(term in normalized for term in INTENTIONAL_WALK_TERMS)


def parse_intentional_walks_from_stats(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    batting_tables = soup.select("table.bb-statsTable")
    score_tables = soup.select("table.bb-teamScoreTable")

    team_names: list[str] = []
    for table in score_tables:
        first_row = table.select_one("tr")
        cells = first_row.select("th,td") if first_row else []
        if cells:
            team_names.append(normalize_team_name(text(cells[0])))

    results: dict[str, dict] = {}
    for team_name, table in zip(team_names, batting_tables):
        header_cells = table.select("tr")[0].select("th,td")
        headers = [text(cell) for cell in header_cells]
        header_map = {label: idx for idx, label in enumerate(headers)}

        team_total = 0
        players: list[dict] = []

        for order, row in enumerate(table.select("tr")[1:], start=1):
            cells = row.select("th,td")
            if not cells:
                continue

            player_link = row.select_one("a[href*='/npb/player/']")
            player_name = text(player_link) or (
                text(cells[header_map["選手名"]]) if "選手名" in header_map else ""
            )
            if not player_name or player_name == "合計":
                continue

            href = player_link.get("href", "") if player_link else ""
            match = re.search(r"/npb/player/(\d+)/top", href)
            player_id = match.group(1) if match else ""

            detail_items: list[str] = []
            for cell in cells[14:]:
                details = [text(node) for node in cell.select(".bb-statsTable__dataDetail")]
                if details:
                    detail_items.extend(detail for detail in details if detail)
                    continue

                cell_text = text(cell)
                if cell_text and cell_text != "-":
                    detail_items.append(cell_text)

            intentional_walks = sum(1 for detail in detail_items if is_intentional_walk(detail))
            if intentional_walks <= 0:
                continue

            team_total += intentional_walks
            players.append(
                {
                    "order": order,
                    "player": player_name,
                    "playerId": player_id,
                    "intentionalWalks": intentional_walks,
                    "details": [detail for detail in detail_items if is_intentional_walk(detail)],
                }
            )

        results[team_name] = {
            "team": team_name,
            "intentionalWalks": team_total,
            "players": players,
        }

    return results


def fetch_schedule_games(session: requests.Session, season: int, through_date: date, start_date: date | None = None) -> list[dict]:
    rows: dict[str, dict] = {}
    start_date = start_date or date(season, 1, 1)

    for current in daterange(start_date, through_date):
        current_text = current.isoformat()
        html = get_with_retry(session, SCHEDULE_URL.format(date=current_text))
        for row in parse_schedule_page(html, current_text):
            rows[row["gameId"]] = row
        time.sleep(0.03)

    return sorted(rows.values(), key=lambda row: (row["date"], row["gameId"]))


def build_context(season: int, through_date: date, start_date: date | None = None) -> dict:
    session = requests.Session()
    schedule_rows = fetch_schedule_games(session, season, through_date, start_date=start_date)

    completed_games = [row for row in schedule_rows if "試合終了" in row["status"]]
    canceled_games = [row for row in schedule_rows if "中止" in row["status"]]
    other_games = [row for row in schedule_rows if row not in completed_games and row not in canceled_games]

    games: list[dict] = []
    fetch_errors: list[dict] = []
    intentional_walk_games = 0
    intentional_walk_plate_appearances = 0

    for index, row in enumerate(completed_games, start=1):
        try:
            html = get_with_retry(session, row["statsUrl"])
            intentional_walks = parse_intentional_walks_from_stats(html)
        except Exception as exc:  # pragma: no cover - network dependent
            fetch_errors.append({"gameId": row["gameId"], "date": row["date"], "error": str(exc)})
            intentional_walks = {}

        team_total = sum(bucket["intentionalWalks"] for bucket in intentional_walks.values())
        if team_total:
            intentional_walk_games += 1
            intentional_walk_plate_appearances += team_total

        games.append(
            {
                "date": row["date"],
                "gameId": row["gameId"],
                "status": row["status"],
                "stadium": row["stadium"],
                "homeTeam": row["homeTeam"],
                "awayTeam": row["awayTeam"],
                "homeScore": row.get("homeScore"),
                "awayScore": row.get("awayScore"),
                "totalRuns": row.get("totalRuns"),
                "scheduleUrl": row["scheduleUrl"],
                "statsUrl": row["statsUrl"],
                "intentionalWalks": {
                    "total": team_total,
                    "teams": intentional_walks,
                },
            }
        )

        if index % 20 == 0:
            print(f"processed {index}/{len(completed_games)} completed games")
        time.sleep(0.03)

    status_counts = Counter(row["status"] for row in schedule_rows)
    return {
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "season": season,
        "throughDate": through_date.isoformat(),
        "source": {
            "schedule": "https://baseball.yahoo.co.jp/npb/schedule/?date=YYYY-MM-DD",
            "stats": "https://baseball.yahoo.co.jp/npb/game/{gameId}/stats",
            "intentionalWalkDetection": "Counts batting detail cells containing one of: 申告敬遠, 敬遠, 故意四球.",
        },
        "summary": {
            "scheduledGames": len(schedule_rows),
            "completedGames": len(completed_games),
            "canceledGames": len(canceled_games),
            "otherStatusGames": len(other_games),
            "gamesWithIntentionalWalks": intentional_walk_games,
            "intentionalWalkPlateAppearances": intentional_walk_plate_appearances,
            "statusCounts": dict(status_counts),
            "fetchErrors": len(fetch_errors),
        },
        "games": games,
        "canceledGames": canceled_games,
        "otherStatusGames": other_games,
        "fetchErrors": fetch_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Sports Navi stadium and intentional-walk context for NPB games.")
    parser.add_argument("--season", type=int, required=True, help="Season year, e.g. 2026")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Optional inclusive start date in YYYY-MM-DD format. Defaults to season-01-01.",
    )
    parser.add_argument(
        "--through-date",
        type=str,
        required=True,
        help="Inclusive end date in YYYY-MM-DD format, e.g. 2026-04-20",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Defaults to summary/sportsnavi_game_context_<season>.json",
    )
    args = parser.parse_args()

    through_date = date.fromisoformat(args.through_date)
    output_path = args.output or (SUMMARY_DIR / f"sportsnavi_game_context_{args.season}.json")

    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    payload = build_context(args.season, through_date, start_date=start_date)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"output: {output_path}")
    print(f"scheduled: {payload['summary']['scheduledGames']}")
    print(f"completed: {payload['summary']['completedGames']}")
    print(f"canceled: {payload['summary']['canceledGames']}")
    print(f"intentional walk games: {payload['summary']['gamesWithIntentionalWalks']}")


if __name__ == "__main__":
    main()

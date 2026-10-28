"""Collect the 2025 nf3 pitcher profiles discovered in the 12 team listings.

Requires beautifulsoup4. Raw pages are cached outside the disposable site build.
No annual source is modified: comparisons with the existing totals are reported.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
BASE = "https://nf3.sakura.ne.jp/2025/"
TEAMS = [
    ("G", "Central", "巨人", "セ"), ("T", "Central", "阪神", "セ"),
    ("DB", "Central", "DeNA", "セ"), ("C", "Central", "広島", "セ"),
    ("S", "Central", "ヤクルト", "セ"), ("D", "Central", "中日", "セ"),
    ("H", "Pacific", "ソフトバンク", "パ"), ("F", "Pacific", "日本ハム", "パ"),
    ("M", "Pacific", "ロッテ", "パ"), ("E", "Pacific", "東北楽天", "パ"),
    ("B", "Pacific", "オリックス", "パ"), ("L", "Pacific", "西武", "パ"),
]
INT_FIELDS = {
    "試合": "games", "先発": "starts", "救援": "reliefAppearances", "勝利": "wins",
    "敗戦": "losses", "HLD": "holds", "S": "saves", "被打者": "batters",
    "投球数": "pitches", "被安": "hits", "被本": "homeRuns", "三振": "strikeouts",
    "四球": "walks", "故意四": "intentionalWalks", "死球": "hitByPitch",
    "暴投": "wildPitches", "ボーク": "balks", "失点": "runs", "自責": "earnedRuns",
    "完投": "completeGames", "完封": "shutouts", "無四球": "noWalkGames",
}
FLOAT_FIELDS = {
    "防御率": "era", "WHIP": "whip", "QS率": "qualityStartRate",
    "HQS率": "highQualityStartRate", "SQS率": "sawamuraQualityStartRate",
    "被打率": "battingAverageAllowed", "被BABIP": "babipAllowed",
    "被出塁率": "onBasePercentageAllowed", "被長打率": "sluggingPercentageAllowed",
    "K/BB": "kBb", "K/9": "kPer9", "BB/9": "bbPer9", "HR/9": "hrPer9",
    "GO/AO": "goFo", "援護率": "runSupportRate", "FIP": "fip", "LOB%": "strandRate",
}


def clean(value):
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def key(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def number(value):
    value = clean(value).replace(",", "").rstrip("%")
    if value in ("", "-", "--", "∞"):
        return None
    return float(value)


def outs(value):
    value = str(value)
    whole, _, fraction = value.partition(".")
    if fraction not in ("", "0", "1", "2"):
        raise ValueError(f"Invalid baseball innings: {value}")
    return int(whole) * 3 + int(fraction or "0")


class Fetcher:
    def __init__(self, cache, delay=0.4, refresh=False):
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.refresh = refresh
        self.lock = threading.Lock()
        self.last_request = 0.0

    def get(self, url):
        path = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".html")
        if path.exists() and not self.refresh:
            return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for attempt in range(3):
            with self.lock:
                time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
            try:
                request = Request(url, headers={"User-Agent": "BaseballDashboard/1.0 (2025 statistical archive; cached requests)"})
                with urlopen(request, timeout=35) as response:
                    html = response.read().decode("utf-8")
                path.write_text(html, encoding="utf-8")
                return BeautifulSoup(html, "html.parser")
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))


def expand_rows(trs):
    """Expand HTML spans to a grid without losing the source's cell alignment."""
    grid, pending = [], {}
    for tr in trs:
        row, col = {}, 0
        for column, (text, remaining) in list(pending.items()):
            row[column] = text
            if remaining <= 1:
                del pending[column]
            else:
                pending[column] = (text, remaining - 1)
        for cell in tr.find_all(["th", "td"], recursive=False):
            while col in row:
                col += 1
            text = clean(cell.get_text(" ", strip=True))
            width, height = int(cell.get("colspan", 1)), int(cell.get("rowspan", 1))
            for offset in range(width):
                row[col + offset] = text
                if height > 1:
                    pending[col + offset] = (text, height - 1)
            col += width
        grid.append([row.get(i, "") for i in range(max(row, default=-1) + 1)])
    return grid


def parse_tables(soup):
    tables = []
    for table in soup.find_all("table", class_="Base_P"):
        if not table.caption:
            continue
        title = clean(table.caption.get_text(" ", strip=True))
        if "連投の回数" in title:
            continue
        bands, header_trs, data_trs, notes = [], [], [], []

        def finish_band():
            if not header_trs or not data_trs:
                return
            header_grid = expand_rows(header_trs)
            width = max(map(len, header_grid))
            headers = []
            for col in range(width):
                labels = []
                for row in header_grid:
                    label = row[col] if col < len(row) else ""
                    if label and label not in labels:
                        labels.append(label)
                headers.append(" / ".join(labels))
            rows = expand_rows(data_trs)
            while headers and not headers[-1] and all(not row[-1] for row in rows):
                headers.pop()
                rows = [row[:-1] for row in rows]
            if any(len(row) != len(headers) for row in rows):
                raise ValueError(f"Unaligned {title}: headers={len(headers)}, rows={[len(row) for row in rows]}")
            bands.append({"title": title, "headers": headers, "rows": rows})

        for tr in table.find_all("tr", recursive=False):
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            if len(cells) == 1 and clean(cells[0].get_text()).startswith("※"):
                notes.append(clean(cells[0].get_text(" ", strip=True)))
                continue
            is_header = all(cell.name == "th" for cell in cells)
            if is_header and data_trs:
                finish_band()
                header_trs, data_trs = [], []
            (header_trs if is_header else data_trs).append(tr)
        finish_band()
        if len(bands) > 1:
            for index, band in enumerate(bands):
                band["title"] = f"{title}（{index + 1}）"
        for band in bands:
            if notes:
                band["notes"] = notes
        tables.extend(bands)
    return tables


def table_records(table):
    return [dict(zip(map(key, table["headers"]), row)) for row in table["rows"]]


def normalize_annual(tables):
    annual = {}
    for table in tables:
        if not table["title"].startswith("通算成績"):
            continue
        for record in table_records(table):
            for label, field in INT_FIELDS.items():
                if label in record and number(record[label]) is not None:
                    annual[field] = int(number(record[label]))
            for label, field in FLOAT_FIELDS.items():
                if label in record:
                    annual[field] = number(record[label])
            if "回数" in record:
                annual["innings"] = record["回数"]
                annual["inningsOuts"] = outs(record["回数"])
    annual["hasPitchCount"] = annual.get("pitches") is not None
    annual["unintentionalWalks"] = annual["walks"] - annual["intentionalWalks"]
    if annual["inningsOuts"]:
        annual["hPer9"] = round(annual["hits"] * 27 / annual["inningsOuts"], 2)
    for table in tables:
        title, records = table["title"], table_records(table)
        if title.startswith("対打者結果一覧"):
            for row in table["rows"]:
                label, amount = row[:2]
                field = {"ゴロ": "grounders", "フライ": "flyBalls", "空三振": "swingingStrikeouts", "見三振": "lookingStrikeouts", "犠打": "sacrificeBunts", "守備妨": "interference"}.get(label)
                if field:
                    annual[field] = int(number(amount))
            total_outs = sum(int(number(row[1])) for row in table["rows"] if number(row[1]) is not None)
            if total_outs:
                annual["groundOutRate"] = round(100 * annual["grounders"] / total_outs, 1)
                annual["flyOutRate"] = round(100 * annual["flyBalls"] / total_outs, 1)
        elif title.startswith("球種一覧"):
            annual["swingMisses"] = sum(int(number(row["空振り"]) or 0) for row in records)
            pitch_total = sum(int(number(row["球数"]) or 0) for row in records)
            annual["pitchTypePitches"] = pitch_total
            annual["whiffRate"] = round(100 * annual["swingMisses"] / annual["pitches"], 2) if annual.get("pitches") else None
        elif title == "左右別成績":
            for label, field in {"打数": "atBats", "安打": "hits", "2塁": "doubles", "3塁": "triples", "犠打": "sacrificeBunts", "犠飛": "sacrificeFlies"}.items():
                annual[field] = sum(int(number(row[label]) or 0) for row in records)
            annual["singles"] = annual["hits"] - annual["doubles"] - annual["triples"] - annual["homeRuns"]
        elif title.startswith("QS/HQS/SQS"):
            for i, field in ((0, "qualityStarts"), (4, "highQualityStarts"), (8, "sawamuraQualityStarts")):
                match = re.search(r"\((\d+)/(\d+)\)", table["rows"][0][i])
                if match:
                    annual[field] = int(match[1])
        elif title == "月別成績":
            annual["monthlySplits"] = []
            for record in records:
                if int(number(record["試合"]) or 0) == 0:
                    continue
                split = {"month": record["月名"], "innings": record["回数"], "inningsOuts": outs(record["回数"])}
                for label, field in INT_FIELDS.items():
                    if label in record:
                        split[field] = int(number(record[label]) or 0)
                for label in ("防御率", "WHIP"):
                    split[FLOAT_FIELDS[label]] = number(record[label])
                annual["monthlySplits"].append(split)
    return annual


def discover_team(fetcher, team):
    code, division, name, league = team
    url = f"https://nf3.sakura.ne.jp/php/stat_disp/stat_disp.php?y=2025&leg={0 if division == 'Central' else 1}&tm={code}&fp=1&dn=1&dk=0"
    soup = fetcher.get(url)
    base = soup.base.get("href", BASE) if soup.base else BASE
    table = soup.find("table", class_="Base")
    if not table:
        raise ValueError(f"No pitcher listing: {url}")
    trs = table.find_all("tr")
    grid = expand_rows(trs[:2])
    headers, values = list(map(key, grid[0])), grid[1]
    total = dict(zip(headers, values))
    total["inningsOuts"] = outs(total["回数"])
    players = []
    for tr in trs:
        # Position-player pitching, former registrants and transfers use real
        # listing filenames such as 38p, wb_20 and tr_B_16. Never guess jerseys.
        anchor = tr.find("a", href=re.compile(rf"(?:\./)?{division}/{code}/p/[A-Za-z0-9_]+_stat\.htm$"))
        if not anchor:
            continue
        cells = tr.find_all(["td", "th"], recursive=False)
        record = dict(zip(headers, [clean(cell.get_text(" ", strip=True)) for cell in cells]))
        if not int(number(record.get("試合", "0")) or 0):
            continue
        source_url = urljoin(base, anchor["href"])
        profile_id = re.search(r"/p/([A-Za-z0-9_]+)_stat\.htm$", source_url)[1]
        uniform = record["背番"]
        players.append({"team": name, "league": league, "teamCode": code, "player": clean(anchor.get_text()), "uniformNumber": uniform, "nf3Id": f"{code}:{profile_id}", "sourceUrl": source_url})
    if not players:
        raise ValueError(f"No active profiles discovered: {url}")
    return {"team": name, "teamCode": code, "league": league, "sourceUrl": url, "totals": total, "discoveredPlayers": len(players)}, players


def collect_player(fetcher, player):
    soup = fetcher.get(player["sourceUrl"])
    tables = parse_tables(soup)
    annual = normalize_annual(tables)
    official = soup.find("a", href=re.compile(r"https?://npb\.jp/bis/players/"))
    result = dict(player, npbUrl=official["href"] if official else None, tables=tables, annual=annual)
    required = {"月別成績", "球場別成績", "左右別成績", "カウント別成績"}
    if not required.issubset({table["title"] for table in tables}):
        raise ValueError(f"Missing profile categories: {player['sourceUrl']}")
    if annual.get("swingingStrikeouts", 0) + annual.get("lookingStrikeouts", 0) != annual["strikeouts"]:
        raise ValueError(f"Strikeout breakdown mismatch: {player['sourceUrl']}")
    return result


def validate(players, teams, existing):
    checks, issues, definition_differences = [], [], []
    for team in teams:
        members = [p for p in players if p["teamCode"] == team["teamCode"]]
        fields = {"inningsOuts": "inningsOuts", "被安": "hits", "被本": "homeRuns", "三振": "strikeouts", "四球": "walks", "故意四": "intentionalWalks", "死球": "hitByPitch", "失点": "runs", "自責": "earnedRuns", "被打者": "batters"}
        check = {"team": team["team"], "players": len(members), "sourceUrl": team["sourceUrl"], "fields": {}}
        for source_field, field in fields.items():
            total = int(number(team["totals"][source_field]))
            player_sum = sum(p["annual"][field] for p in members)
            check["fields"][field] = {"teamTotal": total, "playerSum": player_sum, "matches": total == player_sum}
            if total != player_sum and field == "earnedRuns" and player_sum > total:
                # Rule 9.16(i): a reliever does not inherit the benefit of prior
                # errors. Individual earned runs can exceed team earned runs.
                note = {"team": team["team"], "field": field, "teamTotal": total, "playerSum": player_sum,
                        "reason": "Individual pitcher earned runs may exceed team earned runs under official rule 9.16(i); source figures are preserved.",
                        "sources": ["https://npb.jp/scoring/officialrule_900.pdf", "https://nf3.sakura.ne.jp/Help/Help_pc.htm"]}
                definition_differences.append(note)
                check["fields"][field]["definitionDifference"] = note["reason"]
            elif total != player_sum:
                issues.append({"type": "teamTotalMismatch", "team": team["team"], "field": field, "teamTotal": total, "playerSum": player_sum})
        checks.append(check)
    index = {(p["team"], key(p["player"])): p for p in existing if p.get("year") == "2025"}
    matched, differences, unmatched = 0, [], []
    compare_fields = ("games", "wins", "losses", "saves", "holds", "inningsOuts", "batters", "hits", "homeRuns", "strikeouts", "walks", "intentionalWalks", "hitByPitch", "balks", "runs", "earnedRuns", "atBats", "battingAverageAllowed", "babipAllowed", "fip", "era", "whip")
    for player in players:
        previous = index.get((player["team"], key(player["player"])))
        if not previous:
            unmatched.append({k: player[k] for k in ("team", "player", "nf3Id", "sourceUrl")})
            continue
        matched += 1
        changes = {field: {"existing": previous.get(field), "nf3": player["annual"].get(field)} for field in compare_fields if previous.get(field) != player["annual"].get(field)}
        if changes:
            differences.append({"team": player["team"], "player": player["player"], "nf3Id": player["nf3Id"], "sourceUrl": player["sourceUrl"], "fields": changes})
    return {"teamChecks": checks, "issues": issues, "definitionDifferences": definition_differences, "existingAnnualComparison": {"existingRows": len(index), "matchedRows": matched, "unmatchedProfiles": unmatched, "differentRows": differences, "note": "Existing totals are compared without modification. AB/AVG/BABIP differences can reflect existing BF-BB-HBP approximation; transfer-team aggregates require separate review."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refresh cached HTML")
    parser.add_argument("--teams", nargs="*", help="Optional nf3 team codes for development")
    args = parser.parse_args()
    fetcher = Fetcher(ROOT / ".nf3-cache" / "pitchers-2025", refresh=args.refresh)
    teams, discovered = [], []
    for team in TEAMS:
        if args.teams and team[0] not in args.teams:
            continue
        coverage, team_players = discover_team(fetcher, team)
        teams.append(coverage)
        discovered.extend(team_players)
        print(f"Discovered {team[0]}: {len(team_players)} active pitchers", flush=True)
    players, failures = [], []
    def collect(player):
        try:
            return collect_player(fetcher, player), None
        except Exception as exc:
            return None, {"sourceUrl": player["sourceUrl"], "error": str(exc)}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index, (player, failure) in enumerate(pool.map(collect, discovered), 1):
            if failure:
                failures.append(failure)
                print(f"FAILED {failure}", flush=True)
            else:
                players.append(player)
            if index % 25 == 0:
                print(f"Parsed {index}/{len(discovered)} profiles", flush=True)
    existing = json.loads((ROOT / "summary/player_totals.json").read_text(encoding="utf-8"))["players"]
    validation = validate(players, teams, existing)
    coverage = {"teams": len(teams), "discoveredPlayers": len(discovered), "collectedPlayers": len(players), "tables": sum(len(p["tables"]) for p in players), "playersWithPitchTypes": sum(any(t["title"].startswith("球種一覧") for t in p["tables"]) for p in players), "parseFailures": failures, "teamListings": teams, "tableCategories": dict(Counter(t["title"] for p in players for t in p["tables"])), **validation}
    payload = {"season": "2025", "source": {"name": "プロ野球 ヌルデータ置き場f3", "url": BASE, "retrievedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "collection": "Active pitcher links discovered from all team listings; UTF-8 HTML cached with maximum 2 concurrent requests and at least 0.4 seconds between request starts.", "notes": ["The source pitch-type Whiff% uses swings as denominator; normalized annual whiffRate uses all pitches to match the dashboard definition.", "Source FIP and rate metrics are retained with their source definitions; existing annual differences are recorded in coverage."]}, "players": players, "coverage": coverage}
    if failures:
        raise SystemExit(json.dumps({"parseFailures": failures}, ensure_ascii=True, indent=2))
    if validation["issues"]:
        raise SystemExit(json.dumps({"validationIssues": validation["issues"]}, ensure_ascii=True, indent=2))
    if not args.teams:
        output = ROOT / "summary/nf3_2025_pitchers.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        audit = {"season": "2025", "source": payload["source"], "coverage": coverage, "example": next(p for p in players if p["nf3Id"] == "B:18")}
        (ROOT / "docs/nf3-pitchers-2025.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {output.name}: {output.stat().st_size:,} bytes", flush=True)
    print(json.dumps({k: coverage[k] for k in ("teams", "discoveredPlayers", "collectedPlayers", "tables", "playersWithPitchTypes", "parseFailures", "issues")}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

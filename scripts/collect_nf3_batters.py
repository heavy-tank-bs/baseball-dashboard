"""Collect 2025 factual batter tables from linked nf3 profiles, with an HTML cache.

Requires beautifulsoup4 and requests. Run from any working directory. The team
listing is authoritative for profile discovery; jersey numbers are never guessed.
Only source facts are exported. nf3 identifiers are not Sports Navi identifiers.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://nf3.sakura.ne.jp/2025/"
TEAMS = [
    ("G", "巨人", "セ", "Central", 0), ("T", "阪神", "セ", "Central", 0),
    ("DB", "DeNA", "セ", "Central", 0), ("C", "広島", "セ", "Central", 0),
    ("S", "ヤクルト", "セ", "Central", 0), ("D", "中日", "セ", "Central", 0),
    ("H", "ソフトバンク", "パ", "Pacific", 1), ("F", "日本ハム", "パ", "Pacific", 1),
    ("M", "ロッテ", "パ", "Pacific", 1), ("E", "東北楽天", "パ", "Pacific", 1),
    ("B", "オリックス", "パ", "Pacific", 1), ("L", "西武", "パ", "Pacific", 1),
]
COUNT_FIELDS = {
    "試合": "games", "打席": "plateAppearances", "打数": "atBats",
    "得点": "runs", "安打": "hits", "２Ｂ": "doubles", "３Ｂ": "triples",
    "本塁": "homeRuns", "打点": "runsBattedIn", "四球": "walks",
    "敬遠": "intentionalWalks", "死球": "hitByPitch", "犠打": "sacBunts",
    "犠飛": "sacFlies", "盗塁": "steals", "三振": "strikeouts",
    "盗塁死": "caughtStealing", "併殺打": "groundedIntoDoublePlays",
    "内安": "infieldHits", "塁打": "totalBases", "失策": "errors", "捕逸": "passedBalls",
}
RATE_FIELDS = {
    "打率": "battingAverage", "得点圏": "scoringPositionBattingAverage",
    "出塁率": "onBasePercentage", "長打率": "sluggingPercentage", "OPS": "ops",
    "BABIP": "babip", "IsoD": "isoDiscipline", "IsoP": "isoPower",
}


def clean(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


class Fetcher:
    def __init__(self, cache, delay=0.6, offline=False):
        self.cache, self.delay, self.offline = Path(cache), delay, offline
        self.cache.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "BaseballDashboardResearch/1.0 (polite cached 2025 statistics collection)"
        self.last = 0.0
        self.downloaded = 0

    def get(self, url, filename):
        target = self.cache / filename
        if target.exists():
            return target.read_text(encoding="utf-8")
        if self.offline:
            raise FileNotFoundError(target)
        for attempt in range(3):
            time.sleep(max(0.0, self.delay - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            try:
                response = self.session.get(url, timeout=(15, 60))
                response.raise_for_status()
                response.encoding = "utf-8"
                html = response.text
                if "ヌルデータ" not in html:
                    raise ValueError(f"Unexpected source HTML: {url}")
                target.write_text(html, encoding="utf-8")
                self.downloaded += 1
                return html
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))


def expand_rows(rows):
    """Expand HTML spans to a rectangular cell grid without losing labels."""
    result, pending = [], {}
    for row in rows:
        values, column = [], 0
        cells = row.find_all(["th", "td"], recursive=False)
        for cell in cells:
            while column in pending:
                text, remaining = pending[column]
                values.append(text)
                if remaining > 1:
                    pending[column] = (text, remaining - 1)
                else:
                    del pending[column]
                column += 1
            text = clean(cell)
            width, height = int(cell.get("colspan", 1)), int(cell.get("rowspan", 1))
            for _ in range(width):
                values.append(text)
                if height > 1:
                    pending[column] = (text, height - 1)
                column += 1
        while column in pending:
            text, remaining = pending[column]
            values.append(text)
            if remaining > 1:
                pending[column] = (text, remaining - 1)
            else:
                del pending[column]
            column += 1
        result.append(values)
    return result


def table_blocks(table):
    """Flatten grouped headers; repeated header/data sections become separate tables."""
    caption = table.find("caption")
    if caption is None:
        return []
    title = clean(caption)
    if any(term in title for term in ("連続試合", "連続打席", "登録")):
        return []
    rows = table.find_all("tr", recursive=False)
    if not rows:
        rows = table.select("tbody > tr")
    grids = expand_rows(rows)
    blocks, header_rows, data_rows = [], [], []

    def flush():
        if not header_rows or not data_rows:
            return
        width = max(len(row) for row in header_rows + data_rows)
        headers = []
        for col in range(width):
            labels = []
            for row in header_rows:
                value = row[col] if col < len(row) else ""
                if value and (not labels or labels[-1] != value):
                    labels.append(value)
            headers.append(" / ".join(labels) or f"列{col+1}")
        blocks.append({"title": title, "headers": headers,
                       "rows": [row + [""] * (width - len(row)) for row in data_rows]})

    for row, values in zip(rows, grids):
        # Summary data rows (notably 得点圏) also use Index2 styling.
        has_numeric_data = any(re.fullmatch(r"(?:\d+(?:\.\d+)?|\.\d+)%?", value) for value in values[1:])
        is_header = bool(set(row.get("class", [])) & {"Index", "Index2"}) and not has_numeric_data
        if is_header:
            if data_rows:
                flush()
                header_rows, data_rows = [], []
            header_rows.append(values)
        else:
            data_rows.append(values)
    flush()
    if len(blocks) > 1:
        for index, block in enumerate(blocks, 1):
            block["title"] = f"{title}（{index}）"
    return blocks


def as_number(value):
    value = value.replace(",", "").strip()
    if value in ("", "-", "--", "-%"):
        return None
    return float(value.rstrip("%"))


def normalized_counts(record):
    result = {}
    for label, field in COUNT_FIELDS.items():
        if label in record:
            value = as_number(record[label])
            result[field] = int(value) if value is not None else 0
    for label, field in RATE_FIELDS.items():
        if label in record:
            result[field] = as_number(record[label])
    if "hits" in result:
        result["singles"] = result["hits"] - sum(result.get(f, 0) for f in ("doubles", "triples", "homeRuns"))
    if "walks" in result and "intentionalWalks" in result:
        result["unintentionalWalks"] = result["walks"] - result["intentionalWalks"]
    return result


def record_rows(block):
    return [dict(zip(block["headers"], row)) for row in block["rows"]]


def parse_listing(html, code, team, league):
    soup = BeautifulSoup(html, "html.parser")
    players, total = [], {}
    for table in soup.find_all("table"):
        headers = None
        listing_rows = table.find_all("tr")
        for tr, cells in zip(listing_rows, expand_rows(listing_rows)):
            if "Index" in tr.get("class", []) and "名前" in cells:
                headers = cells
                continue
            if headers is None or not cells:
                continue
            record = dict(zip(headers, cells))
            links = [a for a in tr.find_all("a", href=True)
                     if re.search(r"/f/[^/]+_stat\.htm$", a["href"])]
            if "合計" in cells[:2] and "試合" in record:
                total = normalized_counts(record)
            if not links:
                continue
            link = links[0]
            match = re.search(r"(?:\./)?((?:Central|Pacific)/[^/]+/f/([^/]+)_stat\.htm)$", link["href"])
            if not match:
                raise ValueError(f"Unexpected player profile link: {link['href']}")
            annual = normalized_counts(record)
            if annual.get("games", 0) <= 0:
                continue
            players.append({"team": team, "teamCode": code, "league": league,
                            "player": clean(link), "uniformNumber": record["背番"], "profileKey": match[2],
                            "nf3Id": f"{code}:{match[2]}",
                            "sourceUrl": urljoin(BASE, match[1]),
                            "listingAnnual": annual})
    if not players or not total:
        raise ValueError(f"No linked active hitters or total found for {team}")
    return players, total


def parse_profile(html, metadata):
    soup = BeautifulSoup(html, "html.parser")
    tables = [block for table in soup.find_all("table") for block in table_blocks(table)]
    raw_annual = {}
    for table in tables:
        if table["title"].startswith("通算成績") and table["rows"]:
            raw_annual.update(record_rows(table)[0])
    annual = normalized_counts(raw_annual)
    if not {"games", "plateAppearances", "atBats", "hits"} <= annual.keys():
        raise ValueError(f"Incomplete annual facts: {metadata['sourceUrl']}")
    for key, listing_value in metadata["listingAnnual"].items():
        if key in annual and annual[key] != listing_value:
            raise ValueError(f"Profile/listing mismatch {metadata['nf3Id']} {key}: {annual[key]} != {listing_value}")
    annual.update({"year": "2025", "batterId": "", "player": metadata["player"],
                   "uniformNumber": metadata["uniformNumber"], "team": metadata["team"],
                   "teams": [metadata["team"]], "league": metadata["league"],
                   "ballZoneSwingRate": None, "ballZonePitchCount": 0, "ballZoneSwingCount": 0,
                   "wrc": None, "wrcPlus": None, "parkFactor": None, "effectiveParkFactor": None,
                   "monthlySplits": [], "nf3Id": metadata["nf3Id"],
                   "sourceUrl": metadata["sourceUrl"]})
    for table in tables:
        if table["title"] == "月別成績":
            for raw in record_rows(table):
                counts = normalized_counts(raw)
                if counts.get("games", 0) or counts.get("plateAppearances", 0):
                    label = raw["月名"]
                    # nf3 combines March and April. Keep that source grouping explicit.
                    month = "2025-03/04" if label == "3・4月" else f"2025-{int(label.removesuffix('月')):02}"
                    counts.update({"year": "2025", "month": month, "monthLabel": label,
                                   "sourceGrouping": label, "batterId": "",
                                   "player": metadata["player"], "team": metadata["team"],
                                   "teams": [metadata["team"]], "league": metadata["league"],
                                   "wrc": None, "wrcPlus": None, "parkFactor": None,
                                   "effectiveParkFactor": None,
                                   "scoringPositionAtBats": None, "scoringPositionHits": None,
                                   "scoringPositionBattingAverage": None,
                                   "ballZoneSwingRate": None})
                    if counts.get("battingAverage") is not None:
                        counts["isoPower"] = round(counts["sluggingPercentage"] - counts["battingAverage"], 3)
                        counts["isoDiscipline"] = round(counts["onBasePercentage"] - counts["battingAverage"], 3)
                    babip_denominator = counts.get("atBats", 0) - counts.get("strikeouts", 0) - counts.get("homeRuns", 0) + counts.get("sacFlies", 0)
                    counts["babip"] = round((counts.get("hits", 0) - counts.get("homeRuns", 0)) / babip_denominator, 3) if babip_denominator else None
                    annual["monthlySplits"].append(counts)
        if table["title"] == "ランナ−別成績":
            for raw in record_rows(table):
                if raw.get("条件") == "得点圏":
                    annual["scoringPositionAtBats"] = int(raw["打数"])
                    annual["scoringPositionHits"] = int(raw["安打"])
                    annual["scoringPositionBattingAverage"] = as_number(raw["打率"])
    annual.setdefault("scoringPositionAtBats", 0)
    annual.setdefault("scoringPositionHits", 0)
    npb = soup.find("a", href=re.compile(r"https://npb\.jp/bis/players/\d+\.html"))
    return {k: v for k, v in metadata.items() if k != "listingAnnual"} | {
        "npbUrl": npb["href"] if npb else None, "tables": tables, "annual": annual}


def name_key(player):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", player))


def audit(players, totals, listing_counts, failures):
    compared_fields = ["plateAppearances", "atBats", "runs", "hits", "doubles", "triples",
                       "homeRuns", "runsBattedIn", "walks", "intentionalWalks", "hitByPitch",
                       "sacBunts", "sacFlies", "steals", "strikeouts"]
    team_totals = []
    for _, team, _, _, _ in TEAMS:
        if team not in totals:
            continue
        actual = {field: sum(p["annual"].get(field, 0) for p in players if p["team"] == team)
                  for field in compared_fields}
        differences = {field: {"players": actual[field], "listingTotal": totals[team].get(field)}
                       for field in compared_fields if actual[field] != totals[team].get(field)}
        team_totals.append({"team": team, "players": sum(p["team"] == team for p in players),
                            "totals": actual, "differences": differences})
    monthly, arithmetic = [], []
    for player in players:
        annual = player["annual"]
        for field in compared_fields:
            value = sum(m.get(field, 0) for m in annual["monthlySplits"])
            if value != annual.get(field, 0):
                monthly.append({"nf3Id": player["nf3Id"], "field": field, "annual": annual.get(field), "monthly": value})
        if annual["plateAppearances"] != sum(annual.get(f, 0) for f in ("atBats", "walks", "hitByPitch", "sacBunts", "sacFlies")):
            # Catcher's interference is not part of the five-term official formula.
            arithmetic.append({"nf3Id": player["nf3Id"], "plateAppearances": annual["plateAppearances"],
                               "sumAbBbHbpShSf": sum(annual.get(f, 0) for f in ("atBats", "walks", "hitByPitch", "sacBunts", "sacFlies"))})
    existing_path = ROOT / "summary" / "batter_totals.json"
    existing = json.loads(existing_path.read_text(encoding="utf-8"))["players"] if existing_path.exists() else []
    old = {(p["team"], name_key(p["player"])): p for p in existing if p["year"] == "2025"}
    basic_diffs, matched = [], 0
    for player in players:
        key = player["team"], name_key(player["player"])
        if key not in old:
            continue
        matched += 1
        for field in compared_fields:
            if field == "intentionalWalks":
                continue
            before, after = old[key].get(field), player["annual"].get(field)
            if before != after:
                basic_diffs.append({"team": player["team"], "player": player["player"], "field": field,
                                    "existing": before, "nf3": after})
    return {"players": len(players), "teams": len(totals), "listingCounts": listing_counts,
            "playersWithPlateAppearances": sum(p["annual"]["plateAppearances"] > 0 for p in players),
            "tables": sum(len(p["tables"]) for p in players), "parseFailures": failures,
            "teamTotals": team_totals, "teamTotalDifferences": sum(bool(t["differences"]) for t in team_totals),
            "monthlyDifferences": monthly, "plateAppearanceFormulaDifferences": arithmetic,
            "existingMatched": matched, "existingBasicDifferences": basic_diffs,
            "notes": ["Profiles are discovered exclusively from team hitter listing links.",
                      "Player records are per team; same-league transfer aggregation belongs to the site integration.",
                      "March and April are combined by the source and remain a single explicit 2025-03/04 group.",
                      "Source percentages and display rounding are retained. No 2026 wOBA weights or 2025 wRC+ are inferred."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teams", help="Comma-separated nf3 team codes; default all twelve")
    parser.add_argument("--cache", default=str(ROOT / ".nf3-cache" / "batters"))
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--limit", type=int, help="Focused parser inspection only; outputs are not saved")
    args = parser.parse_args()
    selected = set(args.teams.split(",")) if args.teams else {t[0] for t in TEAMS}
    fetcher = Fetcher(args.cache, args.delay, args.offline)
    players, totals, listing_counts, failures = [], {}, {}, []
    discovered = []
    for code, team, league, _, leg in TEAMS:
        if code not in selected:
            continue
        listing_url = f"https://nf3.sakura.ne.jp/php/stat_disp/stat_disp.php?y=2025&leg={leg}&tm={code}&fp=0&dn=1&dk=0"
        html = fetcher.get(listing_url, f"listing_{code}.html")
        entries, totals[team] = parse_listing(html, code, team, league)
        discovered.extend(entries)
        listing_counts[team] = len(entries)
        print(f"Listing {code}: {len(entries)} active player profiles", flush=True)
    for index, metadata in enumerate(discovered[:args.limit] if args.limit else discovered, 1):
        try:
            html = fetcher.get(metadata["sourceUrl"], f"{metadata['teamCode']}_{metadata['profileKey']}.html")
            players.append(parse_profile(html, metadata))
        except Exception as error:
            failures.append({"nf3Id": metadata["nf3Id"], "url": metadata["sourceUrl"], "error": str(error)})
            print(f"FAIL {metadata['nf3Id']}: {error}", flush=True)
        if index % 20 == 0 or index == len(discovered):
            print(f"Profiles {index}/{len(discovered)}; parsed={len(players)} failures={len(failures)} downloaded={fetcher.downloaded}", flush=True)
    report = audit(players, totals, listing_counts, failures)
    output = {"season": "2025", "source": {"name": "プロ野球 ヌルデータ置き場f3", "url": BASE,
                                           "retrievedAt": datetime.now(timezone.utc).isoformat()},
              "players": players, "coverage": report}
    if args.limit:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if failures or report["teamTotalDifferences"] or report["monthlyDifferences"]:
        # Preserve diagnostic evidence even when an incomplete scrape must not ship.
        (ROOT / "docs" / "nf3-batters-2025.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit("Collection failed validation; inspect docs/nf3-batters-2025.json")
    (ROOT / "summary" / "nf3_2025_batters.json").write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (ROOT / "docs" / "nf3-batters-2025.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("players", "teams", "tables", "teamTotalDifferences", "existingMatched")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

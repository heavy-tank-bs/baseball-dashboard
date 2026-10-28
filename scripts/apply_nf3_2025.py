"""Apply validated nf3 2025 season summaries without changing other seasons.

Run both collect_nf3_*.py collectors first, then this script and verify_nf3_2025.py.
nf3 identifiers remain separate from SportsNavi player identifiers.
"""
from __future__ import annotations

import copy
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def name_key(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).translate(str.maketrans("髙﨑", "高崎"))


def load_source(kind):
    source = json.loads((ROOT / "summary" / f"nf3_2025_{kind}.json").read_text(encoding="utf-8"))
    coverage = source["coverage"]
    if source["season"] != "2025" or len({p["team"] for p in source["players"]}) != 12:
        raise ValueError(f"Incomplete source: {kind}")
    for field in ("parseFailures", "issues", "teamTotalDifferences", "monthlyDifferences"):
        if coverage.get(field):
            raise ValueError(f"Invalid source coverage {kind}: {field}")
    expected = coverage.get("discoveredPlayers", sum(coverage.get("listingCounts", {}).values()))
    if expected != len(source["players"]) or coverage.get("collectedPlayers", coverage.get("players")) != len(source["players"]):
        raise ValueError(f"Truncated source: {kind}")
    return source


def monthly_rows(source, row):
    output = []
    for monthly in source.get("monthlySplits", []):
        monthly = copy.deepcopy(monthly)
        label = monthly.get("sourceGrouping") or monthly.get("label") or monthly["month"]
        if label in ("3・4月", "3･4月") or monthly["month"] == "2025-03/04":
            label, month = "3・4月", "2025-03/04"
        else:
            number = re.search(r"(\d+)月", label)
            month = f"2025-{int(number[1]):02}" if number else monthly["month"]
        monthly.update(month=month, monthLabel=label, sourceGrouping=label,
                       year="2025", player=row["player"], team=row["team"],
                       teams=[row["team"]], league=row["league"],
                       sourceProvider="nf3", wrc=None, wrcPlus=None)
        if "inningsOuts" in monthly:
            # Monthly source tables do not give IBB, AB or pitch counts.
            # Do not manufacture FIP, batting-average or pitch-rate inputs.
            monthly.update(fipConstant=None, fip=None, hasPitchCount=False, pitches=None)
        output.append(monthly)
    return output


def apply(kind):
    filename = "player_totals.json" if kind == "pitchers" else "batter_totals.json"
    id_field = "pitcherId" if kind == "pitchers" else "batterId"
    path = ROOT / "summary" / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    source = load_source(kind)
    previous = [p for p in data["players"] if p["year"] == "2025"]
    index = {(p["team"], name_key(p["player"])): p for p in previous}
    players, matched, changes = [], set(), []
    for profile in source["players"]:
        identity = profile["team"], name_key(profile["player"])
        old = index.get(identity, {})
        if old:
            matched.add(identity)
        annual = copy.deepcopy(profile["annual"])
        row = {**old, **annual, "year": "2025", id_field: old.get(id_field, ""),
               "team": profile["team"], "teams": [profile["team"]], "league": profile["league"],
               "player": old.get("player", profile["player"]), "uniformNumber": profile["uniformNumber"],
               "sourcePlayerId": profile["nf3Id"], "sourceUrl": profile["sourceUrl"],
               "sourceProvider": "nf3", "npbUrl": profile.get("npbUrl")}
        row["monthlySplits"] = monthly_rows(annual, row)
        if kind == "batters":
            # No validated 2025 linear weights or park context are available.
            row.update(wrc=None, wrcPlus=None, parkFactor=None, effectiveParkFactor=None,
                       ballZoneSwingRate=None, ballZonePitchCount=None, ballZoneSwingCount=None)
        players.append(row)
        differences = {key: {"before": old.get(key), "after": row.get(key)}
                       for key in annual if key != "monthlySplits" and old and old.get(key) != row.get(key)}
        if differences:
            changes.append({"team": row["team"], "player": row["player"], "fields": differences})
    if len({(p["team"], name_key(p["player"])) for p in players}) != len(players):
        raise ValueError("Duplicate season player identity")
    if len(matched) != len(index):
        raise ValueError(f"Previously published rows missing from source: {sorted(set(index) - matched)}")
    if kind == "pitchers":
        leagues = []
        fields = ("games", "inningsOuts", "earnedRuns", "homeRuns", "walks", "unintentionalWalks", "intentionalWalks", "hitByPitch", "strikeouts")
        for league in ("セ", "パ"):
            rows = [p for p in players if p["league"] == league]
            totals = {field: sum(p[field] for p in rows) for field in fields}
            innings = totals["inningsOuts"] / 3
            numerator = 13 * totals["homeRuns"] + 3 * (totals["unintentionalWalks"] + totals["hitByPitch"]) - 2 * totals["strikeouts"]
            constant = round(totals["earnedRuns"] * 9 / innings - numerator / innings, 4)
            leagues.append({"year": "2025", "league": league, **totals,
                            "innings": f"{totals['inningsOuts'] // 3}" + (f".{totals['inningsOuts'] % 3}" if totals['inningsOuts'] % 3 else ""),
                            "era": round(totals["earnedRuns"] * 9 / innings, 2), "fipConstant": constant})
            for row in rows:
                row["fipConstant"] = constant
                numerator = 13 * row["homeRuns"] + 3 * (row["unintentionalWalks"] + row["hitByPitch"]) - 2 * row["strikeouts"]
                row["fip"] = round(numerator / (row["inningsOuts"] / 3) + constant, 2) if row["inningsOuts"] else None
        data["leagueStats"] = [p for p in data.get("leagueStats", []) if p["year"] != "2025"] + leagues
    else:
        contexts = data.setdefault("metricContexts", {})
        contexts["wobaConstants"] = [p for p in contexts.get("wobaConstants", []) if p["year"] != "2025"] + [
            {"year": "2025", "constantsYear": None, "available": False,
             "source": "2025年度の検証済みwOBA係数未収録。wRC/wRC+は未算出。"}]
        contexts["leagues"] = [p for p in contexts.get("leagues", []) if p["year"] != "2025"]
        for league in ("セ", "パ"):
            rows = [p for p in players if p["league"] == league]
            pa, runs = (sum(p[field] for p in rows) for field in ("plateAppearances", "runs"))
            contexts["leagues"].append({"year": "2025", "league": league, "plateAppearances": pa,
                                        "runs": runs, "runsPerPlateAppearance": round(runs / pa, 6),
                                        "woba": None, "wobaScale": None, "constantsYear": None, "available": False})
    data["players"] = players + [p for p in data["players"] if p["year"] != "2025"]
    data.setdefault("sourceByYear", {})["2025"] = {**source["source"], "dataset": f"nf3_2025_{kind}.json",
        "scope": "2025年レギュラーシーズン・全12球団。3・4月は取得元の合算区分。",
        "limitations": "年度・条件別集計。個別投球の位置座標は未収録。"}
    data["updatedAt"] = source["source"]["retrievedAt"]
    if "nf3 2025" not in data.get("source", ""):
        data["source"] = data.get("source", "") + " + nf3 2025"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"before": len(previous), "after": len(players), "matched": len(matched),
            "added": len(players) - len(matched), "teamCounts": dict(Counter(p["team"] for p in players)),
            "previousRowsNotMatched": [{"team": p["team"], "player": p["player"]} for key, p in index.items() if key not in matched],
            "changes": changes}


def main():
    for kind in ("pitchers", "batters"):
        load_source(kind)
    results = {kind: apply(kind) for kind in ("pitchers", "batters")}
    (ROOT / ".nf3-cache").mkdir(exist_ok=True)
    (ROOT / ".nf3-cache/integration.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for kind, result in results.items():
        print(kind, {k: result[k] for k in ("before", "after", "matched", "added", "previousRowsNotMatched")})


if __name__ == "__main__":
    main()

"""Verify enriched 2025 stats against NPB official team totals and saved nf3 tables."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import urljoin
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = ROOT / "docs/nf3-2025-official-totals.json"

BATTER_FIELDS = {"打席": "plateAppearances", "打数": "atBats", "得点": "runs", "安打": "hits", "二塁打": "doubles", "三塁打": "triples", "本塁打": "homeRuns", "打点": "runsBattedIn", "盗塁": "steals", "犠打": "sacBunts", "犠飛": "sacFlies", "四球": "walks", "故意四": "intentionalWalks", "死球": "hitByPitch", "三振": "strikeouts"}
PITCHER_FIELDS = {"勝利": "wins", "敗北": "losses", "セーブ": "saves", "ホールド": "holds", "打者": "batters", "安打": "hits", "本塁打": "homeRuns", "四球": "walks", "故意四": "intentionalWalks", "死球": "hitByPitch", "三振": "strikeouts", "ボーク": "balks", "失点": "runs", "自責点": "earnedRuns"}


def refresh_official():
    import requests
    from bs4 import BeautifulSoup
    teams = []
    for kind, page, fields in (("pitchers", "tmp", PITCHER_FIELDS), ("batters", "tmb", BATTER_FIELDS)):
        for league, leg in (("セ", "c"), ("パ", "p")):
            url = f"https://npb.jp/bis/2025/stats/{page}_{leg}.html"
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            table = soup.select_one("table.tablefix2")
            headers = [cell.get_text("", strip=True) for cell in table.select("thead th")]
            count = 0
            for tr in table.select("tbody tr"):
                cells = [cell.get_text("", strip=True) for cell in tr.select("td")]
                if not cells:
                    continue
                record = dict(zip(headers, cells))
                team = "東北楽天" if record["チーム"] == "楽天" else record["チーム"]
                totals = {field: int(record[label]) for label, field in fields.items()}
                individual_context = {}
                if kind == "pitchers":
                    innings = record["投球回"].replace(" ", "")
                    whole, _, remainder = innings.partition(".")
                    totals["inningsOuts"] = int(whole) * 3 + int(remainder or 0)
                    individual_url = urljoin(url, tr.find("a")["href"])
                    individual_response = requests.get(individual_url, timeout=45)
                    individual_response.raise_for_status()
                    individual_table = BeautifulSoup(individual_response.content, "html.parser").select_one("table.tablefix2")
                    individual_headers = [cell.get_text("", strip=True) for cell in individual_table.select("thead th")]
                    individual_rows = [dict(zip(individual_headers, [c.get_text("", strip=True) for c in r.select("td")])) for r in individual_table.select("tbody tr") if r.select("td")]
                    individual_er = sum(int(r["自責点"]) for r in individual_rows)
                    individual_context = {"individualUrl": individual_url, "pitcherRows": len(individual_rows),
                                          "teamEarnedRuns": totals["earnedRuns"], "individualEarnedRuns": individual_er,
                                          "earnedRunsNote": "チーム自責点と個人自責点の合計は一致しない場合がある（公認野球規則9.16(i)）。年度選手成績は個人の合計と照合。"}
                    totals["earnedRuns"] = individual_er
                teams.append({"kind": kind, "league": league, "team": team, "url": url, "totals": totals, **individual_context})
                count += 1
            assert count == 6, (url, count)
    OFFICIAL.write_text(json.dumps({"season": "2025", "source": "NPB公式チーム成績", "retrievedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "teams": teams}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def verify(baseline):
    official = read("docs/nf3-2025-official-totals.json")
    checks, issues, sources, unchanged = [], [], {}, {}
    for kind, filename in (("pitchers", "player_totals.json"), ("batters", "batter_totals.json")):
        data = read(f"summary/{filename}")
        source = read(f"summary/nf3_2025_{kind}.json")
        players = [p for p in data["players"] if p["year"] == "2025"]
        sources[kind] = {"players": len(players), "tables": sum(len(p["tables"]) for p in source["players"]),
                         "source": source["source"], "sourceSha256": hashlib.sha256((ROOT / f"summary/nf3_2025_{kind}.json").read_bytes()).hexdigest()}
        assert len(players) == len(source["players"])
        assert len({p["team"] for p in players}) == 12
        assert data["sourceByYear"]["2025"]["dataset"] == f"nf3_2025_{kind}.json"
        indexed = {(p["team"], p["sourcePlayerId"]): p for p in players}
        fields = list(PITCHER_FIELDS.values()) + ["inningsOuts", "pitches", "atBats"] if kind == "pitchers" else list(BATTER_FIELDS.values())
        for profile in source["players"]:
            row = indexed[profile["team"], profile["nf3Id"]]
            for field in fields:
                if row.get(field) != profile["annual"].get(field):
                    issues.append({"type": "sourceAnnualMismatch", "kind": kind, "player": row["player"], "field": field})
            assert row["monthlySplits"], (kind, row["player"], "missing monthly splits")
            assert all(not (m["month"] == "2025-04" and m.get("sourceGrouping") == "3・4月") for m in row["monthlySplits"])
            if kind == "batters":
                assert row["wrc"] is None and row["wrcPlus"] is None
                assert row["singles"] + row["doubles"] + row["triples"] + row["homeRuns"] == row["hits"]
            else:
                assert row["lookingStrikeouts"] + row["swingingStrikeouts"] == row["strikeouts"]
                assert row["hasPitchCount"] and row["pitches"] is not None
            for table in profile["tables"]:
                assert table["headers"] and all(len(r) == len(table["headers"]) for r in table["rows"]), (profile["sourceUrl"], table["title"])
        for expected in official["teams"]:
            if expected["kind"] != kind:
                continue
            members = [p for p in players if p["team"] == expected["team"]]
            actual = {field: sum(p.get(field, 0) for p in members) for field in expected["totals"]}
            differences = {field: {"dashboard": actual[field], "official": value} for field, value in expected["totals"].items() if actual[field] != value}
            checks.append({"kind": kind, "team": expected["team"], "players": len(members), "url": expected["url"],
                           **{k: expected[k] for k in ("individualUrl", "teamEarnedRuns", "individualEarnedRuns", "earnedRunsNote") if k in expected},
                           "fieldsChecked": len(actual), "differences": differences})
            if differences:
                issues.append(checks[-1])
        if baseline:
            before = json.loads(subprocess.check_output(["git", "show", f"{baseline}:summary/{filename}"], cwd=ROOT).decode("utf-8"))
            same = [p for p in before["players"] if p["year"] != "2025"] == [p for p in data["players"] if p["year"] != "2025"]
            unchanged[kind] = {"baseline": baseline, "non2025PlayersIdentical": same}
            assert same, (kind, "other seasons changed")
            for key in ("leagueStats",):
                assert [p for p in before.get(key, []) if p["year"] != "2025"] == [p for p in data.get(key, []) if p["year"] != "2025"]
            for key, values in before.get("metricContexts", {}).items():
                assert [p for p in values if p["year"] != "2025"] == [p for p in data["metricContexts"][key] if p["year"] != "2025"]
    integration = read(".nf3-cache/integration.json") if (ROOT / ".nf3-cache/integration.json").exists() else None
    report = {"season": "2025", "verifiedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": sources,
              "officialTeamChecks": checks, "otherSeasons": unchanged, "issues": issues,
              "integration": {k: {key: value for key, value in values.items() if key != "changes"} for k, values in integration.items()} if integration else None,
              "limitations": ["nf3の3・4月は合算区分のまま収録。", "個別投球位置・ボールゾーン指標は未収録。", "検証済み2025係数・球場補正がないためwRC/wRC+は未算出。", "条件別集計・球速・球種の原観測の正確性は全投球の外部実測とは照合していない。"]}
    (ROOT / "docs/nf3-2025-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if issues:
        raise SystemExit(json.dumps(issues, ensure_ascii=False, indent=2))
    print(json.dumps({"players": {k: v["players"] for k, v in sources.items()}, "tables": sum(s["tables"] for s in sources.values()), "officialTeamChecks": len(checks), "officialCountingChecks": sum(c["fieldsChecked"] for c in checks), "issues": 0}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-official", action="store_true")
    parser.add_argument("--official-only", action="store_true")
    parser.add_argument("--baseline", default="e108e8da", help="Commit before this requested historical enrichment")
    args = parser.parse_args()
    if args.refresh_official:
        refresh_official()
    if not args.official_only:
        verify(args.baseline)


if __name__ == "__main__":
    main()

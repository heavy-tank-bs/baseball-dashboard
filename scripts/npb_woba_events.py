"""Parse NPB official play-by-play into auditable plate-appearance events.

Every row explicitly gives its *pre*-play base/out state. Consecutive states
therefore determine runs by conservation of runners, including errors and
independent steals, wild pitches, and passed balls. The final play in each
half-inning uses the official inning total because stranded runners disappear
at three outs. Terminal (including walk-off) states have zero future runs.
"""
from __future__ import annotations

import re

from build_woba_constants import classify_event, game_side_team
from npb_boxscore_stats import _Node, _Tree, _cells, _identity


def _walk(node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from _walk(child)


def _state(outs, bases):
    match = re.fullmatch(r"\s*([012])アウト\s*", outs)
    if not match:
        raise ValueError(f"Invalid pre-play outs: {outs!r}")
    normalized = re.sub(r"\s", "", bases)
    if normalized in {"", "-"}:
        occupied = (False, False, False)
    elif normalized == "満塁":
        occupied = (True, True, True)
    elif re.fullmatch(r"[123](?:・[123])*塁", normalized):
        occupied = tuple(str(i) in normalized for i in (1, 2, 3))
    else:
        raise ValueError(f"Invalid pre-play bases: {bases!r}")
    return int(match[1]), occupied


def _key(state):
    return f"{state[0]}:{''.join('1' if b else '0' for b in state[1])}"


def _category(result, state):
    # NPB calls sacrifices 犠牲バント, whereas SportsNavi uses 送りバント.
    if "犠牲バント" in result:
        return "SH"
    if "守備妨害" in result or "三重殺" in result:
        return "OUT"
    return classify_event(result, state)


def _inning_runs(game, inning, half):
    side = "away" if half == "表" else "home"
    rows = game.get("inningScores", {}).get(side, {}).get("innings", [])
    matches = [row for row in rows if row.get("inning") == inning]
    if len(matches) != 1 or matches[0].get("runs") is None:
        raise ValueError(f"Missing official inning runs: {game.get('gameId')} {inning}{half}")
    return int(matches[0]["runs"])


def _line_scores(root):
    """Read official HTML directly, including walk-off cells such as 1x."""
    table = next((node for node in root.descendants("table") if node.attrs.get("id") == "tablefix_ls"), None)
    if table is None:
        return {}
    scores = {}
    for tr in table.descendants("tr"):
        classes = tr.attrs.get("class", "").split()
        half = "表" if "top" in classes else "裏" if "bottom" in classes else None
        if not half:
            continue
        inning = 0
        for cell in _cells(tr):
            if cell.tag != "td" or "total-" in cell.attrs.get("class", ""):
                continue
            inning += 1
            raw = re.sub(r"\s", "", cell.text()).upper()
            match = re.fullmatch(r"(\d+)(X)?", raw)
            if match:
                scores[(inning, half)] = {"runs": int(match[1]), "walkoff": bool(match[2]), "raw": raw}
            elif raw not in {"", "X", "-"}:
                raise ValueError(f"Unrecognized official line-score cell: {raw!r}")
    return scores


def parse_game_text(game: dict, html: str, id_lookup: dict) -> list[dict]:
    """Return PA events; identity lookup matches npb_boxscore_stats' format.

    Raises ValueError for unknown states, identities, negative run transitions,
    unrecognized results, or inconsistent official inning totals. No guessed
    run totals are allowed to enter the constants.
    """
    root = _Tree(html).root
    line_scores = _line_scores(root)
    halves, current = [], None
    for node in _walk(root):
        if node.tag == "h5":
            match = re.match(r"(\d+)回([表裏])", node.text().strip())
            if match:
                current = {"inning": int(match[1]), "half": match[2], "rows": [], "unfinished": []}
                halves.append(current)
        if current is None or node.tag != "tr":
            continue
        cells = _cells(node)
        if len(cells) != 5 or "アウト" not in cells[0].text():
            continue
        state = _state(cells[0].text(), cells[1].text())
        result = cells[4].text().strip()
        if result in {"（途中終了）", "（途中交代）"}:
            # The batter's unfinished turn is printed after a runner makes
            # the third out, or before a pinch hitter completes the same PA.
            current["unfinished"].append((state, result))
            continue
        links = [a for a in cells[2].descendants("a") if "/bis/players/" in a.attrs.get("href", "")]
        is_pa = bool(links)
        team = game_side_team(game, current["half"])
        player_id, name = _identity(cells[2], team, id_lookup) if is_pa else ("", "")
        category = _category(result, state) if is_pa else "RUNNER"
        if category == "OTHER":
            raise ValueError(f"Unknown NPB result: {game.get('gameId')} {result}")
        current["rows"].append({"state": state, "result": result, "isPA": is_pa,
                                "batterId": player_id, "batter": name, "eventType": category})
    if not halves:
        raise ValueError("No official play-by-play innings")
    events = []
    seen = set()
    for section in halves:
        inning, half, rows = section["inning"], section["half"], section["rows"]
        if (inning, half) in seen:
            raise ValueError(f"Duplicate inning: {inning}{half}")
        seen.add((inning, half))
        official = line_scores.get((inning, half))
        official_runs = official["runs"] if official else _inning_runs(game, inning, half)
        if not rows:
            if (section is halves[-1] and official_runs == 0
                    and section["unfinished"] == [((0, (False, False, False)), "（途中終了）")]):
                # Rain can stop the game during the first uncompleted PA.
                # A printed 0/0x inning exists, but supplies no PA or RE sample.
                continue
            raise ValueError(f"Empty inning: {inning}{half}")
        for index, row in enumerate(rows[1:], 1):
            previous = rows[index - 1]
            if (not row["isPA"] and previous["isPA"] and "三振" in previous["result"]
                    and not any(term in previous["result"] for term in ("振り逃げ", "振逃"))
                    and previous["state"] == row["state"] and row["state"][0] < 2):
                # Strikeout + stolen-base attempt on one pitch share the
                # displayed pre-pitch state. Attribute the strikeout first,
                # then the independent runner event, without a phantom run.
                row["state"] = (row["state"][0] + 1, row["state"][1])
        runs_so_far = 0
        for index, row in enumerate(rows):
            pre_state = row["state"]
            final = index == len(rows) - 1
            if final:
                post_state = (3, (False, False, False))
                runs = official_runs - runs_so_far
            else:
                post_state = rows[index + 1]["state"]
                outs_added = post_state[0] - pre_state[0]
                if outs_added < 0:
                    raise ValueError(f"Out count decreased: {game.get('gameId')} {inning}{half}")
                runs = sum(pre_state[1]) + int(row["isPA"]) - outs_added - sum(post_state[1])
            if runs < 0 or runs > sum(pre_state[1]) + int(row["isPA"]):
                raise ValueError(f"Impossible run transition: {game.get('gameId')} {inning}{half} "
                                 f"{row['result']} {pre_state} -> {post_state}, runs={runs}")
            before = runs_so_far
            runs_so_far += runs
            if row["isPA"]:
                events.append({"gameId": str(game.get("gameId") or ""), "date": game.get("date") or "",
                               "inning": inning, "half": half, "battingTeam": game_side_team(game, half),
                               "batter": row["batter"], "batterId": row["batterId"], "order": "",
                               "eventType": row["eventType"], "result": row["result"],
                               "preState": _key(pre_state), "plateAppearancePreState": _key(pre_state),
                               "postState": _key(post_state),
                               "postStateSource": "terminal" if final else "next-official-play-state",
                               "terminalReason": ("walkoff" if official and official["walkoff"] else "inning-ended") if final else None,
                               "runsBefore": before, "runsOnPlay": runs, "runsAfter": runs_so_far,
                               "inningRuns": official_runs, "summaries": [row["result"]]})
        if runs_so_far != official_runs:
            raise ValueError(f"Inning run mismatch: {inning}{half}")
    if line_scores and set(line_scores) != seen:
        raise ValueError(f"Missing or unexpected played innings: {game.get('gameId')} "
                         f"scores={sorted(line_scores)}, parsed={sorted(seen)}")
    return events

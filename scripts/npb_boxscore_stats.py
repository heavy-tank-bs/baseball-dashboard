"""Parse NPB official box scores into the site's SportsNavi cache schema.

No network access or third-party dependencies. Identity lookup accepts
(team, normalize_name(full_name)) -> SportsNavi ID, with ('', name) as a
globally unique fallback; ('npb', NPB_ID) and ('npb_name', NPB_ID) may supply
an explicit ID and display name for the abbreviated box-score labels.
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser


TEAMS = {
    "読売ジャイアンツ": "巨人", "阪神タイガース": "阪神",
    "横浜DeNAベイスターズ": "DeNA", "広島東洋カープ": "広島",
    "東京ヤクルトスワローズ": "ヤクルト", "中日ドラゴンズ": "中日",
    "福岡ソフトバンクホークス": "ソフトバンク",
    "北海道日本ハムファイターズ": "日本ハム",
    "千葉ロッテマリーンズ": "ロッテ", "オリックス・バファローズ": "オリックス",
    "埼玉西武ライオンズ": "西武", "東北楽天ゴールデンイーグルス": "東北楽天",
}


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


class _Node:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        return "".join(child.text() if isinstance(child, _Node) else child for child in self.children)

    def descendants(self, tag):
        for child in self.children:
            if isinstance(child, _Node):
                if child.tag == tag:
                    yield child
                yield from child.descendants(tag)

    def direct(self, tag):
        return [child for child in self.children if isinstance(child, _Node) and child.tag == tag]


class _Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = _Node()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.current.children.append("\n")
            return
        node = _Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {"area", "base", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _identity(row, team, lookup):
    links = [a for a in row.descendants("a") if re.search(r"/bis/players/\d+\.html", a.attrs.get("href", ""))]
    if len(links) != 1:
        raise ValueError(f"Expected one player link in {team} row")
    link = links[0]
    npb_id = re.search(r"/players/(\d+)\.html", link.attrs["href"]).group(1)
    label = normalize_name(link.text())
    player_id = lookup.get(("npb", npb_id))
    player_name = lookup.get(("npb_name", npb_id))
    if player_id:
        if not player_name:
            names = [name for (scope, name), value in lookup.items() if scope == team and value == player_id]
            if len(names) != 1:
                raise ValueError(f"Missing full name for NPB player {npb_id}: {team} {label}")
            player_name = names[0]
        return str(player_id), player_name
    if player_name:
        name = normalize_name(player_name)
        player_id = lookup.get((team, name)) or lookup.get(("", name))
        if player_id:
            return str(player_id), player_name
    for scope in (team, ""):
        candidates = {(str(value), name) for (key_team, name), value in lookup.items()
                      if key_team == scope and name.startswith(label)}
        ids = {value for value, name in candidates}
        if len(ids) == 1:
            return next(iter(ids)), min(name for value, name in candidates)
        if len(ids) > 1:
            raise ValueError(f"Ambiguous player {team} {label} (NPB {npb_id})")
    raise ValueError(f"Unknown player {team} {label} (NPB {npb_id})")


def _cells(row):
    return [c for c in row.children if isinstance(c, _Node) and c.tag in {"th", "td"}]


def _integer(cell):
    value = normalize_name(cell.text())
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"Expected integer box-score value, got {value!r}")
    return int(value)


def _results(cells):
    results = []
    for cell in cells:
        # Each nonempty inning cell is one PA; a BR is used if several PAs
        # share a cell. Ignore indentation in the HTML source.
        raw = cell.text().strip()
        for part in re.split(r"\n", raw):
            result = normalize_name(re.sub(r"[①-⑳]", "", part))
            if result and result not in {"-", "―", "—", "－"}:
                results.append(result)
    return results


def parse_boxscore(html: str, id_lookup: dict) -> tuple[dict, dict]:
    """Return (batting_by_team, pitching_decisions); reject ambiguous input."""
    root = _Tree(html).root
    tables = {n.attrs.get("id"): n for n in root.descendants("table")}
    batting, decisions, pitching_totals = {}, {}, {}
    for side in ("t", "b"):
        table = tables.get(f"tablefix_{side}_b")
        pitching = tables.get(f"tablefix_{side}_p")
        if table is None or pitching is None:
            raise ValueError("Missing one of four official batting/pitching tables")
        section = table.parent
        while section and section.tag != "section":
            section = section.parent
        heading = next(section.descendants("h4"), None) if section else None
        team = TEAMS.get(heading.text().strip() if heading else "")
        if not team:
            raise ValueError("Unrecognized team heading")
        headers = [normalize_name(c.text()) for c in _cells(table.direct("thead")[0].direct("tr")[0])]
        if headers[:8] != ["", "守備", "選手", "打数", "得点", "安打", "打点", "盗塁"]:
            raise ValueError(f"Unexpected batting headers: {headers[:8]}")
        team_rows = {}
        batting_order = 0
        for order, row in enumerate(table.direct("tbody")[0].direct("tr"), 1):
            cells = _cells(row)
            if len(cells) != len(headers):
                raise ValueError(f"Unexpected batting column count for {team}")
            order_label = normalize_name(cells[0].text())
            is_starter = bool(order_label)
            if is_starter:
                if not re.fullmatch(r"[1-9]", order_label) or int(order_label) != batting_order + 1:
                    raise ValueError(f"Invalid batting-order sequence for {team}: {order_label!r}")
                batting_order = int(order_label)
            elif not batting_order:
                raise ValueError(f"Substitute without a preceding batting slot for {team}")
            player_id, player = _identity(row, team, id_lookup)
            details = _results(cells[8:])
            walks = sum("四球" in d or "故意四" in d or "敬遠" in d for d in details)
            hbp = sum("死球" in d for d in details)
            bunt = sum("犠" in d and "犠飛" not in d for d in details)
            sac_fly = sum("犠飛" in d for d in details)
            interference = sum("打妨" in d or "捕妨" in d for d in details)
            doubles = sum(bool(re.search(r"[二2]$", d)) for d in details)
            triples = sum(bool(re.search(r"[三3]$", d)) for d in details)
            homers = sum(d.endswith("本") or "本塁打" in d for d in details)
            ab, runs, hits, rbi, steals = map(_integer, cells[3:8])
            if len(details) != ab + walks + hbp + bunt + sac_fly + interference:
                raise ValueError(f"PA accounting mismatch {team} {player}: AB={ab}, results={details}")
            singles = hits - doubles - triples - homers
            if singles < 0:
                raise ValueError(f"Invalid extra-base hit counts {team} {player}")
            stats = {"order": order, "battingOrder": batting_order, "isStarter": is_starter,
                     "player": player, "playerId": player_id,
                     "ab": ab, "runs": runs, "hits": hits, "rbi": rbi,
                     "walks": walks, "hitByPitch": hbp, "sacBunts": bunt,
                     "sacFlies": sac_fly, "steals": steals,
                     "strikeouts": sum("三振" in d or "振逃" in d for d in details),
                     "homeRuns": homers, "doubles": doubles, "triples": triples,
                     "singles": singles, "plateAppearances": len(details)}
            if player_id in team_rows:
                raise ValueError(f"Duplicate player in batting table: {team} {player}")
            team_rows[player_id] = stats
            team_rows[player] = stats
        if not team_rows:
            raise ValueError(f"Empty batting table: {team}")
        if batting_order != 9:
            raise ValueError(f"Expected nine starting batting slots for {team}, got {batting_order}")
        batting[team] = team_rows
        pitching_totals[team] = dict.fromkeys(("plateAppearances", "hits", "homeRuns", "walks", "hitByPitch", "strikeouts"), 0)
        for row in pitching.direct("tbody")[0].direct("tr"):
            cells = _cells(row)
            if len(cells) != 14:
                raise ValueError(f"Unexpected pitching column count for {team}")
            player_id, player = _identity(row, team, id_lookup)
            marker = normalize_name(cells[0].text())
            if marker not in {"", "○", "◯", "●", "H", "S"}:
                raise ValueError(f"Unknown pitching decision {marker!r}")
            decisions[player_id] = {"pitcherId": player_id, "player": player,
                                    "wins": int(marker in {"○", "◯"}),
                                    "losses": int(marker == "●"),
                                    "saves": int(marker == "S"),
                                    "holds": int(marker == "H")}
            for key, index in (("plateAppearances", 3), ("hits", 5), ("homeRuns", 6),
                               ("walks", 7), ("hitByPitch", 8), ("strikeouts", 9)):
                pitching_totals[team][key] += _integer(cells[index])
    if len(batting) != 2 or not decisions:
        raise ValueError("Incomplete official box score")
    for team, team_rows in batting.items():
        opponent = next(name for name in batting if name != team)
        for key, expected in pitching_totals[opponent].items():
            actual = sum(row[key] for identity, row in team_rows.items() if identity == row["playerId"])
            if actual != expected:
                raise ValueError(f"Batting/pitching {key} mismatch for {team}: {actual} != {expected}")
    return batting, decisions

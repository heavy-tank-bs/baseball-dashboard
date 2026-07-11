from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "summary" / "uniform_numbers.js"
ROSTER_URL = "https://npb.jp/bis/players/active/rst_{code}.html"
TEAM_CODES = {
    "g": "巨人",
    "t": "阪神",
    "db": "DeNA",
    "c": "広島",
    "s": "ヤクルト",
    "d": "中日",
    "h": "ソフトバンク",
    "f": "日本ハム",
    "m": "ロッテ",
    "b": "オリックス",
    "l": "西武",
    "e": "東北楽天",
}
NAME_VARIANTS = str.maketrans(
    {
        "﨑": "崎",
        "髙": "高",
        "神": "神",
        "濵": "浜",
        "邉": "辺",
        "邊": "辺",
        "澤": "沢",
    }
)


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).translate(NAME_VARIANTS)
    return re.sub(r"[\s\u3000]+", "", normalized)


def name_aliases(value: str) -> set[str]:
    normalized = normalize_name(value)
    aliases = {normalized} if normalized else set()
    without_initials = re.sub(r"^(?:[A-Za-z]\.)+", "", normalized)
    if without_initials:
        aliases.add(without_initials)
    return aliases


def fetch_team_roster(session: requests.Session, code: str) -> list[tuple[str, str]]:
    response = session.get(ROSTER_URL.format(code=code), timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[tuple[str, str]] = []
    for unit in soup.select(".player_unit_1"):
        position = unit.select_one(".pos")
        name = unit.select_one(".name")
        if position is None or name is None:
            continue
        position_text = unicodedata.normalize("NFKC", position.get_text(" ", strip=True))
        number_match = re.match(r"\s*(\d+)", position_text)
        if number_match is None:
            continue
        rows.append((name.get_text(" ", strip=True), number_match.group(1)))
    if not rows:
        raise RuntimeError(f"No roster entries found: {code}")
    return rows


def build_payload() -> dict:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    teams: dict[str, dict[str, str]] = {}
    sources: list[str] = []
    for code, team in TEAM_CODES.items():
        url = ROSTER_URL.format(code=code)
        sources.append(url)
        alias_numbers: dict[str, set[str]] = defaultdict(set)
        for player, number in fetch_team_roster(session, code):
            for alias in name_aliases(player):
                alias_numbers[alias].add(number)
        teams[team] = {
            alias: next(iter(numbers))
            for alias, numbers in sorted(alias_numbers.items())
            if len(numbers) == 1
        }
    return {
        "season": "2026",
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "NPB.jp 現役選手一覧",
        "sourceUrls": sources,
        "teams": teams,
    }


def render_javascript(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    helper = r'''

(() => {
  const variants = {
    "﨑": "崎",
    "髙": "高",
    "神": "神",
    "濵": "浜",
    "邉": "辺",
    "邊": "辺",
    "澤": "沢",
  };

  function normalizePlayerName(value) {
    return `${value || ""}`
      .normalize("NFKC")
      .replace(/[﨑髙神濵邉邊澤]/g, (character) => variants[character] || character)
      .replace(/[\s\u3000]+/g, "");
  }

  function playerNameCandidates(value) {
    const normalized = normalizePlayerName(value);
    const withoutInitials = normalized.replace(/^(?:[A-Za-z]\.)+/, "");
    return withoutInitials && withoutInitials !== normalized
      ? [normalized, withoutInitials]
      : [normalized];
  }

  window.getNpbUniformNumber = function getNpbUniformNumber(team, player, fallback = "", season = "") {
    const data = window.NPB_UNIFORM_NUMBERS;
    const fallbackValue = `${fallback || ""}`.trim();
    if (!data?.teams) return fallbackValue;
    if (season && data.season && `${season}` !== `${data.season}`) return fallbackValue;

    const teamCandidates = `${team || ""}`
      .split(/\s*\/\s*/)
      .map((value) => value.trim())
      .filter(Boolean);
    const nameCandidates = playerNameCandidates(player);
    for (const teamName of teamCandidates) {
      const roster = data.teams[teamName];
      if (!roster) continue;
      for (const playerName of nameCandidates) {
        if (roster[playerName]) return `${roster[playerName]}`;
      }
    }
    return fallbackValue;
  };
})();
'''
    return f"window.NPB_UNIFORM_NUMBERS = {data};\n" + helper.lstrip("\n")


def main() -> None:
    payload = build_payload()
    content = render_javascript(payload)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    player_count = sum(len(players) for players in payload["teams"].values())
    print(f"Wrote {OUTPUT_PATH} ({len(payload['teams'])} teams, {player_count} lookup keys)")


if __name__ == "__main__":
    main()

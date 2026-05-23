from __future__ import annotations

import base64
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

import boto3


DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MAX_OUTPUT_TOKENS = 2500
MAX_REQUEST_BYTES = 1_000_000
MAX_SCREEN_CONTEXT_CHARS = 6500
MAX_SEARCH_CONTEXT_CHARS = 16000

DATA_BUCKET = os.environ.get("DATA_BUCKET", "")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "prod/").strip("/")
if DATA_PREFIX:
    DATA_PREFIX += "/"

PITCHER_TERMS = (
    "pitcher",
    "era",
    "whip",
    "fip",
    "k/9",
    "bb/9",
    "\u6295\u624b",
    "\u5148\u767a",
    "\u767b\u677f",
    "\u596a\u4e09\u632f",
    "\u4e09\u632f",
    "\u56db\u7403",
    "\u9632\u5fa1\u7387",
    "\u5931\u70b9",
)
BATTER_TERMS = (
    "batter",
    "hitter",
    "ops",
    "wrc",
    "wrc+",
    "hr",
    "\u91ce\u624b",
    "\u6253\u8005",
    "\u6253\u7387",
    "\u51fa\u5841\u7387",
    "\u9577\u6253\u7387",
    "\u672c\u5841\u6253",
    "\u30db\u30fc\u30e0\u30e9\u30f3",
    "\u5f97\u70b9\u570f",
    "\u6253\u70b9",
)

s3 = boto3.client("s3")


def compact_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\s\u3000\-_./\\|,:;()\[\]{}<>\"'`]+", "", text)


def clean_text(value: Any, limit: int = 1000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def to_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def to_int(value: Any) -> int:
    number = to_float(value)
    return int(number) if number is not None else 0


def innings_to_outs(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    if "." in text:
        whole, fraction = text.split(".", 1)
        return to_int(whole) * 3 + min(to_int(fraction[:1]), 2)
    return to_int(text) * 3


def fmt(value: Any, suffix: str = "") -> str:
    if value in (None, "", "-"):
        return "-"
    return f"{value}{suffix}"


def pct(value: Any) -> str:
    number = to_float(value)
    return "-" if number is None else f"{number:.1f}%"


def s3_key(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("../"):
        normalized = normalized[3:]
    normalized = normalized.lstrip("/")
    if normalized.startswith(DATA_PREFIX):
        return normalized
    return DATA_PREFIX + normalized


def read_s3_text(path: str) -> str:
    if not DATA_BUCKET:
        raise RuntimeError("DATA_BUCKET is not set.")
    response = s3.get_object(Bucket=DATA_BUCKET, Key=s3_key(path))
    return response["Body"].read().decode("utf-8-sig")


def read_s3_json(path: str) -> dict[str, Any]:
    return json.loads(read_s3_text(path))


def read_s3_js_assignment(path: str) -> dict[str, Any]:
    text = read_s3_text(path)
    if "=" not in text:
        raise ValueError(f"Invalid assignment file: {path}")
    body = text.split("=", 1)[1].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


@lru_cache(maxsize=512)
def read_s3_json_cached(path: str) -> dict[str, Any]:
    try:
        return read_s3_json(path)
    except Exception:
        return {}


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = compact_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


class DashboardSearchIndex:
    def __init__(self) -> None:
        started = time.monotonic()
        self.pitch_manifest = read_s3_js_assignment("summary/manifest.js")
        self.batter_manifest = read_s3_js_assignment("summary/batter_manifest.js")
        self.pitcher_entries = self.pitch_manifest.get("entries", [])
        self.batter_entries = self.batter_manifest.get("entries", [])
        self.pitcher_totals = read_s3_json("summary/player_totals.json").get("players", [])
        self.batter_totals = read_s3_json("summary/batter_totals.json").get("players", [])
        self.pitcher_names = unique_preserve_order(
            [entry.get("player", "") for entry in self.pitcher_entries]
            + [row.get("player", "") for row in self.pitcher_totals]
        )
        self.batter_names = unique_preserve_order(
            [entry.get("player", "") for entry in self.batter_entries]
            + [row.get("player", "") for row in self.batter_totals]
        )
        self.teams = unique_preserve_order(
            [team.get("name", "") for team in self.pitch_manifest.get("teams", [])]
            + [team.get("name", "") for team in self.batter_manifest.get("teams", [])]
            + [row.get("team", "") for row in self.pitcher_totals]
            + [row.get("team", "") for row in self.batter_totals]
        )
        self.latest_pitcher_year = max((str(row.get("year", "")) for row in self.pitcher_totals), default="")
        self.latest_batter_year = max((str(row.get("year", "")) for row in self.batter_totals), default="")
        self.loaded_seconds = round(time.monotonic() - started, 3)

    def health(self) -> dict[str, Any]:
        return {
            "pitcherEntries": len(self.pitcher_entries),
            "batterEntries": len(self.batter_entries),
            "pitcherTotals": len(self.pitcher_totals),
            "batterTotals": len(self.batter_totals),
            "loadedSeconds": self.loaded_seconds,
        }

    def search(self, question: str) -> str:
        query = clean_text(question, 1200)
        q_compact = compact_text(query)
        if not q_compact:
            return ""

        years = sorted(set(re.findall(r"20\d{2}", query)))
        dates = sorted(set(re.findall(r"20\d{2}-\d{2}-\d{2}", query)))
        pitcher_names = self._matched_names(q_compact, self.pitcher_names)
        batter_names = self._matched_names(q_compact, self.batter_names)
        teams = self._matched_names(q_compact, self.teams)

        wants_pitcher = bool(pitcher_names) or any(compact_text(term) in q_compact for term in PITCHER_TERMS)
        wants_batter = bool(batter_names) or any(compact_text(term) in q_compact for term in BATTER_TERMS)
        if not wants_pitcher and not wants_batter:
            wants_pitcher = wants_batter = True

        parts = [
            "# Full data search results",
            f"Query: {query}",
            (
                "Detected: "
                f"pitchers={', '.join(pitcher_names) or '-'} / "
                f"batters={', '.join(batter_names) or '-'} / "
                f"teams={', '.join(teams) or '-'} / "
                f"years={', '.join(years) or '-'} / dates={', '.join(dates) or '-'}"
            ),
        ]

        if wants_pitcher:
            pitcher_total_rows = self._search_pitcher_totals(q_compact, pitcher_names, teams, years)
            pitcher_game_rows = self._search_pitcher_games(q_compact, pitcher_names, teams, years, dates)
            parts.append(self._format_pitcher_totals(pitcher_total_rows))
            parts.append(self._format_pitcher_games(pitcher_game_rows))

        if wants_batter:
            batter_total_rows = self._search_batter_totals(q_compact, batter_names, teams, years)
            batter_game_rows = self._search_batter_games(q_compact, batter_names, teams, years, dates)
            parts.append(self._format_batter_totals(batter_total_rows))
            parts.append(self._format_batter_games(batter_game_rows))

        return "\n\n".join(part for part in parts if part)[:MAX_SEARCH_CONTEXT_CHARS]

    def _matched_names(self, q_compact: str, names: list[str]) -> list[str]:
        matches: list[str] = []
        for name in names:
            key = compact_text(name)
            variants = [key]
            variants.extend(compact_text(part) for part in re.split(r"[\s\u3000]+", str(name or "")) if part)
            if len(key) >= 4:
                variants.append(key[:4])
            if len(key) >= 3:
                variants.append(key[:3])
            variants = [variant for variant in variants if len(variant) >= 2]
            if any(variant in q_compact for variant in variants):
                matches.append(name)
        return matches[:8]

    def _row_matches(self, row: dict[str, Any], names: list[str], teams: list[str], years: list[str]) -> bool:
        if names and not self._player_matches(row.get("player"), names):
            return False
        if teams and not self._team_matches(row, teams):
            return False
        if years and str(row.get("year", "")) not in years:
            return False
        return True

    def _entry_matches(
        self, entry: dict[str, Any], names: list[str], teams: list[str], years: list[str], dates: list[str]
    ) -> bool:
        if names and not self._player_matches(entry.get("player"), names):
            return False
        if teams and not self._team_matches(entry, teams):
            return False
        if years and not any(str(entry.get("date", "")).startswith(year) for year in years):
            return False
        if dates and entry.get("date") not in dates:
            return False
        return True

    def _player_matches(self, player: Any, names: list[str]) -> bool:
        player_key = compact_text(player)
        if not player_key:
            return False
        for name in names:
            name_key = compact_text(name)
            if player_key == name_key or player_key in name_key or name_key in player_key:
                return True
        return False

    def _team_matches(self, row: dict[str, Any], teams: list[str]) -> bool:
        row_values = [row.get("team", ""), *(row.get("teams") or [])]
        haystack = {compact_text(value) for value in row_values}
        return any(compact_text(team) in haystack for team in teams)

    def _search_pitcher_totals(
        self, q_compact: str, names: list[str], teams: list[str], years: list[str]
    ) -> list[dict[str, Any]]:
        metric, reverse = self._pitcher_metric(q_compact)
        effective_years = years or ([self.latest_pitcher_year] if not names else [])
        rows = [row for row in self.pitcher_totals if self._row_matches(row, names, teams, effective_years)]
        if not rows and effective_years:
            rows = [row for row in self.pitcher_totals if self._row_matches(row, names, teams, [])]
        rows.sort(key=lambda row: self._metric_sort_value(row, metric, reverse), reverse=reverse)
        return rows[:8]

    def _search_batter_totals(
        self, q_compact: str, names: list[str], teams: list[str], years: list[str]
    ) -> list[dict[str, Any]]:
        metric, reverse = self._batter_metric(q_compact)
        effective_years = years or ([self.latest_batter_year] if not names else [])
        rows = [row for row in self.batter_totals if self._row_matches(row, names, teams, effective_years)]
        if not rows and effective_years:
            rows = [row for row in self.batter_totals if self._row_matches(row, names, teams, [])]
        rows.sort(key=lambda row: self._metric_sort_value(row, metric, reverse), reverse=reverse)
        return rows[:10]

    def _search_pitcher_games(
        self, q_compact: str, names: list[str], teams: list[str], years: list[str], dates: list[str]
    ) -> list[dict[str, Any]]:
        rows = [entry for entry in self.pitcher_entries if self._entry_matches(entry, names, teams, years, dates)]
        if not rows and not (names or teams or years or dates):
            rows = self.pitcher_entries[:]
        if self._asks_best(q_compact):
            rows.sort(key=self._pitcher_game_quality, reverse=True)
        else:
            rows.sort(key=lambda entry: (self._entry_score(entry, q_compact), entry.get("date", "")), reverse=True)
        return rows[:12]

    def _search_batter_games(
        self, q_compact: str, names: list[str], teams: list[str], years: list[str], dates: list[str]
    ) -> list[dict[str, Any]]:
        rows = [entry for entry in self.batter_entries if self._entry_matches(entry, names, teams, years, dates)]
        if not rows and not (names or teams or years or dates):
            rows = self.batter_entries[:]
        if self._asks_best(q_compact):
            rows.sort(key=self._batter_game_quality, reverse=True)
        else:
            rows.sort(key=lambda entry: (self._entry_score(entry, q_compact), entry.get("date", "")), reverse=True)
        return rows[:12]

    def _entry_score(self, entry: dict[str, Any], q_compact: str) -> int:
        fields = [
            entry.get("player"),
            entry.get("team"),
            entry.get("date"),
            entry.get("gameId"),
            entry.get("matchup"),
            entry.get("title"),
        ]
        pitch_mix = entry.get("dashboard", {}).get("pitchMix", [])
        fields.extend(row.get("pitchType") for row in pitch_mix if isinstance(row, dict))
        haystack = compact_text(" ".join(str(field or "") for field in fields))
        score = 0
        for token in self._query_tokens(q_compact):
            if token in haystack:
                score += 8
        if compact_text(entry.get("player")) and compact_text(entry.get("player")) in q_compact:
            score += 80
        if compact_text(entry.get("team")) and compact_text(entry.get("team")) in q_compact:
            score += 30
        if compact_text(entry.get("date")) and compact_text(entry.get("date")) in q_compact:
            score += 50
        return score

    def _query_tokens(self, q_compact: str) -> list[str]:
        tokens = [token for token in re.split(r"[^\w\u3040-\u30ff\u3400-\u9fff]+", q_compact) if len(token) >= 2]
        return tokens[:24]

    def _asks_best(self, q_compact: str) -> bool:
        terms = ("best", "top", "\u4e00\u756a", "\u6700\u9ad8", "\u30d9\u30b9\u30c8", "\u597d\u8abf", "\u512a\u79c0")
        return any(compact_text(term) in q_compact for term in terms)

    def _pitcher_metric(self, q_compact: str) -> tuple[str, bool]:
        if "fip" in q_compact:
            return "fip", False
        if "whip" in q_compact:
            return "whip", False
        if "era" in q_compact or compact_text("\u9632\u5fa1\u7387") in q_compact:
            return "era", False
        if "k/9" in q_compact or compact_text("\u596a\u4e09\u632f") in q_compact or compact_text("\u4e09\u632f") in q_compact:
            return "kPer9", True
        if "bb/9" in q_compact or compact_text("\u56db\u7403") in q_compact:
            return "bbPer9", False
        if compact_text("\u88ab\u6253\u7387") in q_compact:
            return "battingAverageAllowed", False
        return "inningsOuts", True

    def _batter_metric(self, q_compact: str) -> tuple[str, bool]:
        if compact_text("\u5f97\u70b9\u570f") in q_compact:
            return "scoringPositionBattingAverage", True
        if "wrc+" in q_compact or "wrc" in q_compact:
            return "wrcPlus", True
        if "ops" in q_compact:
            return "ops", True
        if "hr" in q_compact or compact_text("\u672c\u5841\u6253") in q_compact or compact_text("\u30db\u30fc\u30e0\u30e9\u30f3") in q_compact:
            return "homeRuns", True
        if compact_text("\u51fa\u5841\u7387") in q_compact:
            return "onBasePercentage", True
        if compact_text("\u9577\u6253\u7387") in q_compact:
            return "sluggingPercentage", True
        if compact_text("\u6253\u7387") in q_compact or compact_text("\u5b89\u6253") in q_compact:
            return "battingAverage", True
        return "plateAppearances", True

    def _metric_sort_value(self, row: dict[str, Any], metric: str, reverse: bool) -> float:
        value = to_float(row.get(metric))
        if value is None:
            return float("-inf") if reverse else float("inf")
        return value

    def _pitcher_game_quality(self, entry: dict[str, Any]) -> float:
        statline = entry.get("statline", {})
        outs = innings_to_outs(statline.get("innings"))
        strikeouts = to_int(statline.get("k"))
        walks = to_int(statline.get("bb")) + to_int(statline.get("hbp"))
        hits = to_int(statline.get("hits"))
        runs = to_int(statline.get("runs")) + to_int(statline.get("er"))
        pitches = to_int(statline.get("pitches"))
        efficiency = outs / max(pitches, 1) * 20 if pitches else 0
        return outs * 1.8 + strikeouts * 2.4 + efficiency - walks * 1.5 - hits * 1.2 - runs * 4.0

    def _batter_game_quality(self, entry: dict[str, Any]) -> float:
        statline = entry.get("statline", {})
        return (
            to_int(statline.get("hits")) * 4
            + to_int(statline.get("homeRuns")) * 7
            + to_int(statline.get("rbi")) * 2
            + to_int(statline.get("walks")) * 1.2
            - to_int(statline.get("strikeouts")) * 0.8
        )

    def _load_pitcher_detail(self, entry: dict[str, Any]) -> dict[str, Any]:
        detail_path = entry.get("detailPath")
        if not detail_path:
            return {}
        return read_s3_json_cached(detail_path).get("dashboard", {})

    def _format_pitcher_totals(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "## Pitcher season stats\n- No matching pitcher season rows."
        lines = ["## Pitcher season stats"]
        for row in rows:
            lines.append(
                "- "
                f"{row.get('year')} {row.get('team')} {row.get('player')}: "
                f"games {fmt(row.get('games'))}, IP {fmt(row.get('innings'))}, "
                f"ERA {fmt(row.get('era'))}, WHIP {fmt(row.get('whip'))}, FIP {fmt(row.get('fip'))}, "
                f"K/9 {fmt(row.get('kPer9'))}, BB/9 {fmt(row.get('bbPer9'))}, "
                f"K {fmt(row.get('strikeouts'))}, BB {fmt(row.get('walks'))}"
            )
        return "\n".join(lines)

    def _format_batter_totals(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "## Batter season stats\n- No matching batter season rows."
        lines = ["## Batter season stats"]
        for row in rows:
            lines.append(
                "- "
                f"{row.get('year')} {row.get('team')} {row.get('player')}: "
                f"games {fmt(row.get('games'))}, PA {fmt(row.get('plateAppearances'))}, "
                f"AVG {fmt(row.get('battingAverage'))}, OBP {fmt(row.get('onBasePercentage'))}, "
                f"SLG {fmt(row.get('sluggingPercentage'))}, OPS {fmt(row.get('ops'))}, "
                f"wRC+ {fmt(row.get('wrcPlus'))}, HR {fmt(row.get('homeRuns'))}, "
                f"RBI {fmt(row.get('runsBattedIn'))}, RISP AVG {fmt(row.get('scoringPositionBattingAverage'))} "
                f"({fmt(row.get('scoringPositionAtBats'))} AB)"
            )
        return "\n".join(lines)

    def _format_pitcher_games(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "## Pitcher game logs\n- No matching pitcher game rows."
        lines = ["## Pitcher game logs"]
        for entry in entries:
            detail = self._load_pitcher_detail(entry)
            dashboard = {**(entry.get("dashboard") or {}), **detail}
            statline = entry.get("statline", {})
            lines.append(
                "- "
                f"{entry.get('date')} {entry.get('team')} {entry.get('player')} / {entry.get('matchup')}: "
                f"IP {fmt(statline.get('innings'))}, pitches {fmt(statline.get('pitches'))}, "
                f"H {fmt(statline.get('hits'))}, K {fmt(statline.get('k'))}, "
                f"BB {fmt(statline.get('bb'))}, R {fmt(statline.get('runs'))}, ER {fmt(statline.get('er'))}. "
                f"Pitch mix: {self._format_pitch_mix(dashboard.get('pitchMix', []), pitcher=True)} "
                f"Finish: {self._format_finish(dashboard.get('finish'))} "
                f"Outcomes: {self._format_outcomes(dashboard.get('outcomes'))}"
            )
        return "\n".join(lines)

    def _format_batter_games(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "## Batter game logs\n- No matching batter game rows."
        lines = ["## Batter game logs"]
        for entry in entries:
            statline = entry.get("statline", {})
            dashboard = entry.get("dashboard", {})
            lines.append(
                "- "
                f"{entry.get('date')} {entry.get('team')} {entry.get('player')} / {entry.get('matchup')}: "
                f"AB {fmt(statline.get('ab'))}, H {fmt(statline.get('hits'))}, "
                f"HR {fmt(statline.get('homeRuns'))}, RBI {fmt(statline.get('rbi'))}, "
                f"BB {fmt(statline.get('walks'))}, SO {fmt(statline.get('strikeouts'))}. "
                f"Pitch mix faced: {self._format_pitch_mix(dashboard.get('pitchMix', []), pitcher=False)} "
                f"Plate appearances: {self._format_plate_appearances(dashboard.get('plateAppearances', []))}"
            )
        return "\n".join(lines)

    def _format_pitch_mix(self, rows: list[dict[str, Any]], pitcher: bool) -> str:
        if not rows:
            return "-"
        parts: list[str] = []
        for row in rows[:6]:
            base = f"{row.get('pitchType')} {fmt(row.get('count'))}({pct(row.get('ratio'))})"
            if pitcher:
                extras = []
                if row.get("avgSpeed") not in (None, "", "-"):
                    extras.append(f"avg {row.get('avgSpeed')}km/h")
                if row.get("whiffRate") not in (None, "", "-"):
                    extras.append(f"whiff {pct(row.get('whiffRate'))}")
                if row.get("csw") not in (None, "", "-"):
                    extras.append(f"CSW {pct(row.get('csw'))}")
                if row.get("stuffScore") not in (None, "", "-"):
                    extras.append(f"Stuff {row.get('stuffScore')}")
                if extras:
                    base += " [" + ", ".join(extras) + "]"
            parts.append(base)
        return "; ".join(parts)

    def _format_finish(self, finish: dict[str, Any] | None) -> str:
        rows = (finish or {}).get("rows") or []
        if not rows:
            return "-"
        return "; ".join(
            f"{row.get('pitchType')} {fmt(row.get('count'))}({pct(row.get('ratio'))}), "
            f"looking {fmt(row.get('looking'))}/swinging {fmt(row.get('swinging'))}"
            for row in rows[:5]
        )

    def _format_outcomes(self, outcomes: dict[str, Any] | None) -> str:
        rows = (outcomes or {}).get("rows") or []
        rows = [row for row in rows if to_int(row.get("count")) > 0]
        if not rows:
            return "-"
        return "; ".join(f"{row.get('label')} {fmt(row.get('count'))}({pct(row.get('ratio'))})" for row in rows[:6])

    def _format_plate_appearances(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "-"
        return "; ".join(
            f"{row.get('label')} inning {row.get('inning')} {row.get('result')} vs "
            f"{row.get('pitcher')} {row.get('pitchType')} {fmt(row.get('speed'))}"
            for row in rows[:8]
        )


SEARCH_INDEX: DashboardSearchIndex | None = None


def get_search_index() -> DashboardSearchIndex:
    global SEARCH_INDEX
    if SEARCH_INDEX is None:
        SEARCH_INDEX = DashboardSearchIndex()
    return SEARCH_INDEX


def build_input(payload: dict[str, Any], search_context: str) -> str:
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    history_lines = []
    for item in history[-8:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        speaker = "User" if item.get("role") == "user" else "Assistant"
        history_lines.append(f"{speaker}: {clean_text(item.get('content'), 900)}")

    screen_context = clean_text(payload.get("context"), MAX_SCREEN_CONTEXT_CHARS)
    message = clean_text(payload.get("message"), 1000)
    return "\n".join(
        [
            "# Screen context",
            screen_context or "(No visible dashboard context was provided.)",
            "",
            "# Full-data search context",
            search_context or "(No full-data search hits.)",
            "",
            "# Recent conversation",
            "\n".join(history_lines) or "(No prior conversation.)",
            "",
            "# Current user question",
            message,
        ]
    )


def extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    parts: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts).strip()


def call_openai(payload: dict[str, Any], search_context: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set on Lambda.")

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    max_output_tokens = int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS))
    instructions = "\n".join(
        [
            "You are an AI assistant embedded in a Japanese NPB dashboard.",
            "Answer in Japanese.",
            "Use both the visible screen context and the full-data search context as sources of truth.",
            "When the full-data search context has relevant rows, use it even if the current screen does not show those rows.",
            "Do not invent player stats, dates, teams, pitch types, rankings, or conclusions that are not supported by the context.",
            "If the search results are insufficient, say what was missing and suggest a more specific player, team, year, or metric.",
            "Keep answers practical and readable. Prefer 4 to 10 short bullets for comparisons.",
        ]
    )
    request_payload = {
        "model": model,
        "instructions": instructions,
        "input": build_input(payload, search_context),
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail_json = json.loads(detail)
            message = detail_json.get("error", {}).get("message") or detail
        except json.JSONDecodeError:
            message = detail
        raise RuntimeError(message) from error
    return extract_response_text(data) or "回答を生成できませんでした。"


def allowed_origin(request_origin: str | None) -> str:
    allowed = [origin.strip() for origin in os.environ.get("ALLOWED_ORIGIN", "*").split(",") if origin.strip()]
    if "*" in allowed:
        return "*"
    if request_origin and request_origin in allowed:
        return request_origin
    return allowed[0] if allowed else "*"


def json_response(status: int, payload: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False)
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": allowed_origin(origin),
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "content-type",
            "Vary": "Origin",
        },
        "body": body,
    }


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    if len(raw_body.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("Request body is too large.")
    return json.loads(raw_body)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    headers = event.get("headers") or {}
    origin = headers.get("origin") or headers.get("Origin")
    request_context = event.get("requestContext") or {}
    http = request_context.get("http") or {}
    method = (http.get("method") or event.get("httpMethod") or "GET").upper()
    path = event.get("rawPath") or event.get("path") or "/"

    if method == "OPTIONS":
        return json_response(204, {}, origin)

    if method == "GET" and path.endswith("/api/search-health"):
        try:
            return json_response(200, get_search_index().health(), origin)
        except Exception as error:
            return json_response(500, {"error": str(error)}, origin)

    if method != "POST":
        return json_response(404, {"error": "Not found."}, origin)

    try:
        payload = parse_body(event)
        message = clean_text(payload.get("message"), 1000)
        if not message:
            return json_response(400, {"error": "message is required."}, origin)
        search_context = get_search_index().search(message)
        reply = call_openai({**payload, "message": message}, search_context)
        return json_response(200, {"reply": reply}, origin)
    except json.JSONDecodeError:
        return json_response(400, {"error": "Invalid JSON request body."}, origin)
    except ValueError as error:
        return json_response(413, {"error": str(error)}, origin)
    except Exception as error:
        return json_response(500, {"error": str(error)}, origin)

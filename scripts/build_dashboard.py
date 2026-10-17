import argparse
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import requests
from bs4 import BeautifulSoup
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle
from playwright.sync_api import sync_playwright


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
BASE_URL = "https://baseball.yahoo.co.jp"

NAVY = "#0F2340"
GOLD = "#C8A55A"
BG = "#F4F1EA"
CARD = "#FBF9F4"
TEXT = "#162235"
MUTED = "#6F7A87"
GRID = "#D8D0C4"
HEAT_COLORS = ["#F8F3E6", "#EFD49A", "#DFA650", "#B87A1F", "#7C4B0C"]

FONT_CANDIDATES = [
    Path(r"C:\Windows\Fonts\meiryo.ttc"),
    Path(r"C:\Windows\Fonts\YuGothM.ttc"),
    Path(r"C:\Windows\Fonts\msgothic.ttc"),
]

HIT_WORDS = ("安",)
HIT_RESULT_PATTERN = re.compile(r"(安|[2２]|[3３]|本)$")
AB_EXCLUDE = ("四球", "死球", "犠打", "犠飛")
SWING_MISS_WORDS = ("空振り", "空三振", "バ三振", "振逃")
STRIKEOUT_WORDS = ("三振", "振逃")
GROUNDER_WORDS = ("ゴロ", "併打")
FLY_WORDS = ("飛", "直", "ライナー")
HEATMAP_WIDTH = 54.0
HEATMAP_HEIGHT = 63.0
HEATMAP_SPLITS = 5
STRAIGHT_PITCH_TYPES = {"ストレート"}
PAGE_FIGSIZE = (8.9556, 13.7334)
OUTPUT_DPI = 180
DISPLAY_INNINGS = tuple(range(1, 10))
JINA_PREFIX = "https://r.jina.ai/http://"
MAX_SCORE_INNINGS = 12
MAX_BATTERS_PER_HALF = 20
COUNT_BUCKETS = ("初球", "追い込み前", "2ストライク以降", "フルカウント", "不明")
PITCH_COLORS = [NAVY, "#355C8C", "#6A89B4", GOLD, "#D6C192", "#9D8B75", "#7D97B5"]


def text(node):
    if node is None:
        return ""
    return node.get_text(" ", strip=True).replace("\xa0", " ")


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "-", value)
    value = re.sub(r"\s+", "", value)
    return value or "dashboard"


def normalize_date_folder(date_jp: str) -> str:
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_jp or "")
    if not m:
        return "unknown-date"
    year, month, day = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def resolve_manifest_script(base_output_dir: Path, explicit_manifest_script: str | None = None) -> Path | None:
    if explicit_manifest_script:
        manifest_script = Path(explicit_manifest_script).expanduser().resolve()
        if not manifest_script.exists():
            raise FileNotFoundError(f"Manifest builder not found: {manifest_script}")
        return manifest_script

    candidates = []
    cwd = Path.cwd().resolve()
    candidates.extend([base_output_dir, *base_output_dir.parents, cwd, *cwd.parents])
    seen = set()
    for root in candidates:
        if root in seen:
            continue
        seen.add(root)
        manifest_script = root / "summary" / "build_manifest.py"
        generated_dir = root / "generated"
        if not manifest_script.exists() or not generated_dir.exists():
            continue
        try:
            base_output_dir.relative_to(generated_dir)
        except ValueError:
            continue
        return manifest_script
    return None


def refresh_manifest(manifest_script: Path) -> Path:
    spec = importlib.util.spec_from_file_location("pitch_dashboard_manifest_build", manifest_script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.main()
    return manifest_script.with_name("manifest.js")


def pick_font():
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("Japanese font not found")


def setup_style():
    font_path = pick_font()
    font_manager.fontManager.addfont(str(font_path))
    font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
    mpl.rcParams["font.family"] = font_name
    mpl.rcParams["axes.edgecolor"] = GRID
    mpl.rcParams["axes.labelcolor"] = TEXT
    mpl.rcParams["xtick.color"] = TEXT
    mpl.rcParams["ytick.color"] = TEXT


def pixels_to_points(px: float) -> float:
    return px * 72.0 / OUTPUT_DPI


def axes_y_from_pixels(ax, px: float) -> float:
    axes_height = ax.get_position().height * ax.figure.get_figheight() * OUTPUT_DPI
    return 0 if axes_height == 0 else px / axes_height


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def parse_title_metadata(title: str) -> dict:
    clean = title.strip()
    m = re.search(r"(?P<date>\d{4}年\d+月\d+日)\s+(?P<matchup>.+?)\s+(一球速報|試合出場成績)", clean)
    if not m:
        return {"date_jp": "", "matchup": ""}
    date_jp = m.group("date")
    matchup = m.group("matchup").replace("vs.", "vs")
    return {"date_jp": date_jp, "matchup": matchup}


def parse_matchup_table(table) -> dict:
    headers = [text(th) for th in table.select("thead th")]
    cells = table.select("tbody tr td")
    if len(cells) < 4 or len(headers) < 2:
        return {}
    if headers[0] == "投手":
        pitcher_idx, batter_idx = 0, 2
    elif headers[0] == "打者":
        batter_idx, pitcher_idx = 0, 2
    else:
        pitcher_idx, batter_idx = 0, 2
    pitcher_link = cells[pitcher_idx].select_one("a")
    batter_link = cells[batter_idx].select_one("a")
    pitcher_id = None
    batter_id = None
    if pitcher_link and pitcher_link.get("href"):
        m = re.search(r"/npb/player/(\d+)/top", pitcher_link["href"])
        pitcher_id = m.group(1) if m else None
    if batter_link and batter_link.get("href"):
        m = re.search(r"/npb/player/(\d+)/top", batter_link["href"])
        batter_id = m.group(1) if m else None
    return {
        "pitcher": text(pitcher_link) or text(cells[pitcher_idx]),
        "pitcher_id": pitcher_id,
        "pitcher_hand": text(cells[pitcher_idx + 1]),
        "batter": text(batter_link) or text(cells[batter_idx]),
        "batter_id": batter_id,
        "batter_hand": text(cells[batter_idx + 1]),
    }


def parse_pitch_table(table) -> list[dict]:
    rows = []
    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        rows.append(
            {
                "seq": text(tds[0]),
                "pitch_no": text(tds[1]),
                "pitch_type": text(tds[2]).replace(" - -", ""),
                "speed": text(tds[3]),
                "result": text(tds[4]),
            }
        )
    return rows


def parse_markers(soup: BeautifulSoup) -> dict:
    markers = {}
    for marker in soup.select(".bb-allocationChartArea span.bb-icon__ballCircle"):
        seq = text(marker)
        style = marker.get("style", "")
        top = re.search(r"top:([0-9.]+)px", style)
        left = re.search(r"left:([0-9.]+)px", style)
        markers[seq] = {
            "top": float(top.group(1)) if top else None,
            "left": float(left.group(1)) if left else None,
        }
    return markers


def fetch_markdown_via_jina(url: str) -> str:
    normalized = url.removeprefix("https://").removeprefix("http://")
    resp = requests.get(f"{JINA_PREFIX}{normalized}", headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    return resp.text


def strip_markdown_links(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return value.strip()


def split_markdown_row(line: str) -> list[str]:
    return [strip_markdown_links(cell) for cell in line.strip().strip("|").split("|")]


def parse_markdown_player_line(line: str, role_suffix: str) -> dict:
    match = re.search(
        rf"\[([^\]]+)\]\(https?://baseball\.yahoo\.co\.jp/npb/player/(\d+)/top\)#\d+\s+([左右両]){role_suffix}",
        line,
    )
    if not match:
        return {}
    name, player_id, hand = match.groups()
    return {"name": name, "id": player_id, "hand": hand}


def parse_pitch_rows_markdown(lines: list[str]) -> list[dict]:
    header = "| 投球数 | 球種 | 球速 | 結果 |"
    for idx, line in enumerate(lines):
        if line.strip() != header:
            continue
        rows = []
        for row_line in lines[idx + 2 :]:
            if not row_line.startswith("|"):
                break
            cells = split_markdown_row(row_line)
            if len(cells) < 5 or not cells[0].isdigit():
                break
            rows.append(
                {
                    "seq": cells[0],
                    "pitch_no": cells[1],
                    "pitch_type": cells[2].replace(" - -", ""),
                    "speed": cells[3],
                    "result": cells[4],
                }
            )
        return rows
    return []


def fetch_score_page_via_jina(game_id: str, index: str) -> dict:
    score_url = f"{BASE_URL}/npb/game/{game_id}/score?index={index}"
    markdown = fetch_markdown_via_jina(score_url)
    lines = markdown.splitlines()
    title_line = next((line.removeprefix("Title: ").strip() for line in lines if line.startswith("Title: ")), "")
    pitch_rows = parse_pitch_rows_markdown(lines)
    if not pitch_rows:
        return {
            "index": index,
            "prev": None,
            "metadata": parse_title_metadata(title_line),
            "matchup": {},
            "pitch_rows": [],
            "markers": {},
        }
    batter = parse_markdown_player_line(next((line for line in lines if line.startswith("_打者_")), ""), "打")
    pitcher = parse_markdown_player_line(next((line for line in lines if line.startswith("_投手_")), ""), "投")
    return {
        "index": index,
        "prev": None,
        "metadata": parse_title_metadata(title_line),
        "matchup": {
            "pitcher": pitcher.get("name"),
            "pitcher_id": pitcher.get("id"),
            "pitcher_hand": pitcher.get("hand"),
            "batter": batter.get("name"),
            "batter_id": batter.get("id"),
            "batter_hand": batter.get("hand"),
        },
        "pitch_rows": pitch_rows,
        "markers": {},
    }


def fetch_score_page(session: requests.Session, game_id: str, index: str | None) -> dict:
    score_url = f"{BASE_URL}/npb/game/{game_id}/score"
    if index:
        score_url = f"{score_url}?index={index}"
    resp = session.get(score_url, timeout=30)
    resp.raise_for_status()
    return parse_score_page_html(resp.text, index)


def parse_score_page_html(html: str, index: str | None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    prev = soup.select_one("#btn_prev")
    tables = soup.select("#pitchesDetail table")
    if len(tables) < 6:
        return {
            "index": index or "live",
            "prev": prev.get("index") if prev else None,
            "metadata": parse_title_metadata(text(soup.title)),
            "matchup": {},
            "pitch_rows": [],
            "markers": {},
        }
    return {
        "index": index or "live",
        "prev": prev.get("index") if prev else None,
        "metadata": parse_title_metadata(text(soup.title)),
        "matchup": parse_matchup_table(tables[4]),
        "pitch_rows": parse_pitch_table(tables[5]),
        "markers": parse_markers(soup),
    }


def fetch_score_page_via_playwright(page, game_id: str, index: str | None) -> dict:
    score_url = f"{BASE_URL}/npb/game/{game_id}/score"
    if index:
        score_url = f"{score_url}?index={index}"
    page.goto(score_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(800)
    try:
        page.wait_for_selector("#pitchesDetail table", timeout=5000)
    except Exception:
        pass
    return parse_score_page_html(page.content(), index)


def collect_pitch_pages_via_jina(game_id: str) -> tuple[list[dict], dict]:
    pages = []
    metadata = {}
    for inning in range(1, MAX_SCORE_INNINGS + 1):
        inning_has_pages = False
        for half in ("1", "2"):
            for batter in range(1, MAX_BATTERS_PER_HALF + 1):
                index = f"{inning:02d}{half}{batter:02d}00"
                page = fetch_score_page_via_jina(game_id, index)
                if not page["pitch_rows"]:
                    break
                pages.append(page)
                metadata = metadata or page["metadata"]
                inning_has_pages = True
        if inning > 9 and not inning_has_pages:
            break
    return pages, metadata


def collect_pitch_pages_from_browser_page(page, game_id: str) -> tuple[list[dict], dict]:
    pages = []
    seen = set()
    index = None
    metadata = {}
    while True:
        item = fetch_score_page_via_playwright(page, game_id, index)
        pages.append(item)
        metadata = metadata or item["metadata"]
        prev = item["prev"]
        if not prev or prev in seen:
            break
        seen.add(prev)
        index = prev
    return pages, metadata


def collect_pitch_pages_via_playwright(game_id: str, browser_page=None) -> tuple[list[dict], dict]:
    if browser_page is not None:
        return collect_pitch_pages_from_browser_page(browser_page, game_id)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        owned_page = browser.new_page()
        try:
            return collect_pitch_pages_from_browser_page(owned_page, game_id)
        finally:
            browser.close()


def collect_pitch_pages(session: requests.Session, game_id: str, browser_page=None) -> tuple[list[dict], dict]:
    try:
        pages = []
        seen = set()
        index = None
        metadata = {}
        while True:
            item = fetch_score_page(session, game_id, index)
            pages.append(item)
            metadata = metadata or item["metadata"]
            prev = item["prev"]
            if not prev or prev in seen:
                break
            seen.add(prev)
            index = prev
        if any(item["pitch_rows"] for item in pages) and not any(item["markers"] for item in pages):
            return collect_pitch_pages_via_playwright(game_id, browser_page=browser_page)
        return pages, metadata
    except requests.RequestException:
        try:
            return collect_pitch_pages_via_playwright(game_id, browser_page=browser_page)
        except Exception:
            return collect_pitch_pages_via_jina(game_id)


def collect_pitcher_rows(pages: list[dict], pitcher_name: str | None, pitcher_id: str | None) -> list[dict]:
    rows = []
    seen_pitch_numbers = set()
    for page in pages:
        matchup = page["matchup"]
        if pitcher_id:
            if matchup.get("pitcher_id") != pitcher_id:
                continue
        elif matchup.get("pitcher") != pitcher_name:
            continue
        markers = page["markers"]
        for pitch in page["pitch_rows"]:
            pitch_no = pitch["pitch_no"]
            if pitch_no in seen_pitch_numbers:
                continue
            seen_pitch_numbers.add(pitch_no)
            marker = markers.get(pitch["seq"], {})
            rows.append(
                {
                    "pa_index": page["index"],
                    "pitcher": matchup.get("pitcher"),
                    "pitcher_id": matchup.get("pitcher_id"),
                    "pitcher_hand": matchup.get("pitcher_hand"),
                    "batter": matchup.get("batter"),
                    "batter_id": matchup.get("batter_id"),
                    "batter_hand": matchup.get("batter_hand"),
                    "seq": pitch["seq"],
                    "pitchNo": pitch_no,
                    "pitchType": pitch["pitch_type"],
                    "speed": pitch["speed"] or None,
                    "result": pitch["result"],
                    "top": marker.get("top"),
                    "left": marker.get("left"),
                }
            )
    return rows


def parse_statline_via_jina(game_id: str, pitcher_name: str | None, pitcher_id: str | None) -> tuple[dict, dict]:
    stats_url = f"{BASE_URL}/npb/game/{game_id}/stats"
    markdown = fetch_markdown_via_jina(stats_url)
    lines = markdown.splitlines()
    title_line = next((line.removeprefix("Title: ").strip() for line in lines if line.startswith("Title: ")), "")
    metadata = parse_title_metadata(title_line)
    in_pitcher_section = False
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            in_pitcher_section = "投手成績" in line
            continue
        if not in_pitcher_section:
            continue
        if "選手名" not in line or "投球回" not in line or "自責点" not in line:
            continue
        for row_line in lines[idx + 2 :]:
            if not row_line.startswith("|"):
                break
            cells = split_markdown_row(row_line)
            if len(cells) < 14:
                continue
            first_link = re.search(r"/npb/player/(\d+)/top", row_line)
            row_player_id = first_link.group(1) if first_link else None
            row_player_name = cells[1]
            if pitcher_id:
                if row_player_id != pitcher_id:
                    continue
            elif row_player_name != pitcher_name:
                continue
            return (
                {
                    "player": row_player_name,
                    "era": cells[2],
                    "innings": cells[3],
                    "pitches": cells[4],
                    "batters": cells[5],
                    "hits": cells[6],
                    "hr": cells[7],
                    "k": cells[8],
                    "bb": cells[9],
                    "hbp": cells[10],
                    "balk": cells[11],
                    "runs": cells[12],
                    "er": cells[13],
                },
                metadata,
            )
    target = pitcher_id or pitcher_name or "(unknown pitcher)"
    raise ValueError(f"Pitcher stat line not found: {target}")


def parse_statline(session: requests.Session, game_id: str, pitcher_name: str | None, pitcher_id: str | None) -> tuple[dict, dict]:
    stats_url = f"{BASE_URL}/npb/game/{game_id}/stats"
    try:
        resp = session.get(stats_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return parse_statline_via_jina(game_id, pitcher_name, pitcher_id)
    soup = BeautifulSoup(resp.text, "html.parser")
    metadata = parse_title_metadata(text(soup.title))
    for table in soup.select("table"):
        headers = [text(th) for th in table.select("thead th")]
        if "投球回" not in headers or "投球数" not in headers or "被本塁打" not in headers:
            continue
        for tr in table.select("tr"):
            first_link = tr.select_one("a[href*='/npb/player/']")
            row_player_id = None
            if first_link and first_link.get("href"):
                m = re.search(r"/npb/player/(\d+)/top", first_link["href"])
                row_player_id = m.group(1) if m else None
            cells = [text(cell) for cell in tr.select("th,td")]
            if not cells:
                continue
            player_idx = len(cells) - 13
            if player_idx < 0:
                continue
            if len(cells) < player_idx + 13:
                continue
            row_player_name = cells[player_idx]
            if pitcher_id:
                if row_player_id != pitcher_id:
                    continue
            elif row_player_name != pitcher_name:
                continue
            return (
                {
                    "player": cells[player_idx],
                    "era": cells[player_idx + 1],
                    "innings": cells[player_idx + 2],
                    "pitches": cells[player_idx + 3],
                    "batters": cells[player_idx + 4],
                    "hits": cells[player_idx + 5],
                    "hr": cells[player_idx + 6],
                    "k": cells[player_idx + 7],
                    "bb": cells[player_idx + 8],
                    "hbp": cells[player_idx + 9],
                    "balk": cells[player_idx + 10],
                    "runs": cells[player_idx + 11],
                    "er": cells[player_idx + 12],
                },
                metadata,
            )
    target = pitcher_id or pitcher_name or "(unknown pitcher)"
    raise ValueError(f"Pitcher stat line not found: {target}")


def zone_index(left: float, top: float) -> tuple[int, int]:
    col = min(int(left / (HEATMAP_WIDTH / HEATMAP_SPLITS)), HEATMAP_SPLITS - 1)
    row = min(int(top / (HEATMAP_HEIGHT / HEATMAP_SPLITS)), HEATMAP_SPLITS - 1)
    return row, col


def parse_inning(index: str | None):
    if not index or not index[:2].isdigit():
        return None
    return int(index[:2])


def parse_speed(value: str | None):
    if not value or "km/h" not in value:
        return None
    return float(value.replace("km/h", ""))


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_hit(result: str):
    if not result:
        return False
    primary = result.split("[", 1)[0].strip()
    if not primary:
        return False
    return any(word in primary for word in HIT_WORDS) or bool(HIT_RESULT_PATTERN.search(primary))


def is_ab_result(result: str):
    return classify_terminal_result(result) in {"1B", "2B", "3B", "HR", "K", "OUT"}


def classify_terminal_result(result: str) -> str:
    """Classify a completed PA, keeping interrupted and unknown results explicit."""
    primary = normalize_result(result)
    if not primary or primary in {"ボール", "ストライク", "見逃し", "空振り", "ファウル", "バントファウル"}:
        return "INCOMPLETE"
    if any(word in primary for word in ("三振", "振逃")):
        return "K"
    if any(word in primary for word in ("盗塁", "盗失", "けん制", "牽制", "走塁死", "途中終了", "途中交代")):
        return "INCOMPLETE"
    for terms, category in [(("故意四", "敬遠"), "IBB"), (("四球",), "BB"), (("死球",), "HBP"),
                            (("犠飛",), "SF"), (("犠打", "犠野", "犠失"), "SH"),
                            (("打撃妨害", "打妨", "捕妨"), "INT")]:
        if any(word in primary for word in terms):
            return category
    hit_type = classify_hit_type(primary)
    if hit_type:
        return {"singles": "1B", "doubles": "2B", "triples": "3B", "home_runs": "HR"}[hit_type]
    if any(word in primary for word in ("ゴロ", "併打", "飛", "直", "ライナー", "失", "野選", "アウト", "守備妨害")):
        return "OUT"
    return "UNKNOWN"


def normalize_result(result: str) -> str:
    if not result:
        return ""
    return result.split("[", 1)[0].strip()


def build_stat_bucket():
    return {
        "count": 0,
        "speeds": [],
        "swing_miss": 0,
        "ab": 0,
        "hits": 0,
        "singles": 0,
        "doubles": 0,
        "triples": 0,
        "home_runs": 0,
        "grounders": 0,
        "flyballs": 0,
        "strikeouts": 0,
    }


def classify_hit_type(result: str):
    primary = normalize_result(result)
    if not primary:
        return None
    if primary.endswith("本"):
        return "home_runs"
    if primary.endswith(("3", "３")):
        return "triples"
    if primary.endswith(("2", "２")):
        return "doubles"
    if any(word in primary for word in HIT_WORDS):
        return "singles"
    return None


def is_swing_miss_result(result: str) -> bool:
    primary = normalize_result(result)
    return any(word in primary for word in SWING_MISS_WORDS)


def classify_plate_appearance_result(result: str):
    primary = normalize_result(result)
    if not primary:
        return None
    if any(word in primary for word in STRIKEOUT_WORDS):
        return "strikeouts"
    if any(word in primary for word in GROUNDER_WORDS):
        return "grounders"
    if any(word in primary for word in FLY_WORDS):
        return "flyballs"
    return None


def record_ab_result(stats: dict, result: str):
    outcome = classify_plate_appearance_result(result)
    if outcome:
        stats[outcome] += 1
    if not is_ab_result(result):
        return
    stats["ab"] += 1
    hit_type = classify_hit_type(result)
    if hit_type:
        stats["hits"] += 1
        stats[hit_type] += 1


def summarize_stat_row(stats: dict):
    avg_speed = f"{np.mean(stats['speeds']):.1f}" if stats["speeds"] else "-"
    whiff = stats["swing_miss"] / stats["count"] * 100 if stats["count"] else None
    hit_rate = stats["hits"] / stats["ab"] if stats["ab"] else None
    return {
        "avg_speed": avg_speed,
        "whiff_count": stats["swing_miss"],
        "whiff": whiff,
        "hit_rate": hit_rate,
        "at_bats": stats["ab"],
        "hits": stats["hits"],
        "singles": stats["singles"],
        "doubles": stats["doubles"],
        "triples": stats["triples"],
        "home_runs": stats["home_runs"],
        "grounders": stats["grounders"],
        "flyballs": stats["flyballs"],
        "strikeouts": stats["strikeouts"],
    }


def format_percent(value):
    return f"{value:.1f}%" if value is not None else "-"


def format_average(value):
    return f"{value:.3f}" if value is not None else "-"


def build_plate_appearances(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["pa_index"]].append(row)
    for pitches in grouped.values():
        pitches.sort(key=lambda row: safe_int(row["seq"], 0))
    return grouped


def classify_count_bucket(seq: int, balls: int, strikes: int):
    if seq <= 1 or (balls == 0 and strikes == 0):
        return "初球"
    if balls == 3 and strikes == 2:
        return "フルカウント"
    if strikes == 2:
        return "2ストライク以降"
    return "追い込み前"


def advance_count(balls: int, strikes: int, result: str):
    if any(word in result for word in ("ボール", "四球", "死球")):
        return min(3, balls + 1), strikes
    if "ファウル" in result:
        return balls, strikes if strikes >= 2 else strikes + 1
    if any(word in result for word in ("見逃し", "空振り", "見三振", "空三振", "ストライク")):
        return balls, min(2, strikes + 1)
    return balls, strikes


def build_count_mix_summary(plate_appearances):
    bucket_counts = {bucket: Counter() for bucket in COUNT_BUCKETS}
    bucket_totals = Counter()
    for pitches in plate_appearances.values():
        balls = 0
        strikes = 0
        expected_seq = 1
        count_known = True
        for idx, row in enumerate(pitches):
            seq = safe_int(row.get("seq"), 0)
            count_known = count_known and seq == expected_seq
            expected_seq = seq + 1
            bucket = classify_count_bucket(seq, balls, strikes) if count_known else "不明"
            bucket_counts[bucket][row["pitchType"]] += 1
            bucket_totals[bucket] += 1
            if idx == len(pitches) - 1:
                continue
            balls, strikes = advance_count(balls, strikes, row["result"])
    return bucket_counts, bucket_totals


def build_finish_pitch_summary(plate_appearances):
    finish_stats = defaultdict(lambda: {"count": 0, "looking": 0, "swinging": 0, "speeds": []})
    total = 0
    for pitches in plate_appearances.values():
        final = pitches[-1]
        primary = normalize_result(final["result"])
        if classify_plate_appearance_result(primary) != "strikeouts":
            continue
        stats = finish_stats[final["pitchType"]]
        stats["count"] += 1
        total += 1
        speed = parse_speed(final["speed"])
        if speed is not None:
            stats["speeds"].append(speed)
        if "見" in primary:
            stats["looking"] += 1
        else:
            stats["swinging"] += 1
    return total, finish_stats


def build_velocity_trend(rows):
    ordered = sorted(rows, key=lambda row: safe_int(row["pitchNo"], 0))
    inning_starts = {}
    speed_rows = []
    for row in ordered:
        pitch_no = safe_int(row["pitchNo"], 0)
        inning = parse_inning(row["pa_index"])
        if inning is not None and inning not in inning_starts:
            inning_starts[inning] = pitch_no
        speed = parse_speed(row["speed"])
        if speed is None:
            continue
        if row["pitchType"] not in STRAIGHT_PITCH_TYPES:
            continue
        speed_rows.append(
            {
                "pitch_no": pitch_no,
                "pitch_type": row["pitchType"],
                "speed": speed,
                "inning": inning,
            }
        )
    markers = [(inning, pitch_no) for inning, pitch_no in sorted(inning_starts.items())]
    return speed_rows, markers


def build_inning_summary(straight_by_inning: dict):
    rows = []
    for inning in DISPLAY_INNINGS:
        stats = straight_by_inning.get(
            inning,
            build_stat_bucket(),
        )
        summary = summarize_stat_row(stats)
        rows.append(
            {
                "inning": inning,
                "count": stats["count"],
                "at_bats": summary["at_bats"],
                "avg_speed": summary["avg_speed"],
                "whiff": summary["whiff"],
                "hit_rate": summary["hit_rate"],
            }
        )
    return rows


def summarize(rows):
    total = len(rows)
    pitch_counts = Counter(row["pitchType"] for row in rows)
    pitch_stats = defaultdict(build_stat_bucket)
    plate_appearances = build_plate_appearances(rows)
    heat_by_hand = {
        "右": np.zeros((HEATMAP_SPLITS, HEATMAP_SPLITS), dtype=int),
        "左": np.zeros((HEATMAP_SPLITS, HEATMAP_SPLITS), dtype=int),
    }
    straight_by_inning = defaultdict(build_stat_bucket)

    for row in rows:
        inning = parse_inning(row["pa_index"])
        stats = pitch_stats[row["pitchType"]]
        stats["count"] += 1
        speed = parse_speed(row["speed"])
        if speed is not None:
            stats["speeds"].append(speed)
        if is_swing_miss_result(row["result"]):
            stats["swing_miss"] += 1
        if row["pitchType"] in STRAIGHT_PITCH_TYPES and inning is not None:
            inning_stats = straight_by_inning[inning]
            inning_stats["count"] += 1
            if speed is not None:
                inning_stats["speeds"].append(speed)
            if is_swing_miss_result(row["result"]):
                inning_stats["swing_miss"] += 1
        if row["left"] is not None and row["top"] is not None and row["batter_hand"] in heat_by_hand:
            r, c = zone_index(float(row["left"]), float(row["top"]))
            heat_by_hand[row["batter_hand"]][r, c] += 1

    for pitches in plate_appearances.values():
        final = pitches[-1]
        record_ab_result(pitch_stats[final["pitchType"]], final["result"])
        inning = parse_inning(final["pa_index"])
        if final["pitchType"] in STRAIGHT_PITCH_TYPES and inning is not None:
            record_ab_result(straight_by_inning[inning], final["result"])

    return (
        total,
        pitch_counts,
        pitch_stats,
        heat_by_hand,
        build_inning_summary(straight_by_inning),
        build_count_mix_summary(plate_appearances),
        build_finish_pitch_summary(plate_appearances),
        build_velocity_trend(rows),
    )


def draw_round_box(ax, xy, wh, fc=CARD, ec=GRID, radius=18, lw=1.2):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=lw,
        edgecolor=ec,
        facecolor=fc,
        transform=ax.transAxes,
        clip_on=True,
    )
    ax.add_patch(patch)
    return patch


def draw_header(ax, statline, metadata):
    ax.axis("off")
    draw_round_box(ax, (0.0, 0.0), (1.0, 1.0), fc=NAVY, ec=NAVY, radius=28, lw=0)
    ax.text(0.04, 0.54, statline["player"], color="white", fontsize=31, fontweight="bold", transform=ax.transAxes)
    subtitle = f"{metadata.get('date_jp', '')} {metadata.get('matchup', '').replace('vs', ' vs ')}".strip()
    ax.text(0.04, 0.16, subtitle, color="#D7DCE5", fontsize=12, transform=ax.transAxes)
    ax.text(0.96, 0.55, "Pitch Dashboard", ha="right", color="white", fontsize=22, fontweight="bold", transform=ax.transAxes)
    ax.text(0.96, 0.2, "参照先：スポーツナビ", ha="right", color="#C7D0DB", fontsize=11, transform=ax.transAxes)


def draw_stat_cards(ax, statline):
    ax.axis("off")
    labels = [
        ("投球回", statline["innings"]),
        ("球数", statline["pitches"]),
        ("対戦打者", statline["batters"]),
        ("被安打", statline["hits"]),
        ("奪三振", statline["k"]),
        ("与四球", statline["bb"]),
        ("自責点", statline["er"]),
        ("失点", statline["runs"]),
    ]
    pad = 0.014
    box_w = (1 - pad * (len(labels) + 1)) / len(labels)
    for i, (label, value) in enumerate(labels):
        x = pad + i * (box_w + pad)
        draw_round_box(ax, (x, 0.08), (box_w, 0.84), fc=CARD, ec=GRID, radius=18)
        ax.text(x + box_w / 2, 0.64, label, ha="center", va="center", fontsize=11, color=MUTED, transform=ax.transAxes)
        ax.text(x + box_w / 2, 0.34, value, ha="center", va="center", fontsize=22, color=TEXT, fontweight="bold", transform=ax.transAxes)


def draw_ratio_chart(ax, pitch_counts, total):
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.set_facecolor("none")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.text(0.04, 0.9, "球種比率", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)
    inner = ax.inset_axes([0.08, 0.18, 0.84, 0.68])
    ordered = pitch_counts.most_common()
    labels = [k for k, _ in ordered]
    counts = [v for _, v in ordered]
    ratios = [v / total * 100 for v in counts]
    colors = [NAVY, "#355C8C", "#6A89B4", GOLD, "#D6C192"]
    x = np.arange(len(labels))
    bars = inner.bar(x, ratios, color=colors[: len(labels)], width=0.62)
    inner.set_ylabel("割合 (%)", fontsize=12)
    inner.set_ylim(0, max(ratios) * 1.28)
    inner.set_xticks(x, labels)
    inner.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.8)
    inner.set_axisbelow(True)
    inner.tick_params(axis="x", rotation=25, labelsize=11)
    inner.tick_params(axis="y", labelsize=11)
    for bar, ratio, count in zip(bars, ratios, counts):
        inner.text(bar.get_x() + bar.get_width() / 2, ratio + 0.8, f"{ratio:.1f}%\n{count}球", ha="center", va="bottom", fontsize=11, color=TEXT)


def draw_pitch_table(ax, pitch_counts, pitch_stats, total):
    ax.axis("off")
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.text(0.04, 0.9, "球種別サマリー", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)

    headers = ["球種", "平均球速", "球数", "空振数", "空振率", "被打数", "単打", "二塁打", "三塁打", "本塁打", "ゴロ", "フライ", "三振", "被打率"]
    header_x = [0.08, 0.18, 0.27, 0.37, 0.46, 0.54, 0.61, 0.67, 0.73, 0.79, 0.85, 0.90, 0.94, 0.98]
    col_x = [0.05, 0.18, 0.27, 0.37, 0.46, 0.54, 0.61, 0.67, 0.73, 0.79, 0.85, 0.90, 0.94, 0.98]
    for x, header in zip(header_x, headers):
        ax.text(x, 0.78, header, ha="center", va="center", fontsize=8.5, color=MUTED, transform=ax.transAxes)
    table_top = 0.73
    table_bottom = 0.14
    ax.plot([0.04, 0.96], [table_top, table_top], color=GRID, lw=1, transform=ax.transAxes)

    ordered = pitch_counts.most_common()
    row_height = (table_top - table_bottom) / max(len(ordered), 1)
    row_centers = [table_top - row_height * (idx + 0.5) for idx in range(len(ordered))]
    row_lines = [table_top - row_height * (idx + 1) for idx in range(len(ordered))]
    for y, line_y, (pitch_type, count) in zip(row_centers, row_lines, ordered):
        stats = pitch_stats[pitch_type]
        summary = summarize_stat_row(stats)
        values = [
            pitch_type,
            summary["avg_speed"],
            str(count),
            str(summary["whiff_count"]),
            format_percent(summary["whiff"]),
            str(summary["at_bats"]),
            str(summary["singles"]),
            str(summary["doubles"]),
            str(summary["triples"]),
            str(summary["home_runs"]),
            str(summary["grounders"]),
            str(summary["flyballs"]),
            str(summary["strikeouts"]),
            format_average(summary["hit_rate"]),
        ]
        aligns = ["left", "center", "center", "center", "center", "center", "center", "center", "center", "center", "center", "center", "center", "center"]
        for x, value, align in zip(col_x, values, aligns):
            ax.text(x if align != "left" else 0.05, y, value, ha=align, va="center", fontsize=8.7, color=TEXT, transform=ax.transAxes)
        ax.plot([0.05, 0.95], [line_y, line_y], color="#ECE5D8", lw=0.8, transform=ax.transAxes)


def draw_straight_inning_table(ax, inning_rows):
    ax.axis("off")
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.text(0.04, 0.9, "イニング別平均球速（ストレート）", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)

    headers = ["回", "平均球速", "球数", "空振率", "被打数", "被打率"]
    col_x = [0.08, 0.27, 0.43, 0.6, 0.77, 0.9]
    for x, header in zip(col_x, headers):
        ax.text(x, 0.78, header, ha="center", va="center", fontsize=12, color=MUTED, transform=ax.transAxes)
    table_top = 0.73
    table_bottom = 0.12
    ax.plot([0.04, 0.96], [table_top, table_top], color=GRID, lw=1, transform=ax.transAxes)

    row_height = (table_top - table_bottom) / max(len(inning_rows), 1)
    row_centers = [table_top - row_height * (idx + 0.5) for idx in range(len(inning_rows))]
    row_lines = [table_top - row_height * (idx + 1) for idx in range(len(inning_rows))]
    for y, line_y, row in zip(row_centers, row_lines, inning_rows):
        values = [
            f"{row['inning']}回",
            f"{row['avg_speed']} km/h" if row["avg_speed"] != "-" else "-",
            str(row["count"]),
            f"{row['whiff']:.1f}%" if row["whiff"] is not None else "-",
            str(row["at_bats"]),
            format_average(row["hit_rate"]),
        ]
        for x, value in zip(col_x, values):
            ax.text(x, y, value, ha="center", va="center", fontsize=13, color=TEXT, transform=ax.transAxes)
        ax.plot([0.05, 0.95], [line_y, line_y], color="#ECE5D8", lw=0.8, transform=ax.transAxes)


def get_pitcher_view_labels(hand):
    if hand == "右":
        return "外角", "内角"
    return "内角", "外角"


def build_pitch_color_map(pitch_types):
    return {pitch_type: PITCH_COLORS[idx % len(PITCH_COLORS)] for idx, pitch_type in enumerate(pitch_types)}


def draw_count_mix_chart(ax, pitch_types, bucket_counts, bucket_totals):
    ax.axis("off")
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.text(0.04, 0.91, "カウント別球種割合", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)

    inner_bottom = 0.17 + axes_y_from_pixels(ax, 100)
    inner_height = 0.56
    inner_top = inner_bottom + inner_height
    inner = ax.inset_axes([0.18, inner_bottom, 0.66, inner_height])
    color_map = build_pitch_color_map(pitch_types)
    y = np.arange(len(COUNT_BUCKETS))
    left = np.zeros(len(COUNT_BUCKETS))
    handles = []
    for pitch_type in pitch_types:
        values = []
        for bucket in COUNT_BUCKETS:
            total = bucket_totals[bucket]
            count = bucket_counts[bucket][pitch_type]
            values.append(0 if total == 0 else count / total * 100)
        bars = inner.barh(y, values, left=left, color=color_map[pitch_type], height=0.56, label=pitch_type)
        handles.append(bars[0])
        for idx, value in enumerate(values):
            if value >= 12:
                inner.text(left[idx] + value / 2, y[idx], f"{value:.0f}%", ha="center", va="center", fontsize=9, color="white")
        left += np.array(values)
    inner.set_xlim(0, 112)
    inner.set_yticks(y, COUNT_BUCKETS)
    inner.invert_yaxis()
    inner.set_xlabel("割合 (%)", fontsize=11)
    inner.set_xticks(np.arange(0, 101, 20))
    inner.tick_params(axis="x", labelsize=10)
    inner.tick_params(axis="y", labelsize=11)
    inner.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.8)
    inner.set_axisbelow(True)
    for idx, bucket in enumerate(COUNT_BUCKETS):
        inner.text(103.0, y[idx], f"{bucket_totals[bucket]}球", ha="left", va="center", fontsize=10, color=MUTED)
    legend_y = (0.91 + inner_top) / 2
    ax.legend(
        handles,
        pitch_types,
        loc="center",
        bbox_to_anchor=(0.5, legend_y),
        bbox_transform=ax.transAxes,
        ncol=min(3, len(pitch_types)),
        frameon=False,
        fontsize=10,
        columnspacing=1.2,
        handletextpad=0.5,
    )
    ax.text(0.04, 0.05, "各投球を初球、追い込み前、2ストライク以降、フルカウントで分類", fontsize=10, color=MUTED, transform=ax.transAxes)


def draw_finish_pitch_table(ax, finish_total, finish_stats):
    ax.axis("off")
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.text(0.04, 0.88, "決め球サマリ（三振）", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)
    if not finish_total:
        ax.text(0.5, 0.48, "この試合では三振がありません", ha="center", va="center", fontsize=14, color=MUTED, transform=ax.transAxes)
        return

    headers = ["球種", "球数", "割合", "見逃し", "空振"]
    col_x = [0.12, 0.44, 0.6, 0.76, 0.9]
    for x, header in zip(col_x, headers):
        ax.text(x, 0.72, header, ha="center", va="center", fontsize=12, color=MUTED, transform=ax.transAxes)
    ax.plot([0.04, 0.96], [0.66, 0.66], color=GRID, lw=1, transform=ax.transAxes)

    ordered = sorted(finish_stats.items(), key=lambda item: item[1]["count"], reverse=True)
    row_y = np.linspace(0.54, 0.2, len(ordered))
    for y, (pitch_type, stats) in zip(row_y, ordered):
        values = [
            pitch_type,
            str(stats["count"]),
            f"{stats['count'] / finish_total * 100:.1f}%",
            str(stats["looking"]),
            str(stats["swinging"]),
        ]
        aligns = ["center", "center", "center", "center", "center"]
        for x, value, align in zip(col_x, values, aligns):
            ax.text(x, y, value, ha=align, va="center", fontsize=13, color=TEXT, transform=ax.transAxes)
        ax.plot([0.05, 0.95], [y - 0.055, y - 0.055], color="#ECE5D8", lw=0.8, transform=ax.transAxes)


def draw_velocity_trend(ax, pitch_types, speed_rows, inning_markers):
    ax.axis("off")
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    title = ax.text(0.04, 0.92, "球速推移", fontsize=18, fontweight="bold", color=TEXT, transform=ax.transAxes)
    if not speed_rows:
        ax.text(0.5, 0.48, "球速データがありません", ha="center", va="center", fontsize=14, color=MUTED, transform=ax.transAxes)
        return

    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    title_bbox = title.get_window_extent(renderer=renderer)
    label_x = ax.transAxes.inverted().transform((title_bbox.x1 + 10, title_bbox.y0))[0]
    ax.text(label_x, 0.92, "● ストレート", fontsize=11, color=NAVY, va="center", transform=ax.transAxes)

    inner = ax.inset_axes([0.08, 0.16, 0.84, 0.68])
    pitch_nos = np.array([row["pitch_no"] for row in speed_rows])
    speeds = np.array([row["speed"] for row in speed_rows])
    inner.plot(pitch_nos, speeds, color="#B9C4D3", linewidth=1.4, alpha=0.95, zorder=1)
    inner.scatter(pitch_nos, speeds, s=30, color=NAVY, zorder=2)

    y_top = speeds.max() + 3
    for inning, pitch_no in inning_markers[1:]:
        inner.axvline(pitch_no - 0.5, color=GRID, linewidth=1.0, linestyle=":")
        inner.text(pitch_no, y_top - 0.3, f"{inning}回", ha="center", va="top", fontsize=9, color=MUTED)

    inner.set_xlim(max(1, pitch_nos.min() - 1), pitch_nos.max() + 1)
    inner.set_ylim(speeds.min() - 3, y_top)
    inner.set_xlabel("投球数", fontsize=11)
    inner.set_ylabel("km/h", fontsize=11)
    inner.tick_params(axis="both", labelsize=10)
    inner.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.8)
    inner.set_axisbelow(True)
    ax.text(0.04, 0.05, "ストレートのみを投球数順に表示", fontsize=10, color=MUTED, transform=ax.transAxes)


def draw_heatmap(ax, heat, title, hand):
    draw_round_box(ax, (0, 0), (1, 1), fc=CARD, ec=GRID, radius=20)
    ax.set_facecolor("none")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    display_heat = heat
    heatmap_box = [0.12, 0.24, 0.76, 0.56]
    inner = ax.inset_axes(heatmap_box)
    cmap = mpl.colors.LinearSegmentedColormap.from_list("orix_heat", HEAT_COLORS)
    vmax = max(1, int(display_heat.max()))
    inner.imshow(display_heat, cmap=cmap, vmin=0, vmax=vmax)
    inner.set_title(title, loc="center", fontsize=16, color=TEXT, fontweight="bold", pad=18 + pixels_to_points(80))
    inner.set_xticks([])
    inner.set_yticks([])
    inner.set_xticks(np.arange(-0.5, HEATMAP_SPLITS, 1), minor=True)
    inner.set_yticks(np.arange(-0.5, HEATMAP_SPLITS, 1), minor=True)
    inner.grid(which="minor", color="white", linewidth=2)
    inner.tick_params(which="minor", bottom=False, left=False)
    outer_zone = Rectangle((-0.5, -0.5), HEATMAP_SPLITS, HEATMAP_SPLITS, fill=False, edgecolor="#3D3D3D", linewidth=1.8)
    strike_zone = Rectangle((0.5, 0.5), 3, 3, fill=False, edgecolor="#1F1F1F", linewidth=2.6)
    inner.add_patch(outer_zone)
    inner.add_patch(strike_zone)
    inner.set_xlim(-0.5, HEATMAP_SPLITS - 0.5)
    inner.set_ylim(HEATMAP_SPLITS - 0.5, -0.5)
    for r in range(HEATMAP_SPLITS):
        for c in range(HEATMAP_SPLITS):
            value = int(display_heat[r, c])
            color = "white" if value >= vmax * 0.55 else TEXT
            inner.text(c, r, str(value), ha="center", va="center", fontsize=15, fontweight="bold", color=color)
    left_label, right_label = get_pitcher_view_labels(hand)
    label_y = heatmap_box[1] - axes_y_from_pixels(ax, 4)
    ax.text(0.24, label_y, left_label, ha="center", va="center", fontsize=12, color=MUTED, transform=ax.transAxes)
    ax.text(0.76, label_y, right_label, ha="center", va="center", fontsize=12, color=MUTED, transform=ax.transAxes)
    ax.text(0.5, 0.08, "中央3×3がストライクゾーン", ha="center", va="center", fontsize=11, color=MUTED, transform=ax.transAxes)


def render_page_one(statline: dict, metadata: dict, pitch_counts, pitch_stats, total: int, output_png: Path):
    fig = plt.figure(figsize=PAGE_FIGSIZE, facecolor=BG)
    gs = GridSpec(18, 2, figure=fig, hspace=0.42, wspace=0.28)
    fig.subplots_adjust(left=0.055, right=0.945, top=0.98, bottom=0.04)

    ax_header = fig.add_subplot(gs[0:2, :])
    ax_cards = fig.add_subplot(gs[2:4, :])
    ax_ratio = fig.add_subplot(gs[4:11, :])
    ax_table = fig.add_subplot(gs[11:18, :])

    draw_header(ax_header, statline, metadata)
    draw_stat_cards(ax_cards, statline)
    draw_ratio_chart(ax_ratio, pitch_counts, total)
    draw_pitch_table(ax_table, pitch_counts, pitch_stats, total)

    fig.savefig(output_png, dpi=180, facecolor=BG)
    plt.close(fig)


def render_page_two(statline: dict, metadata: dict, inning_rows: list[dict], heat_by_hand: dict, output_png: Path):
    fig = plt.figure(figsize=PAGE_FIGSIZE, facecolor=BG)
    left = 0.055
    right = 0.945
    width = right - left
    fig_height_px = fig.get_figheight() * OUTPUT_DPI
    available_height_px = fig_height_px * (0.98 - 0.04)
    base_row_px = available_height_px / (18 + 17 * 0.42)
    section_gap_px = base_row_px * 0.42
    top_block_height_px = base_row_px * (2 + 0.42)
    inning_height_px = base_row_px * (4 + 3 * 0.42) + 200
    heat_height_px = base_row_px * (10 + 9 * 0.42) - 200
    bottom_margin_px = fig_height_px * 0.04

    def fig_y(px: float) -> float:
        return px / fig_height_px

    heat_width = width / 2.28
    heat_gap = heat_width * 0.28
    heat_bottom = fig_y(bottom_margin_px)
    inning_bottom = fig_y(bottom_margin_px + heat_height_px + section_gap_px)
    cards_bottom = fig_y(bottom_margin_px + heat_height_px + section_gap_px + inning_height_px + section_gap_px)
    header_bottom = fig_y(
        bottom_margin_px + heat_height_px + section_gap_px + inning_height_px + section_gap_px + top_block_height_px + section_gap_px
    )

    ax_header = fig.add_axes([left, header_bottom, width, fig_y(top_block_height_px)])
    ax_cards = fig.add_axes([left, cards_bottom, width, fig_y(top_block_height_px)])
    ax_inning = fig.add_axes([left, inning_bottom, width, fig_y(inning_height_px)])
    ax_heat_r = fig.add_axes([left, heat_bottom, heat_width, fig_y(heat_height_px)])
    ax_heat_l = fig.add_axes([left + heat_width + heat_gap, heat_bottom, heat_width, fig_y(heat_height_px)])

    draw_header(ax_header, statline, metadata)
    draw_stat_cards(ax_cards, statline)
    draw_straight_inning_table(ax_inning, inning_rows)
    draw_heatmap(ax_heat_r, heat_by_hand["右"], "投球コースヒートマップ\nvs 右打者", "右")
    draw_heatmap(ax_heat_l, heat_by_hand["左"], "投球コースヒートマップ\nvs 左打者", "左")

    fig.savefig(output_png, dpi=180, facecolor=BG)
    plt.close(fig)


def render_page_three(
    statline: dict,
    metadata: dict,
    pitch_counts,
    finish_summary,
    velocity_trend,
    output_png: Path,
):
    fig = plt.figure(figsize=PAGE_FIGSIZE, facecolor=BG)
    gs = GridSpec(18, 2, figure=fig, hspace=0.46, wspace=0.28)
    fig.subplots_adjust(left=0.055, right=0.945, top=0.98, bottom=0.04)

    ax_header = fig.add_subplot(gs[0:2, :])
    ax_cards = fig.add_subplot(gs[2:4, :])
    ax_finish = fig.add_subplot(gs[4:9, :])
    ax_speed = fig.add_subplot(gs[9:18, :])

    pitch_types = [pitch_type for pitch_type, _ in pitch_counts.most_common()]
    finish_total, finish_stats = finish_summary
    speed_rows, inning_markers = velocity_trend

    draw_header(ax_header, statline, metadata)
    draw_stat_cards(ax_cards, statline)
    draw_finish_pitch_table(ax_finish, finish_total, finish_stats)
    draw_velocity_trend(ax_speed, pitch_types, speed_rows, inning_markers)

    fig.savefig(output_png, dpi=OUTPUT_DPI, facecolor=BG)
    plt.close(fig)


def render_page_four(
    statline: dict,
    metadata: dict,
    pitch_counts,
    count_mix_summary,
    output_png: Path,
):
    fig = plt.figure(figsize=PAGE_FIGSIZE, facecolor=BG)
    gs = GridSpec(18, 2, figure=fig, hspace=0.46, wspace=0.28)
    fig.subplots_adjust(left=0.055, right=0.945, top=0.98, bottom=0.04)

    ax_header = fig.add_subplot(gs[0:2, :])
    ax_cards = fig.add_subplot(gs[2:4, :])
    ax_count = fig.add_subplot(gs[4:18, :])

    pitch_types = [pitch_type for pitch_type, _ in pitch_counts.most_common()]
    bucket_counts, bucket_totals = count_mix_summary

    draw_header(ax_header, statline, metadata)
    draw_stat_cards(ax_cards, statline)
    draw_count_mix_chart(ax_count, pitch_types, bucket_counts, bucket_totals)

    fig.savefig(output_png, dpi=OUTPUT_DPI, facecolor=BG)
    plt.close(fig)


def write_summary(
    metadata: dict,
    statline: dict,
    pitch_counts,
    pitch_stats,
    total: int,
    inning_rows: list[dict],
    count_mix_summary,
    finish_summary,
    velocity_trend,
    output_summary: Path,
):
    lines = [
        f"{metadata.get('date_jp', '')} {metadata.get('matchup', '')} {statline['player']}",
        f"投球回\t{statline['innings']}",
        f"球数\t{statline['pitches']}",
        f"対戦打者数\t{statline['batters']}",
        f"被安打\t{statline['hits']}",
        f"奪三振\t{statline['k']}",
        f"与四球\t{statline['bb']}",
        f"自責点\t{statline['er']}",
        f"失点\t{statline['runs']}",
        "",
        "[球種比率]",
    ]
    for pitch_type, count in pitch_counts.most_common():
        stats = pitch_stats[pitch_type]
        summary = summarize_stat_row(stats)
        lines.append(
            f"{pitch_type}\t平均{summary['avg_speed']}\t{count}球\t空振数{summary['whiff_count']}\t"
            f"空振率{format_percent(summary['whiff'])}\t被打数{summary['at_bats']}\t"
            f"単打{summary['singles']}\t二塁打{summary['doubles']}\t三塁打{summary['triples']}\t本塁打{summary['home_runs']}\t"
            f"ゴロ{summary['grounders']}\tフライ{summary['flyballs']}\t三振{summary['strikeouts']}\t被打率{format_average(summary['hit_rate'])}"
        )
    lines.extend(["", "[イニング別平均球速（ストレート）]"])
    for row in inning_rows:
        avg_speed = f"{row['avg_speed']} km/h" if row["avg_speed"] != "-" else "-"
        whiff = format_percent(row["whiff"])
        hit_rate = format_average(row["hit_rate"])
        lines.append(f"{row['inning']}回\t{avg_speed}\t{row['count']}球\t空振率{whiff}\t被打数{row['at_bats']}\t被打率{hit_rate}")

    bucket_counts, bucket_totals = count_mix_summary
    lines.extend(["", "[カウント別球種割合]"])
    for bucket in COUNT_BUCKETS:
        total_bucket = bucket_totals[bucket]
        if not total_bucket:
            lines.append(f"{bucket}\t0球")
            continue
        parts = [f"{pitch_type} {count / total_bucket * 100:.1f}%" for pitch_type, count in bucket_counts[bucket].most_common()]
        lines.append(f"{bucket}\t{total_bucket}球\t" + " / ".join(parts))

    finish_total, finish_stats = finish_summary
    lines.extend(["", "[決め球サマリ（三振）]"])
    if not finish_total:
        lines.append("三振なし")
    else:
        for pitch_type, stats in sorted(finish_stats.items(), key=lambda item: item[1]["count"], reverse=True):
            lines.append(
                f"{pitch_type}\t{stats['count']}件\t{stats['count'] / finish_total * 100:.1f}%\t"
                f"見逃し{stats['looking']}\t空振{stats['swinging']}"
            )

    speed_rows, _ = velocity_trend
    lines.extend(["", "[球速推移（ストレート）]"])
    if speed_rows:
        speeds = [row["speed"] for row in speed_rows]
        lines.append(f"平均{np.mean(speeds):.1f} km/h\t最高{np.max(speeds):.1f} km/h\t最低{np.min(speeds):.1f} km/h")
    else:
        lines.append("球速データなし")
    output_summary.write_text("\n".join(lines), encoding="utf-8")


def write_dashboard_summary(payload: dict, output_summary: Path):
    rows = payload["pitches"]
    statline = payload["statline"]
    metadata = payload["metadata"]
    total, pitch_counts, pitch_stats, heat_by_hand, inning_rows, count_mix_summary, finish_summary, velocity_trend = summarize(rows)
    write_summary(
        metadata,
        statline,
        pitch_counts,
        pitch_stats,
        total,
        inning_rows,
        count_mix_summary,
        finish_summary,
        velocity_trend,
        output_summary,
    )


def render_dashboard(payload: dict, output_png_1: Path, output_png_2: Path, output_png_3: Path, output_png_4: Path, output_summary: Path):
    setup_style()
    rows = payload["pitches"]
    statline = payload["statline"]
    metadata = payload["metadata"]
    total, pitch_counts, pitch_stats, heat_by_hand, inning_rows, count_mix_summary, finish_summary, velocity_trend = summarize(rows)

    render_page_one(statline, metadata, pitch_counts, pitch_stats, total, output_png_1)
    render_page_two(statline, metadata, inning_rows, heat_by_hand, output_png_2)
    render_page_three(statline, metadata, pitch_counts, finish_summary, velocity_trend, output_png_3)
    render_page_four(statline, metadata, pitch_counts, count_mix_summary, output_png_4)
    write_dashboard_summary(payload, output_summary)


def main():
    parser = argparse.ArgumentParser(description="Build a Sports Navi pitcher dashboard image set and refresh summary site data.")
    parser.add_argument("--game-id", required=True, help="Sports Navi NPB game id, e.g. 2021038691")
    parser.add_argument("--pitcher", help="Pitcher name as shown on Sports Navi, e.g. 宮城 大弥")
    parser.add_argument("--pitcher-id", help="Sports Navi player id from /npb/player/<id>/top, e.g. 1900087")
    parser.add_argument("--output-dir", default="generated", help="Base directory for dashboard outputs")
    parser.add_argument("--output-prefix", help="Optional output file prefix")
    parser.add_argument("--skip-png", action="store_true", help="Write dashboard JSON and summary only, without PNG pages")
    parser.add_argument("--manifest-script", help="Optional path to summary/build_manifest.py for refreshing summary site data")
    parser.add_argument("--skip-manifest", action="store_true", help="Do not refresh summary site data after writing outputs")
    args = parser.parse_args()
    if not args.pitcher and not args.pitcher_id:
        raise ValueError("Specify either --pitcher or --pitcher-id")

    prefix_base = args.output_prefix or sanitize_filename(f"{args.game_id}-{args.pitcher or args.pitcher_id}")

    session = make_session()
    pages, score_meta = collect_pitch_pages(session, args.game_id)
    pitches = collect_pitcher_rows(pages, args.pitcher, args.pitcher_id)
    if not pitches:
        target = args.pitcher_id or args.pitcher
        raise ValueError(f"No pitches found for {target} in game {args.game_id}")
    resolved_name = pitches[0]["pitcher"]
    statline, stats_meta = parse_statline(session, args.game_id, args.pitcher or resolved_name, args.pitcher_id)
    payload = {
        "game_id": args.game_id,
        "metadata": stats_meta or score_meta,
        "statline": statline,
        "pitches": pitches,
    }

    base_output_dir = Path(args.output_dir).resolve()
    output_dir = base_output_dir / normalize_date_folder(payload["metadata"].get("date_jp", ""))
    output_dir.mkdir(parents=True, exist_ok=True)

    payload_path = output_dir / f"{prefix_base}-dashboard.json"
    summary_path = output_dir / f"{prefix_base}-summary.txt"
    png_path_1 = output_dir / f"{prefix_base}-dashboard-1.png"
    png_path_2 = output_dir / f"{prefix_base}-dashboard-2.png"
    png_path_3 = output_dir / f"{prefix_base}-dashboard-3.png"
    png_path_4 = output_dir / f"{prefix_base}-dashboard-4.png"

    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.skip_png:
        write_dashboard_summary(payload, summary_path)
    else:
        render_dashboard(payload, png_path_1, png_path_2, png_path_3, png_path_4, summary_path)

    manifest_path = None
    if not args.skip_manifest:
        manifest_script = resolve_manifest_script(base_output_dir, args.manifest_script)
        if manifest_script:
            manifest_path = refresh_manifest(manifest_script)

    print(f"payload: {payload_path}")
    print(f"summary: {summary_path}")
    if manifest_path:
        print(f"manifest: {manifest_path}")
    if not args.skip_png:
        print(f"image1: {png_path_1}")
        print(f"image2: {png_path_2}")
        print(f"image3: {png_path_3}")
        print(f"image4: {png_path_4}")


if __name__ == "__main__":
    main()

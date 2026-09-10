"""
Build the full category-only candidate corpus for one comparison group
("quantum" or "cs") by pulling every paper in that group's home arXiv
categories since 2021, with NO keyword filter of any kind.

Why this exists: the per-pillar keyword-based procedure
(build_pillar_paper_list.py) has a hard structural ceiling no amount of
pagination or keyword-list expansion can remove -- a paper that never uses
one of the listed phrases in its title/abstract is invisible to it. This
script removes that ceiling entirely by pulling every paper in scope,
full stop, and leaves the question of which of the six pillars a paper
actually belongs to (or whether it's in scope at all) to the separate
domain-classification step (see DATA_AVAILABILITY_FRAMEWORK.md /
Section 2.6 of data_availability_report.tex), applied after the pull.

Categories are deliberately each side's "home" categories -- where that
side's research actually concentrates -- not the full union of every
category any individual pillar's keyword search happened to cross-list.
Quantum does NOT include cs.LG, for example: including it would import the
entire classical-ML literature into the quantum-side corpus just because
one quantum-algorithms keyword search touched cs.LG as a cross-listing.
    quantum: quant-ph, cond-mat.supr-con, cond-mat.mes-hall
    cs:      cs.DS, cs.CC, cs.LG, cs.NA, cs.IT, cs.CR, cs.AR, cs.PL,
             cs.DC, cs.ET, eess.SY, eess.SP, physics.app-ph

Scale (measured 2026-08-30 via arXiv's own totalResults, no keyword filter):
~109,321 quantum papers, ~344,858 CS papers.

DEEP-PAGINATION LIMIT (discovered 2026-08-30): arXiv's search API returns a
hard HTTP 500 for any request with start >= ~10,000, confirmed directly
(start=9,950 succeeds, start=10,000/10,050/20,000/30,000 all fail
identically, no amount of retrying helps -- this is a structural ceiling in
their search backend, not a transient error). A single query spanning the
whole 2021-present date range can therefore never retrieve more than the
newest ~10,000 papers for either group, silently truncating exactly the
older end of the corpus.

Fix: recursively slice the date range. For any given (start_date, end_date)
window, first probe its total result count (a cheap max_results=1 query);
if that total is safely under the ceiling, paginate the window normally
(start=0 up to its own total, always < 10,000); if not, split the window
in half by date and recurse on each half. This adapts to uneven submission
volume across time (e.g. 2025-2026 months have far more papers than 2021
months) instead of guessing a fixed slice size that might still overflow
for a heavy period.

Run quantum and cs as separate, sequential invocations, never concurrently
-- running both at once against arXiv's API is what caused sustained
rate-limiting (HTTP 429) during the keyword-based re-pull earlier this
session (see build_pillar_paper_list.py's ARXIV_POLITENESS_DELAY_S comment).

Usage:
    python3 scripts/build_full_category_corpus.py quantum
    python3 scripts/build_full_category_corpus.py cs
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
DATA_DIR = ROOT / "data"

UA = "Mozilla/5.0 (research; systematic-review-tool; contact:as3485@rit.edu)"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
OPENSEARCH_NS = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}
PAGE_SIZE = 100
POLITENESS_DELAY_S = 8
SAFE_LIMIT = 9000  # stay comfortably clear of arXiv's ~10,000 deep-pagination ceiling
MAX_SPLIT_DEPTH = 25  # guards against runaway recursion; a window this many
                       # halvings deep would be sub-hour, never actually needed

RANGE_START = datetime(2021, 1, 1)
RANGE_END = datetime(2030, 12, 31, 23, 59)

CATEGORIES = {
    "quantum": ["quant-ph", "cond-mat.supr-con", "cond-mat.mes-hall"],
    "cs": ["cs.DS", "cs.CC", "cs.LG", "cs.NA", "cs.IT", "cs.CR", "cs.AR", "cs.PL",
           "cs.DC", "cs.ET", "eess.SY", "eess.SP", "physics.app-ph"],
}


def checkpoint_path(group: str) -> Path:
    return CACHE_DIR / f"full_category_corpus_{group}_checkpoint.json"


def output_path(group: str) -> Path:
    return DATA_DIR / f"{group}_full_category_corpus.jsonl"


def fmt_date(d: datetime) -> str:
    return d.strftime("%Y%m%d%H%M")


def load_checkpoint(group: str) -> dict:
    p = checkpoint_path(group)
    if p.exists():
        return json.loads(p.read_text())
    return {"done": False, "completed_windows": [], "total_fetched": 0}


def save_checkpoint(group: str, cp: dict):
    checkpoint_path(group).write_text(json.dumps(cp))


def parse_entries(root) -> list[dict]:
    entries = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        id_url = entry.find("atom:id", ARXIV_NS).text
        m = re.search(r"abs/(.+)$", id_url)
        arxiv_id = m.group(1) if m else id_url
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        title = entry.find("atom:title", ARXIV_NS).text.strip().replace("\n", " ")
        published = entry.find("atom:published", ARXIV_NS).text
        abstract = entry.find("atom:summary", ARXIV_NS).text.strip().replace("\n", " ")
        authors = [a.find("atom:name", ARXIV_NS).text for a in entry.findall("atom:author", ARXIV_NS)]
        primary_cat_el = entry.find("arxiv:primary_category", ARXIV_NS)
        primary_category = primary_cat_el.get("term") if primary_cat_el is not None else ""
        entries.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "published": published,
            "year": published[:4] if published else "",
            "abstract": abstract,
            "primary_category": primary_category,
            "abs_link": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_link": f"https://arxiv.org/pdf/{arxiv_id}",
        })
    return entries


def _query(search_query: str, start: int, max_results: int):
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return ET.fromstring(resp.read())
        except Exception as e:
            print(f"  ! fetch error (attempt {attempt + 1}) start={start}: {e}", file=sys.stderr)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch start={start} after retries")


def window_total(search_query: str) -> int:
    root = _query(search_query, 0, 1)
    tr = root.find("opensearch:totalResults", OPENSEARCH_NS)
    return int(tr.text) if tr is not None else 0


def paginate_window(categories: list[str], win_start: datetime, win_end: datetime,
                     total: int, out, seen_ids: set) -> int:
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    search_query = f"({cat_query}) AND submittedDate:[{fmt_date(win_start)} TO {fmt_date(win_end)}]"
    fetched = 0
    start = 0
    while start < total:
        root = _query(search_query, start, PAGE_SIZE)
        entries = parse_entries(root)
        if not entries:
            break
        new_count = 0
        for e in entries:
            if e["arxiv_id"] in seen_ids:
                continue
            seen_ids.add(e["arxiv_id"])
            out.write(json.dumps(e) + "\n")
            new_count += 1
        out.flush()
        fetched += new_count
        start += PAGE_SIZE
        if start < total:
            time.sleep(POLITENESS_DELAY_S)
    return fetched


def process_window(categories: list[str], win_start: datetime, win_end: datetime,
                    out, seen_ids: set, cp: dict, group: str, depth: int = 0) -> int:
    window_key = f"{fmt_date(win_start)}-{fmt_date(win_end)}"
    if window_key in cp["completed_windows"]:
        return 0

    time.sleep(POLITENESS_DELAY_S)
    total = window_total(
        f"({' OR '.join(f'cat:{c}' for c in categories)}) AND "
        f"submittedDate:[{fmt_date(win_start)} TO {fmt_date(win_end)}]"
    )
    print(f"[{group}] window {win_start.date()} to {win_end.date()}: {total} papers (depth={depth})")

    if total == 0:
        cp["completed_windows"].append(window_key)
        save_checkpoint(group, cp)
        return 0

    if total <= SAFE_LIMIT or depth >= MAX_SPLIT_DEPTH:
        time.sleep(POLITENESS_DELAY_S)
        fetched = paginate_window(categories, win_start, win_end, total, out, seen_ids)
        cp["total_fetched"] += fetched
        cp["completed_windows"].append(window_key)
        save_checkpoint(group, cp)
        print(f"[{group}]   -> fetched {fetched} new, running total {cp['total_fetched']}")
        return fetched

    # Too many results for one window -- split in half by date and recurse.
    mid = win_start + (win_end - win_start) / 2
    n1 = process_window(categories, win_start, mid, out, seen_ids, cp, group, depth + 1)
    n2 = process_window(categories, mid + timedelta(minutes=1), win_end, out, seen_ids, cp, group, depth + 1)
    cp["completed_windows"].append(window_key)  # mark the parent done too, once both halves are
    save_checkpoint(group, cp)
    return n1 + n2


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CATEGORIES:
        print(f"usage: python3 {Path(__file__).name} [{'|'.join(CATEGORIES)}]")
        sys.exit(1)
    group = sys.argv[1]
    categories = CATEGORIES[group]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    cp = load_checkpoint(group)
    if cp.get("done"):
        print(f"Checkpoint indicates {group} full-category pull already complete. "
              f"Delete {checkpoint_path(group)} to redo.")
        return

    out_path = output_path(group)
    seen_ids = set()
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                try:
                    seen_ids.add(json.loads(line)["arxiv_id"])
                except Exception:
                    pass

    print(f"[{group}] categories: {categories}")
    print(f"[{group}] resuming with {len(seen_ids)} already cached, "
          f"{len(cp['completed_windows'])} windows already completed")

    with open(out_path, "a") as out:
        process_window(categories, RANGE_START, RANGE_END, out, seen_ids, cp, group)

    cp["done"] = True
    save_checkpoint(group, cp)
    print(f"[{group}] complete. Total papers cached: {cp['total_fetched']} "
          f"(unique in file: {len(seen_ids)})")


if __name__ == "__main__":
    main()

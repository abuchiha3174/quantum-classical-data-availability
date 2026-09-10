"""
Build a combined paper list for one comparison group ("quantum" or "cs") by
querying arXiv once per pillar (see domain_definitions.py) and merging /
deduplicating the results into a single output file per group.

Pillar 1 in each group ("hardware") reuses an existing verified dataset
instead of re-querying, if one is configured in domain_definitions.py.

Output auto-increments each run: data/quantum_pillars_run1.jsonl,
data/quantum_pillars_run2.jsonl, ... so successive runs (e.g. after editing
domain_definitions.py) are never silently overwritten and can be diffed.

Does nothing on import -- run explicitly:
    python3 scripts/build_pillar_paper_list.py quantum
    python3 scripts/build_pillar_paper_list.py cs
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_definitions import GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UA = "Mozilla/5.0 (research; systematic-review-tool; contact:as3485@rit.edu)"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
OPENSEARCH_NS = {"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}
ARXIV_POLITENESS_DELAY_S = 8  # bumped from 3s 2026-08-30 -- two concurrent pulls (quantum
# + cs) at 3s each triggered sustained 429s across dozens of keywords in both runs;
# 8s plus the retry hardening below cleared every failed keyword on the sequential retry.
PAGE_SIZE = 100

# Matches the superconducting-qubit dataset's scope (last ~5 years) -- every
# pillar pull, quantum or CS, must use the same window or the comparison
# isn't fair. Upper bound is a far-future cap rather than "now" so this
# doesn't need updating; arXiv just won't have anything past today anyway.
DATE_RANGE = "submittedDate:[202101010000 TO 203012312359]"


def next_run_path(group: str) -> Path:
    n = 1
    while (DATA_DIR / f"{group}_pillars_run{n}.jsonl").exists():
        n += 1
    return DATA_DIR / f"{group}_pillars_run{n}.jsonl"


def arxiv_search_all(keyword: str, categories: list[str], pillar_id: str):
    """Paginate through every result for one keyword+category query, using arXiv's
    own reported totalResults to decide when to stop -- rather than an arbitrary
    100-result cap that silently truncated high-volume keywords (found 2026-08-29:
    some keywords like "quantum machine learning" or "machine learning algorithm"
    have 1000+ true matches, of which the old single-page version only ever kept
    the newest 100)."""
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    kw_query = f'(ti:"{keyword}" OR abs:"{keyword}")'
    search_query = f"({kw_query}) AND ({cat_query}) AND {DATE_RANGE}"

    all_entries = []
    start = 0
    total_results = None
    while True:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": PAGE_SIZE,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        root = None
        for attempt in range(8):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    root = ET.fromstring(resp.read())
                break
            except Exception as e:
                print(f"    ! fetch error (attempt {attempt + 1}) for {keyword!r} start={start}: {e}")
                time.sleep(10 * (attempt + 1))
        if root is None:
            print(f"    ! giving up on {keyword!r} at start={start} after retries")
            break

        if total_results is None:
            tr = root.find("opensearch:totalResults", OPENSEARCH_NS)
            total_results = int(tr.text) if tr is not None else 0

        page_entries = parse_entries(root, pillar_id)
        if not page_entries:
            break
        all_entries.extend(page_entries)
        start += PAGE_SIZE
        if start >= total_results:
            break
        time.sleep(ARXIV_POLITENESS_DELAY_S)

    return all_entries, (total_results or 0)


def parse_entries(root, pillar_id: str):
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
            "pillars": {pillar_id},
        })
    return entries


def load_existing_dataset(csv_path: str, pillar_id: str):
    """Reuse an already-built, already-verified dataset instead of re-querying."""
    path = ROOT / csv_path
    if not path.exists():
        print(f"  ! configured existing_dataset not found: {path}")
        return []
    papers = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            aid = row.get("arXiv ID", "").strip()
            if not aid:
                continue
            papers.append({
                "arxiv_id": aid,
                "title": row.get("Title", ""),
                "authors": row.get("Authors", "").split("; ") if row.get("Authors") else [],
                "published": row.get("Published Date", ""),
                "year": row.get("Published Year", ""),
                "abstract": "",
                "primary_category": "",
                "abs_link": row.get("Paper Link", ""),
                "pdf_link": row.get("PDF/HTML Link", ""),
                "pillars": {pillar_id},
            })
    return papers


def build_group(group: str):
    pillars = GROUPS[group]
    by_id: dict[str, dict] = {}

    for pillar in pillars:
        if pillar.get("existing_dataset"):
            existing = load_existing_dataset(pillar["existing_dataset"], pillar["id"])
            for p in existing:
                if p["arxiv_id"] in by_id:
                    by_id[p["arxiv_id"]]["pillars"] |= p["pillars"]
                else:
                    by_id[p["arxiv_id"]] = p
            print(f"[{pillar['id']}] {pillar['name']}: reused {len(existing)} papers from existing dataset")
            continue

        pillar_count = 0
        for keyword in pillar["keywords"]:
            try:
                entries, total_results = arxiv_search_all(keyword, pillar["arxiv_categories"], pillar["id"])
            except Exception as e:
                print(f"  ! query failed for {pillar['id']} / {keyword!r}: {e}")
                continue
            for e in entries:
                if e["arxiv_id"] in by_id:
                    by_id[e["arxiv_id"]]["pillars"] |= e["pillars"]
                else:
                    by_id[e["arxiv_id"]] = e
            pillar_count += len(entries)
            print(f"    {keyword!r}: fetched {len(entries)}/{total_results}")
            time.sleep(ARXIV_POLITENESS_DELAY_S)
        print(f"[{pillar['id']}] {pillar['name']}: {pillar_count} raw hits across {len(pillar['keywords'])} keyword queries")

    papers = list(by_id.values())
    for p in papers:
        p["pillars"] = sorted(p["pillars"])

    out_path = next_run_path(group)
    with open(out_path, "w") as f:
        for p in papers:
            f.write(json.dumps(p) + "\n")

    print(f"\nwrote {len(papers)} deduplicated papers to {out_path}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in GROUPS:
        print(f"usage: python3 {Path(__file__).name} [{'|'.join(GROUPS)}]")
        sys.exit(1)
    build_group(sys.argv[1])

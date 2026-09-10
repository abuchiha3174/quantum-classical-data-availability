#!/usr/bin/env python3
"""
Phase 1: Pull superconducting-qubit quantum computing papers from arXiv API.
Paginates through results sorted by submittedDate descending, stops once
entries fall before 2021-01-01. Writes incremental JSON-lines cache and
a checkpoint file so progress survives interruption.
"""
import urllib.request
import urllib.parse
import time
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

WORKDIR = "/Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review"
CACHE_DIR = os.path.join(WORKDIR, "cache")
JSONL_PATH = os.path.join(CACHE_DIR, "arxiv_papers.jsonl")
CHECKPOINT_PATH = os.path.join(CACHE_DIR, "arxiv_checkpoint.json")

BASE_URL = "http://export.arxiv.org/api/query"
SEARCH_QUERY = '(abs:"superconducting qubit" OR abs:"superconducting qubits" OR ti:"superconducting qubit" OR ti:"superconducting qubits") AND (cat:quant-ph OR cat:cond-mat.supr-con OR cat:cond-mat.mes-hall)'
MAX_RESULTS = 100
CUTOFF_DATE = datetime(2021, 1, 1, tzinfo=timezone.utc)
USER_AGENT = "qDATA-systematic-review-bot/1.0 (mailto:as3485@rit.edu; academic research on data availability in quantum computing papers)"

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom',
    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
}


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"start": 0, "done": False, "total_fetched": 0}


def save_checkpoint(cp):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(cp, f)


def fetch_page(start):
    params = {
        "search_query": SEARCH_QUERY,
        "start": start,
        "max_results": MAX_RESULTS,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            print(f"  fetch error (attempt {attempt+1}): {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch start={start} after retries")


def parse_entries(xml_bytes):
    root = ET.fromstring(xml_bytes)
    total_results = root.find('opensearch:totalResults', NS)
    total_results = int(total_results.text) if total_results is not None else None
    entries = []
    for entry in root.findall('atom:entry', NS):
        id_url = entry.find('atom:id', NS).text.strip()
        # arxiv id like http://arxiv.org/abs/2101.01234v1
        arxiv_id = id_url.rsplit('/', 1)[-1]
        arxiv_id_noversion = arxiv_id.split('v')[0] if 'v' in arxiv_id.split('/')[-1] else arxiv_id
        title = entry.find('atom:title', NS).text.strip().replace('\n', ' ').replace('  ', ' ')
        summary = entry.find('atom:summary', NS).text.strip().replace('\n', ' ')
        published = entry.find('atom:published', NS).text.strip()
        authors = [a.find('atom:name', NS).text for a in entry.findall('atom:author', NS)]
        links = entry.findall('atom:link', NS)
        abs_link = ""
        pdf_link = ""
        for l in links:
            if l.get('type') == 'text/html' or l.get('rel') == 'alternate':
                abs_link = l.get('href')
            if l.get('title') == 'pdf':
                pdf_link = l.get('href')
        primary_cat_el = entry.find('arxiv:primary_category', NS)
        primary_cat = primary_cat_el.get('term') if primary_cat_el is not None else ""

        entries.append({
            "arxiv_id": arxiv_id_noversion,
            "title": title,
            "authors": authors,
            "published": published,
            "year": published[:4],
            "abstract": summary,
            "abs_link": abs_link or f"https://arxiv.org/abs/{arxiv_id_noversion}",
            "pdf_link": pdf_link or f"https://arxiv.org/pdf/{arxiv_id_noversion}",
            "primary_category": primary_cat,
        })
    return entries, total_results


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = load_checkpoint()
    if cp.get("done"):
        print("Checkpoint indicates Phase 1 already complete. Delete checkpoint to redo.")
        return

    start = cp["start"]
    total_fetched = cp["total_fetched"]
    seen_ids = set()
    if os.path.exists(JSONL_PATH):
        with open(JSONL_PATH) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    seen_ids.add(rec["arxiv_id"])
                except Exception:
                    pass

    print(f"Resuming from start={start}, {len(seen_ids)} already cached")

    with open(JSONL_PATH, "a") as out:
        while True:
            print(f"Fetching start={start} ...")
            xml_bytes = fetch_page(start)
            entries, total_results = parse_entries(xml_bytes)
            if total_results is not None:
                print(f"  totalResults reported by API: {total_results}")

            if not entries:
                print("No more entries returned. Stopping.")
                cp["done"] = True
                save_checkpoint(cp)
                break

            stop = False
            new_count = 0
            for e in entries:
                try:
                    pub_dt = datetime.strptime(e["published"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except Exception:
                    pub_dt = None
                if pub_dt is not None and pub_dt < CUTOFF_DATE:
                    stop = True
                    continue
                if e["arxiv_id"] in seen_ids:
                    continue
                seen_ids.add(e["arxiv_id"])
                out.write(json.dumps(e) + "\n")
                new_count += 1
            out.flush()
            total_fetched += new_count
            print(f"  parsed {len(entries)} entries, {new_count} new, total cached={total_fetched}")

            start += MAX_RESULTS
            cp["start"] = start
            cp["total_fetched"] = total_fetched
            save_checkpoint(cp)

            if stop:
                print("Reached entries before 2021-01-01. Stopping pagination.")
                cp["done"] = True
                save_checkpoint(cp)
                break

            if total_results is not None and start >= total_results:
                print("Reached end of result set.")
                cp["done"] = True
                save_checkpoint(cp)
                break

            time.sleep(10)  # bumped from 3s -- arXiv's export API rate-limited this
            # session twice already today (two concurrent jobs earlier, then a
            # same-offset 429/503/redirect streak on the retry); being more
            # conservative here to avoid a longer/harder throttle.

    print(f"Phase 1 complete. Total papers cached: {total_fetched}")


if __name__ == "__main__":
    main()

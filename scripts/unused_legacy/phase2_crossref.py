#!/usr/bin/env python3
"""
Phase 2: Pull journal papers on superconducting qubits from Crossref,
restricted to a set of target venues. Cache to JSON-lines; dedup against
arXiv happens in a later script (merge.py).
"""
import urllib.request
import urllib.parse
import time
import json
import os
import sys

WORKDIR = "/Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review"
CACHE_DIR = os.path.join(WORKDIR, "cache")
JSONL_PATH = os.path.join(CACHE_DIR, "crossref_papers.jsonl")
CHECKPOINT_PATH = os.path.join(CACHE_DIR, "crossref_checkpoint.json")

BASE_URL = "https://api.crossref.org/works"
USER_AGENT = "qDATA-systematic-review-bot/1.0 (mailto:as3485@rit.edu)"
FROM_DATE = "2021-01-01"
UNTIL_DATE = "2026-08-16"
ROWS = 100

TARGET_VENUES = [
    "PRX Quantum",
    "npj Quantum Information",
    "Nature Physics",
    "Quantum",
    "Physical Review Letters",
    "Physical Review A",
    "Physical Review B",
]


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"venue_idx": 0, "offset": 0, "done": False}


def save_checkpoint(cp):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(cp, f)


def fetch_page(venue, offset):
    params = {
        "query.bibliographic": "superconducting qubit",
        "filter": f"from-pub-date:{FROM_DATE},until-pub-date:{UNTIL_DATE},container-title:{venue}",
        "rows": ROWS,
        "offset": offset,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  fetch error (attempt {attempt+1}): {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch venue={venue} offset={offset}")


def parse_items(data, venue):
    items = data.get("message", {}).get("items", [])
    total = data.get("message", {}).get("total-results", 0)
    out = []
    for it in items:
        title_list = it.get("title", [])
        title = title_list[0] if title_list else ""
        if not title:
            continue
        # container-title check: crossref filter is sometimes loose, verify
        container = it.get("container-title", [])
        container_str = container[0] if container else venue
        authors = []
        for a in it.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            name = (given + " " + family).strip()
            if name:
                authors.append(name)
        doi = it.get("DOI", "")
        # published date
        pub = it.get("published-print") or it.get("published-online") or it.get("published") or {}
        date_parts = pub.get("date-parts", [[None]])[0]
        year = date_parts[0] if date_parts and date_parts[0] else None
        date_str = "-".join(str(p) for p in date_parts if p) if date_parts else ""
        out.append({
            "title": title,
            "authors": "; ".join(authors),
            "year": year,
            "published_date": date_str,
            "doi": doi,
            "venue": container_str,
            "doi_link": f"https://doi.org/{doi}" if doi else "",
        })
    return out, total


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = load_checkpoint()
    if cp.get("done"):
        print("Checkpoint indicates Phase 2 already complete. Delete checkpoint to redo.")
        return

    seen = set()
    if os.path.exists(JSONL_PATH):
        with open(JSONL_PATH) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    seen.add((rec["doi"], rec["title"]))
                except Exception:
                    pass

    with open(JSONL_PATH, "a") as out:
        venue_idx = cp["venue_idx"]
        offset = cp["offset"]
        while venue_idx < len(TARGET_VENUES):
            venue = TARGET_VENUES[venue_idx]
            print(f"Venue: {venue}, offset={offset}")
            data = fetch_page(venue, offset)
            items, total = parse_items(data, venue)
            print(f"  total-results reported: {total}, got {len(items)} items")

            new_count = 0
            for it in items:
                key = (it["doi"], it["title"])
                if key in seen:
                    continue
                seen.add(key)
                out.write(json.dumps(it) + "\n")
                new_count += 1
            out.flush()
            print(f"  {new_count} new items written")

            offset += ROWS
            if offset >= total or len(items) == 0:
                venue_idx += 1
                offset = 0

            cp["venue_idx"] = venue_idx
            cp["offset"] = offset
            save_checkpoint(cp)
            time.sleep(1.5)

        cp["done"] = True
        save_checkpoint(cp)

    print("Phase 2 complete.")


if __name__ == "__main__":
    main()

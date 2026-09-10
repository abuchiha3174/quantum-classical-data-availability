#!/usr/bin/env python3
"""
Build final CSV from merged_papers.jsonl + availability_results.jsonl.
Can be run repeatedly to regenerate the CSV as Phase 3 makes more progress.
"""
import json
import csv
import os

WORKDIR = "/Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review"
CACHE_DIR = os.path.join(WORKDIR, "cache")
DATA_DIR = os.path.join(WORKDIR, "data")
MERGED_JSONL = os.path.join(CACHE_DIR, "merged_papers.jsonl")
RESULTS_JSONL = os.path.join(CACHE_DIR, "availability_results.jsonl")
OUT_CSV = os.path.join(DATA_DIR, "superconducting_qubits_papers.csv")

HEADER = [
    "Title", "Authors", "Published Year", "Published Date", "Domain",
    "Venue/Source", "arXiv ID", "DOI", "Paper Link", "PDF/HTML Link",
    "Data Present", "Data Link(s)", "Detection Method", "Verified", "Notes",
]


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_key(row):
    return row.get("arxiv_id") or row.get("doi") or row["norm_title"]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    merged = load_jsonl(MERGED_JSONL)
    results = {r["key"]: r for r in load_jsonl(RESULTS_JSONL)}

    # sort by published_date descending for readability
    def sort_key(r):
        return r.get("published_date") or ""
    merged.sort(key=sort_key, reverse=True)

    checked_count = 0
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for row in merged:
            key = row_key(row)
            avail = results.get(key)
            if avail:
                data_present = avail.get("data_present", "Not yet checked")
                data_links = "; ".join(avail.get("data_links", []))
                method = avail.get("method", "not yet processed")
                extra_note = avail.get("notes", "")
                if data_present != "Not yet checked":
                    checked_count += 1
            else:
                data_present = "Not yet checked"
                data_links = ""
                method = "not yet processed"
                extra_note = ""

            notes = row.get("notes", "")
            if extra_note:
                notes = (notes + "; " + extra_note).strip("; ").strip()

            writer.writerow([
                row["title"],
                row["authors"],
                row.get("year", ""),
                row.get("published_date", ""),
                "Quantum Computing — Superconducting Qubits",
                row.get("venue", ""),
                row.get("arxiv_id", ""),
                row.get("doi", ""),
                row.get("paper_link", ""),
                row.get("pdf_link", ""),
                data_present,
                data_links,
                method,
                "",  # Verified - left blank
                notes,
            ])

    print(f"Wrote {len(merged)} rows to {OUT_CSV}")
    print(f"Phase 3 checked (not 'Not yet checked'): {checked_count} / {len(merged)}")


if __name__ == "__main__":
    main()

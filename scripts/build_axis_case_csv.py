"""
Build a review-ready CSV from axis_case_classifier.py's output, joined back
against the pillar paper list for title/author/date metadata -- same join
pattern as build_pillar_csv.py.

Usage:
    python3 scripts/build_axis_case_csv.py quantum
    python3 scripts/build_axis_case_csv.py cs
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_definitions import GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE = ROOT / "cache"
AXIS_CACHE_DIR = CACHE / "axis_case"

HEADER = [
    "Title", "Authors", "Published Date", "arXiv ID", "Paper Link",
    "Axis A Case", "Axis A Evidence",
    "Axis B Case", "Axis B Evidence",
    "Confidence", "Flag For Human", "Notes",
    "Link(s) Checked", "Link Verification Result",
    "Verified", "Corrected Axis A Case", "Corrected Axis B Case", "Reviewer Notes",
]

CASE_LABELS = {
    1: "1 - Not present",
    2: "2 - Present, directly accessible",
    3: "3 - Present, not handed over",
    4: "4 - Present, underspecified",
    5: "5 - Claimed accessible, unverifiable",
    6: "6 - Conditional on request",
}


def latest_pillar_list(group: str) -> Path | None:
    n = 1
    latest = None
    while (DATA_DIR / f"{group}_pillars_run{n}.jsonl").exists():
        latest = DATA_DIR / f"{group}_pillars_run{n}.jsonl"
        n += 1
    return latest


def load_jsonl(path: Path) -> list:
    rows = []
    if not path.exists():
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def format_link_results(link_results: list) -> str:
    if not link_results:
        return ""
    parts = []
    for r in link_results:
        status = "OK" if r.get("resolved") else f"FAILED ({r.get('error') or r.get('status_code')})"
        parts.append(f"{r['url']} -> {status}")
    return " | ".join(parts)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in GROUPS:
        print(f"usage: python3 {Path(__file__).name} [{'|'.join(GROUPS)}]")
        sys.exit(1)
    group = sys.argv[1]

    axis_cache_path = AXIS_CACHE_DIR / f"axis_case_{group}.jsonl"
    axis_results = {d["arxiv_id"]: d for d in load_jsonl(axis_cache_path)}
    if not axis_results:
        print(f"no results in {axis_cache_path} -- run axis_case_classifier.py --group {group} first")
        sys.exit(1)

    # Pull title/author/date metadata. The current, comprehensive source is
    # the full category-based corpus -- every paper that can be classified
    # was extracted from it, so it should cover ~all cases. The legacy
    # pillar list and merged_papers.jsonl are checked first and merged in
    # underneath it (full-corpus entries win on conflict), only to cover the
    # rare paper predating the full-corpus pull that isn't in it. Bug fixed
    # 2026-09-10: this used to check ONLY the pillar list, which left 97% of
    # CS rows with a blank title/author/date because most classified CS
    # papers came from the full-corpus pull, not the old pillar-based one.
    meta = {}
    for source in (CACHE / "merged_papers.jsonl", latest_pillar_list(group),
                   DATA_DIR / f"{group}_full_category_corpus.jsonl"):
        if source is None:
            continue
        for p in load_jsonl(source):
            meta[p["arxiv_id"]] = p  # later sources win on conflict

    out_path = DATA_DIR / f"{group}_axis_case_review.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for aid, r in axis_results.items():
            p = meta.get(aid, {})
            authors = p.get("authors", "")
            if isinstance(authors, list):
                authors = "; ".join(authors)

            axis_a = r.get("axis_a_case")
            axis_b = r.get("axis_b_case")

            w.writerow([
                p.get("title", ""),
                authors,
                p.get("published", ""),
                aid,
                p.get("abs_link", f"https://arxiv.org/abs/{aid}"),
                CASE_LABELS.get(axis_a, axis_a if axis_a is not None else "not yet run"),
                r.get("axis_a_evidence", ""),
                CASE_LABELS.get(axis_b, axis_b if axis_b is not None else "not yet run"),
                r.get("axis_b_evidence", ""),
                r.get("confidence", ""),
                "Yes" if r.get("flag_for_human") else "No",
                r.get("notes", ""),
                "; ".join(x["url"] for x in r.get("link_results", [])),
                format_link_results(r.get("link_results", [])),
                r.get("verified", ""),   # blank until a human confirms
                "",  # Corrected Axis A Case -- filled in only if the human overrides the LLM
                "",  # Corrected Axis B Case -- same
                "",  # Reviewer Notes
            ])

    n_flagged = sum(1 for r in axis_results.values() if r.get("flag_for_human"))
    print(f"wrote {len(axis_results)} rows to {out_path}")
    print(f"{n_flagged}/{len(axis_results)} flagged for human review")


if __name__ == "__main__":
    main()

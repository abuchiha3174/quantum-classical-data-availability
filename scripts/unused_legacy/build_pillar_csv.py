"""
Build a review-ready CSV for one pillar group, matching the same column
structure as data/superconducting_qubits_papers.csv, from the latest
{group}_pillars_run{N}.jsonl paper list and the detector's analysis cache.

Adds two columns beyond the original quantum CSV's structure, since this
pipeline now also does domain-pillar classification:
  - Searched Pillar(s): which pillar(s) the paper was pulled under
  - Content Pillar(s): which pillar(s) the paper's own text actually supports
  (a mismatch between these two is worth a human glancing at)

Usage:
    python3 scripts/build_pillar_csv.py quantum
    python3 scripts/build_pillar_csv.py cs
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

HEADER = [
    "Title", "Authors", "Published Year", "Published Date", "Domain",
    "Venue/Source", "arXiv ID", "Paper Link", "PDF/HTML Link",
    "Data Present", "Data Link(s)", "Detection Method",
    "Searched Pillar(s)", "Content Pillar(s)", "Verified", "Notes",
]


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


def pillar_names(group: str, ids: list) -> str:
    lookup = {p["id"]: p["name"] for p in GROUPS[group]}
    # keep pillar names for ids even if that pillar is currently commented
    # out in domain_definitions.py (e.g. a paper pulled in an earlier run
    # under a pillar that's since been disabled) -- fall back to the raw id
    return "; ".join(lookup.get(i, i) for i in ids)


def data_present_label(result: dict) -> str:
    if not result:
        return "Not yet checked"
    status = result.get("status", "")
    if "Unclear" in status:
        return "Unclear - could not fetch PDF"
    if "Candidate" in status:
        return "Yes (repository link)" if result.get("candidate_links") else "Statement only, no link"
    return "No"


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in GROUPS:
        print(f"usage: python3 {Path(__file__).name} [{'|'.join(GROUPS)}]")
        sys.exit(1)
    group = sys.argv[1]

    pillar_list_path = latest_pillar_list(group)
    if pillar_list_path is None:
        print(f"no {group}_pillars_run*.jsonl found in {DATA_DIR} -- run build_pillar_paper_list.py {group} first")
        sys.exit(1)

    papers = load_jsonl(pillar_list_path)
    cache_path = CACHE / f"analysis_cache_{group}.jsonl"
    cache = {d["arxiv_id"]: d for d in load_jsonl(cache_path)}

    papers.sort(key=lambda p: p.get("published", ""), reverse=True)

    out_path = DATA_DIR / f"{group}_papers.csv"
    checked = 0
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for p in papers:
            aid = p["arxiv_id"]
            result = cache.get(aid)
            data_present = data_present_label(result)
            if data_present not in ("Not yet checked",):
                checked += 1
            links = "; ".join(result.get("candidate_links", [])) if result else ""
            method = result.get("detection_method", "not yet processed") if result else "not yet processed"
            searched = pillar_names(group, p.get("pillars", []))
            content = pillar_names(group, result.get("content_pillars", [])) if result else ""

            w.writerow([
                p.get("title", ""),
                "; ".join(p.get("authors", [])) if isinstance(p.get("authors"), list) else p.get("authors", ""),
                p.get("year", ""),
                p.get("published", ""),
                f"{'Quantum' if group == 'quantum' else 'Classical'} Computing — {searched or 'unspecified pillar'}",
                "arXiv",
                aid,
                p.get("abs_link", ""),
                p.get("pdf_link", ""),
                data_present,
                links,
                method,
                searched,
                content,
                "",  # Verified -- left blank for manual review
                "",  # Notes -- left blank for manual review
            ])

    print(f"wrote {len(papers)} rows to {out_path}")
    print(f"already scanned by detector: {checked} / {len(papers)}")
    print(f"source paper list: {pillar_list_path}")


if __name__ == "__main__":
    main()

import csv
import json

CSV_V1 = "data/superconducting_qubits_papers.csv"
CSV_V2 = "data/superconducting_qubits_papers_v2.csv"
V2_RESULTS = "cache/detector_v2_results.jsonl"


def main():
    v2_by_id = {}
    with open(V2_RESULTS) as f:
        for line in f:
            d = json.loads(line)
            v2_by_id[d["arxiv_id"]] = d

    with open(CSV_V1, newline="") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    arxiv_idx = header.index("arXiv ID")
    data_idx = header.index("Data Present")
    verified_idx = header.index("Verified")

    new_header = header + [
        "v2 Signal",
        "v2 Candidate Links",
        "v2 Keyword Hits",
        "Changed vs v1",
    ]

    out_rows = [new_header]
    changed_count = 0
    v1_no_v2_candidate = 0

    for row in rows[1:]:
        arxiv_id = row[arxiv_idx].strip()
        v1_label = row[data_idx]
        v1_verified = row[verified_idx]
        d = v2_by_id.get(arxiv_id)

        if d is None:
            out_rows.append(row + ["not in v2 run (non-arXiv or unfetched)", "", "", ""])
            continue

        v2_status = d["status"]
        links = "; ".join(d.get("candidate_links", []))
        phrases = "; ".join(sorted({h["phrase"] for h in d.get("keyword_hits", [])}))

        v1_had_signal = v1_label not in ("No", "Not yet checked", "")
        v2_had_signal = "Candidate" in v2_status
        changed = v1_had_signal != v2_had_signal

        if changed:
            changed_count += 1
            if v1_had_signal is False and v2_had_signal is True:
                pass  # v2 caught something v1 missed - the important direction
        if (not v1_had_signal) and (not v1_verified) and v2_had_signal:
            v1_no_v2_candidate += 1  # v1 said no signal (unverified), v2 disagrees -> priority review

        out_rows.append(row + [v2_status, links, phrases, "YES" if changed else ""])

    with open(CSV_V2, "w", newline="") as f:
        w = csv.writer(f)
        w.writerows(out_rows)

    print(f"wrote {CSV_V2}")
    print(f"total rows: {len(out_rows)-1}")
    print(f"rows where v1 label and v2 signal disagree: {changed_count}")
    print(f"  of those, v1 said 'No'/unverified but v2 found a candidate signal: {v1_no_v2_candidate}")
    print("  (this last number is your priority re-check list -- v1 may have silently missed these)")


if __name__ == "__main__":
    main()

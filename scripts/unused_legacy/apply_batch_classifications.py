"""
Apply a set of classifications (keyed by arxiv_id) onto the ORIGINAL,
full-text batch records, producing the batch's "_done.jsonl" output.

This exists because classification is done from a condensed digest
(make_batch_digest.py), not the full paper_text, to keep what a reviewer
has to read manageable -- but the file that gets merged back into the
shared cache (merge_axis_case_batches.py) must still carry each record's
original, complete, unmodified paper_text and link_results. This script is
what reunites the two: it takes the small classifications file (just the
judgment fields, nothing else) and writes it onto a copy of the original
full record.

The classifications file is plain JSON: a single object mapping
arxiv_id -> {axis_a_case, axis_a_evidence, axis_b_case, axis_b_evidence,
confidence, flag_for_human, notes}.

Usage:
    python3 scripts/apply_batch_classifications.py \\
        cache/axis_case/batches/quantum_batch_000.jsonl \\
        cache/axis_case/batches/quantum_batch_000_classifications.json \\
        cache/axis_case/batches/quantum_batch_000_done.jsonl
"""
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ["axis_a_case", "axis_a_evidence", "axis_b_case", "axis_b_evidence",
                   "confidence", "flag_for_human", "notes"]


def main():
    if len(sys.argv) != 4:
        print(f"usage: python3 {Path(__file__).name} <original_batch.jsonl> "
              f"<classifications.json> <output_done.jsonl>")
        sys.exit(1)

    batch_path, classifications_path, out_path = (Path(p) for p in sys.argv[1:4])

    classifications = json.loads(classifications_path.read_text())

    original = []
    with open(batch_path) as f:
        for line in f:
            original.append(json.loads(line))

    missing = [r["arxiv_id"] for r in original if r["arxiv_id"] not in classifications]
    if missing:
        print(f"ERROR: {len(missing)} paper(s) in {batch_path.name} have no classification "
              f"in {classifications_path.name} -- refusing to write a partial output.")
        for aid in missing[:20]:
            print(f"  missing: {aid}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        sys.exit(1)

    problems = []
    for r in original:
        c = classifications[r["arxiv_id"]]
        for field in REQUIRED_FIELDS:
            if field not in c:
                problems.append(f"{r['arxiv_id']}: classification missing field {field!r}")
        for axis_field in ("axis_a_case", "axis_b_case"):
            v = c.get(axis_field)
            if v is not None and not (1 <= v <= 6):
                problems.append(f"{r['arxiv_id']}: {axis_field}={v} out of range 1-6")

    if problems:
        print(f"ERROR: {len(problems)} validation problem(s) -- refusing to write output:")
        for p in problems[:20]:
            print(f"  {p}")
        sys.exit(1)

    with open(out_path, "w") as f:
        for r in original:
            c = classifications[r["arxiv_id"]]
            merged = dict(r)  # preserves arxiv_id, paper_text, link_results, verified unchanged
            merged.update({field: c[field] for field in REQUIRED_FIELDS})
            f.write(json.dumps(merged) + "\n")

    print(f"wrote {len(original)} fully-classified records to {out_path}")


if __name__ == "__main__":
    main()

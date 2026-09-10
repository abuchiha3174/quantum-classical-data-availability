"""
Apply a single paper's finished classification directly onto the shared
cache/axis_case/axis_case_{group}.jsonl cache, in place -- so a classifying
agent can persist progress after EVERY paper instead of only at the end of
a whole batch. This exists specifically because batch-level persistence
(the original split/classify-whole-batch/merge flow) is all-or-nothing: if
an agent is interrupted mid-batch, every paper it already finished in that
batch is lost, since nothing gets written until the full batch is done.

This script is intentionally narrow: it replaces exactly one record (matched
by arxiv_id) with a fully-classified version, and refuses to run unless that
replacement record actually looks classified (same validation
merge_axis_case_batches.py already applies), so a bad or partial record can
never silently overwrite a good pending one.

Usage:
    python3 scripts/apply_one_classification.py <group> <classified_record.json>

<classified_record.json> is a single JSON object (not JSON-lines) with at
least: arxiv_id, axis_a_case, axis_a_evidence, axis_b_case, axis_b_evidence,
confidence, flag_for_human, notes. Any other fields present (paper_text,
link_results, verified) are used as-is if given, or preserved from the
existing pending record if omitted -- so the caller only needs to pass the
fields it actually filled in, not retype the whole record.

After running this for a paper, refresh the human-readable outputs:
    python3 scripts/build_axis_case_csv.py <group>
    python3 scripts/build_axis_case_xlsx.py <group>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXIS_CACHE_DIR = ROOT / "cache" / "axis_case"

REQUIRED_FIELDS = ["axis_a_case", "axis_a_evidence", "axis_b_case", "axis_b_evidence",
                   "confidence", "flag_for_human", "notes"]


def main():
    if len(sys.argv) != 3:
        print(f"usage: python3 {Path(__file__).name} <group> <classified_record.json>")
        sys.exit(1)

    group, record_path = sys.argv[1], Path(sys.argv[2])
    cache_path = AXIS_CACHE_DIR / f"axis_case_{group}.jsonl"
    if not cache_path.exists():
        print(f"no cache at {cache_path}")
        sys.exit(1)

    update = json.loads(record_path.read_text())
    arxiv_id = update.get("arxiv_id")
    if not arxiv_id:
        print("record is missing arxiv_id")
        sys.exit(1)

    for field in REQUIRED_FIELDS:
        if field not in update:
            print(f"ERROR: record missing required field {field!r} -- refusing to apply")
            sys.exit(1)
    for axis_field in ("axis_a_case", "axis_b_case"):
        v = update[axis_field]
        if not (isinstance(v, int) and 1 <= v <= 6):
            print(f"ERROR: {axis_field}={v!r} is not an integer 1-6 -- refusing to apply")
            sys.exit(1)
    if update.get("notes") == "pending_claude_code_classification":
        print("ERROR: record still marked pending -- refusing to apply")
        sys.exit(1)

    found = False
    lines_out = []
    with open(cache_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("arxiv_id") == arxiv_id:
                found = True
                merged = dict(d)
                merged.update(update)  # only overwrites fields actually present in `update`
                lines_out.append(json.dumps(merged))
            else:
                lines_out.append(line.rstrip("\n"))

    if not found:
        print(f"ERROR: {arxiv_id} not found in {cache_path} -- refusing to apply")
        sys.exit(1)

    with open(cache_path, "w") as f:
        f.write("\n".join(lines_out) + "\n")

    print(f"applied classification for {arxiv_id} to {cache_path}")


if __name__ == "__main__":
    main()

"""
Merge completed batch files (written by parallel classification agents, per
the manifest from split_axis_case_batches.py) back into the main
cache/axis_case/axis_case_{group}.jsonl cache.

Only one process should ever run this (unlike the batch files themselves,
which are each owned by exactly one agent) -- it's the single point where
parallel work gets folded back into the shared cache, so it's the one place
a write race could happen if run twice concurrently. Run it once, after
confirming every batch's *_done.jsonl file exists.

A record from a *_done.jsonl file replaces the pending record with the same
arxiv_id in the main cache. Records for arxiv_ids not present in any batch
(i.e., papers that were already classified before this batch round, or
weren't part of this split) are left untouched.

Usage:
    python3 scripts/merge_axis_case_batches.py --group quantum
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXIS_CACHE_DIR = ROOT / "cache" / "axis_case"
BATCH_DIR = AXIS_CACHE_DIR / "batches"

REQUIRED_FIELDS = ["axis_a_case", "axis_a_evidence", "axis_b_case", "axis_b_evidence",
                   "confidence", "flag_for_human", "notes"]


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def validate(record: dict, batch_path: Path) -> list[str]:
    problems = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            problems.append(f"{record.get('arxiv_id', '?')}: missing field {field!r}")
    if record.get("notes") == "pending_claude_code_classification":
        problems.append(f"{record.get('arxiv_id', '?')}: still marked pending in {batch_path.name} -- "
                         f"was this record actually classified?")
    if record.get("axis_a_case") is not None and not (1 <= record["axis_a_case"] <= 6):
        problems.append(f"{record.get('arxiv_id', '?')}: axis_a_case out of range: {record['axis_a_case']}")
    if record.get("axis_b_case") is not None and not (1 <= record["axis_b_case"] <= 6):
        problems.append(f"{record.get('arxiv_id', '?')}: axis_b_case out of range: {record['axis_b_case']}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", required=True)
    parser.add_argument("--allow-incomplete", action="store_true",
                         help="Merge whatever *_done.jsonl files exist even if the manifest lists "
                              "some batches as not yet finished. Default: refuse unless all are present.")
    args = parser.parse_args()

    manifest_path = BATCH_DIR / f"{args.group}_manifest.json"
    if not manifest_path.exists():
        print(f"no manifest at {manifest_path} -- run split_axis_case_batches.py first")
        return
    manifest = json.loads(manifest_path.read_text())

    missing = [b for b in manifest if not Path(b["done_path"]).exists()]
    if missing and not args.allow_incomplete:
        print(f"{len(missing)}/{len(manifest)} batches are not done yet -- refusing to merge partial results.")
        for b in missing:
            print(f"  missing: {b['done_path']}")
        print("Pass --allow-incomplete to merge the batches that ARE done anyway "
              "(the rest stay pending and can be re-batched later).")
        return

    all_problems = []
    updates: dict[str, dict] = {}
    for b in manifest:
        done_path = Path(b["done_path"])
        if not done_path.exists():
            continue
        records = load_jsonl(done_path)
        if len(records) != b["n_papers"]:
            all_problems.append(f"{done_path.name}: expected {b['n_papers']} records, found {len(records)}")
        for r in records:
            all_problems.extend(validate(r, done_path))
            updates[r["arxiv_id"]] = r

    if all_problems:
        print(f"{len(all_problems)} validation problem(s) found -- refusing to merge until fixed:")
        for p in all_problems[:50]:
            print(f"  {p}")
        if len(all_problems) > 50:
            print(f"  ... and {len(all_problems) - 50} more")
        return

    main_cache_path = AXIS_CACHE_DIR / f"axis_case_{args.group}.jsonl"
    existing = {r["arxiv_id"]: r for r in load_jsonl(main_cache_path)}
    n_replaced = sum(1 for aid in updates if aid in existing)
    existing.update(updates)

    with open(main_cache_path, "w") as f:
        for r in existing.values():
            f.write(json.dumps(r) + "\n")

    still_pending = sum(1 for r in existing.values() if r.get("notes") == "pending_claude_code_classification")
    print(f"merged {len(updates)} classified records ({n_replaced} replaced pending records) into {main_cache_path}")
    print(f"{still_pending} records remain pending (not part of this batch round, if any)")
    print(f"next: python3 scripts/build_axis_case_csv.py {args.group}")


if __name__ == "__main__":
    main()

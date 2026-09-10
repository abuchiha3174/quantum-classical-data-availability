"""
Split the pending records in cache/axis_case/axis_case_{group}.jsonl into N
batch files, so that N independent classification agents (Claude Code
sub-agents, or separate human reviewers) can work in parallel without ever
writing to the same file -- this is what makes the parallel classification
step (Stage 4) safe to run concurrently.

Design rationale: multiple agents writing to one shared JSONL file at the
same time is a race condition (interleaved writes corrupt the file, or one
agent's write silently clobbers another's). Instead, each agent gets its own
batch file to read AND its own separate output file to write -- no file is
ever touched by more than one agent. merge_axis_case_batches.py
(run afterward, by one process) is the only step that reads all the batch
outputs and folds them back into the shared cache.

Only records still marked "pending_claude_code_classification" are batched
(already-classified records are left alone), so this script is safe to
re-run if some papers still need classifying after a previous batch round
(e.g., a batch that failed, or newly extracted papers from a later Stage 3
run).

Usage:
    python3 scripts/split_axis_case_batches.py --group quantum --n-batches 10
    python3 scripts/split_axis_case_batches.py --group cs --batch-size 50
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXIS_CACHE_DIR = ROOT / "cache" / "axis_case"
BATCH_DIR = AXIS_CACHE_DIR / "batches"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", required=True, help="e.g. quantum or cs")
    size_group = parser.add_mutually_exclusive_group(required=True)
    size_group.add_argument("--n-batches", type=int, help="Split into exactly this many batch files.")
    size_group.add_argument("--batch-size", type=int, help="Aim for this many papers per batch file.")
    args = parser.parse_args()

    src_path = AXIS_CACHE_DIR / f"axis_case_{args.group}.jsonl"
    all_records = load_jsonl(src_path)
    pending = [r for r in all_records if r.get("notes") == "pending_claude_code_classification"]

    print(f"source: {src_path}")
    print(f"total records: {len(all_records)}, pending classification: {len(pending)}")

    if not pending:
        print("nothing to batch -- either everything is already classified, "
              "or Stage 3 (axis_case_classifier.py) hasn't been run yet.")
        return

    if args.n_batches:
        n_batches = args.n_batches
    else:
        n_batches = max(1, math.ceil(len(pending) / args.batch_size))

    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Clear out any stale batch files from a previous split for this group,
    # so leftover batches from an earlier (different-sized) split don't get
    # mixed in with this run's manifest.
    for stale in BATCH_DIR.glob(f"{args.group}_batch_*.jsonl"):
        stale.unlink()

    batch_size = math.ceil(len(pending) / n_batches)
    manifest = []
    for i in range(n_batches):
        chunk = pending[i * batch_size: (i + 1) * batch_size]
        if not chunk:
            continue
        batch_path = BATCH_DIR / f"{args.group}_batch_{i:03d}.jsonl"
        with open(batch_path, "w") as f:
            for r in chunk:
                f.write(json.dumps(r) + "\n")
        manifest.append({"batch_id": i, "path": str(batch_path), "n_papers": len(chunk),
                          "done_path": str(BATCH_DIR / f"{args.group}_batch_{i:03d}_done.jsonl")})
        print(f"  batch {i:03d}: {len(chunk)} papers -> {batch_path}")

    manifest_path = BATCH_DIR / f"{args.group}_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nwrote {len(manifest)} batch files, manifest: {manifest_path}")
    print("Next: give each batch file to an independent classification agent "
          "(see AGENT_CLASSIFICATION_PROMPT.md for the exact instructions to "
          "use), having each one write its results to the corresponding "
          "*_done.jsonl path listed in the manifest. Then run "
          "merge_axis_case_batches.py once all batches are done.")


if __name__ == "__main__":
    main()

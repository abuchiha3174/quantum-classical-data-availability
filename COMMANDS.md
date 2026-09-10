# Command reference

All commands assume you're in the project folder:
```bash
cd /Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review
```

## Keep the laptop awake during a long run

`caffeinate -i` prevents idle sleep for as long as the wrapped command runs,
and releases automatically when it finishes -- no manual cleanup needed.
Closing the lid still sleeps the machine regardless of this, unless it's
plugged into an external display, so leave it open (or attach a monitor)
if the run needs to survive a closed lid.

```bash
# Basic: keep the machine from idling to sleep while the script runs
caffeinate -i python3 scripts/detector_v2.py --group quantum --input data/quantum_pillars_run1.jsonl

# Also keep the display on (not required for a background run, just useful
# if you want to watch the log without the screen dimming/locking)
caffeinate -di python3 scripts/detector_v2.py --group quantum --input data/quantum_pillars_run1.jsonl
```

## Step 1 — build a pillar-based paper list

Queries arXiv once per pillar keyword (see `scripts/domain_definitions.py`
to edit pillars/keywords), dedupes across pillars, writes one combined file
per group. Auto-increments each run (run1, run2, run3...) so you never
silently overwrite a previous pull.

```bash
# Quantum side (6 pillars: hardware, control, qec, algorithms, compilation, info_theory)
caffeinate -i python3 scripts/build_pillar_paper_list.py quantum

# CS side (on hold for now, but same command when ready)
caffeinate -i python3 scripts/build_pillar_paper_list.py cs
```

Output: `data/quantum_pillars_run{N}.jsonl` or `data/cs_pillars_run{N}.jsonl`

## Step 2 — run the data-availability + domain-pillar detector

Downloads each paper's PDF, extracts text + links, deletes the PDF, scans
for data/code-availability signals AND checks the paper's own content
against every pillar's keyword list. Resumable (skips already-cached
papers), and every invocation writes a fresh run-numbered snapshot.

```bash
# Point it at a specific pillar-list run, tagged with which group it is
# (enables the domain-pillar classification pass)
caffeinate -i python3 scripts/detector_v2.py --group quantum --input data/quantum_pillars_run1.jsonl

# Later, same pattern for CS
caffeinate -i python3 scripts/detector_v2.py --group cs --input data/cs_pillars_run1.jsonl

# Original mode (no group/input given) -- backward-compatible with the
# existing superconducting-qubit-only run, no domain-pillar classification
caffeinate -i python3 scripts/detector_v2.py

# Process only specific arXiv IDs (useful for quick spot-testing before a
# full run, or re-checking a handful of papers)
python3 scripts/detector_v2.py --group quantum --input data/quantum_pillars_run1.jsonl 2608.12345 2607.09876
```

Output: `data/quantum_availability_run{N}.jsonl` (or `cs_availability_run{N}.jsonl`,
or `superconducting_qubits_availability_run{N}.jsonl` for the original mode)

## Useful checks while a run is in progress

```bash
# How many papers has it cached so far, for a given group
wc -l cache/analysis_cache_quantum.jsonl

# Is the process still actually running (replace PID with the real one, or
# grep for it if you didn't note the PID when you started it)
ps aux | grep detector_v2.py | grep -v grep

# Quick breakdown of candidate vs no-signal so far, without waiting for the run to finish
python3 -c "
import json
rows = [json.loads(l) for l in open('cache/analysis_cache_quantum.jsonl')]
cand = sum(1 for d in rows if 'Candidate' in d['status'])
print(f'processed: {len(rows)}, candidates: {cand}, no-signal: {len(rows)-cand}')
"

# Disk space sanity check -- should stay roughly flat run-to-run, since PDFs
# are deleted immediately after processing (see the comment in detector_v2.py
# about the earlier 74,000-file image-extraction incident if this ever
# starts climbing unexpectedly)
du -sh cache/pdfs cache/pdftext
df -h /Users/abhisheksingh/Documents/qDATA
```

## Editing scope later

To change which keywords/categories define a pillar, edit
`scripts/domain_definitions.py` only -- both `build_pillar_paper_list.py`
and `detector_v2.py` import from it, so a single edit there is picked up
by both scripts on their next run without touching either script file.

## Step 3/4/5 — axis-case classification (data availability, per paper)

Once `detector_v2.py` has run, every paper record in
`cache/axis_case/axis_case_{group}.jsonl` sits at
`notes: "pending_claude_code_classification"` until it goes through this
batch cycle. Classification itself (reading each paper against
`DATA_AVAILABILITY_FRAMEWORK.md`'s two-axis, six-case scheme) is done by a
human/Claude Code agent reading the text directly -- it is deliberately
**not** an LLM API call inside the script (an earlier attempt to fan this
out across 10 parallel background agents failed outright due to session
usage limits; sequential, one-batch-at-a-time review replaced it and is the
current approach).

```bash
# Split all still-pending papers into fresh batch files. --batch-size is a
# *target*; the script evens it out across a whole number of batches, so
# the actual per-batch count can come out slightly under the target (e.g.
# a target of 150 over 3,372 pending papers produced 23 batches of 147
# each, not exactly 150). Batch size is not fixed across rounds -- the
# first round of this project used 100/batch, the second used a 150
# target; pick whatever size fits the session budget for that round.
python3 scripts/split_axis_case_batches.py --group quantum --batch-size 150

# For one batch file, condense each paper's full text down to head + tail +
# keyword-context windows, so it's small enough to read in a handful of
# Read calls instead of hitting the per-read token cap.
python3 scripts/make_batch_digest.py cache/axis_case/batches/quantum_batch_000.jsonl

# Read the resulting *_digest.jsonl in chunks (~6-8 papers per Read call is
# a safe token budget), classify each paper against the framework, and
# write results into a {batch}_classifications.json keyed by arxiv_id with
# the 7 required fields (axis_a_case, axis_a_evidence, axis_b_case,
# axis_b_evidence, confidence, flag_for_human, notes). Flag for human
# review (flag_for_human: true) whenever confidence isn't high or a
# judgment call was needed -- never guess silently.

# Once every paper in the batch has a classification entry, validate and
# merge it back onto the original full records (this refuses to write
# anything if even one paper is missing or malformed):
python3 scripts/apply_batch_classifications.py \
    cache/axis_case/batches/quantum_batch_000.jsonl \
    cache/axis_case/batches/quantum_batch_000_classifications.json \
    cache/axis_case/batches/quantum_batch_000_done.jsonl

# Fold the finished batch back into the shared per-group cache. Use
# --allow-incomplete whenever only some of the split batches are done --
# it merges what's finished and leaves the rest pending, rather than
# refusing to merge anything until every batch in the round is complete.
python3 scripts/merge_axis_case_batches.py --group quantum --allow-incomplete

# Rebuild the review CSV from the merged cache (safe to re-run any time;
# always reflects current state, including still-pending rows).
python3 scripts/build_axis_case_csv.py quantum

# Render that CSV as a color-coded .xlsx for human review -- rows with
# Flag For Human = Yes (including all not-yet-classified pending rows,
# which default to flagged) are filled red so they're visible without
# opening every cell. Re-run any time after build_axis_case_csv.py to
# refresh it; this step never edits the CSV itself.
python3 scripts/build_axis_case_xlsx.py quantum
```

Output: `data/{group}_axis_case_review.csv` (source of truth) and
`data/{group}_axis_case_review.xlsx` (same data, red-highlighted for review).

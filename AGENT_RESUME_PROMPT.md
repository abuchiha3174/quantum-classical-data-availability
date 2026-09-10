# Agent resume prompt

**How to use this**: paste the whole block below (everything after the line of dashes)
directly into a fresh Claude Code session, running in this repo's root directory, on
whatever machine has both this repo cloned AND the large data/cache files copied into
place (see `SESSION_HANDOFF.md`'s "Getting the data" section — this repo alone does not
have them, they're too large for git). Read `SESSION_HANDOFF.md` first for the
human-readable overview; this file is the literal, ready-to-run instruction set.

---

You are the classification worker for the CS side of a thesis data-availability
comparison project. Repo root: the current directory — confirm with `ls` that you see
`scripts/`, `DATA_AVAILABILITY_FRAMEWORK.md`, and `cache/axis_case/axis_case_cs.jsonl`
before doing anything; if any of those are missing, stop and tell the user — it means
the large data/cache files haven't been copied into place yet.

## Context

This project retrieves arXiv papers and classifies each one under a two-axis, six-case
data-availability framework (defined in `DATA_AVAILABILITY_FRAMEWORK.md` at the project
root — read it in full before classifying anything). The quantum side is fully
classified (3,472/3,478). The CS side is the active work: as of this handoff, 2,282
papers classified, 1,968 pending (already batched into
`cache/axis_case/batches/cs_batch_NNN.jsonl` files).

A separate extraction process (`scripts/detector_v2.py`) feeds new papers into this
pipeline. It is NOT running right now. CS extraction is only 15,940/345,107 done — this
is the actual bottleneck, not classification. If the user wants more than the current
1,968-paper pending pool worked through, extraction needs to run too (see "Restarting
extraction" below) — don't wait on it by default, just say so if you run out of pending
work.

`scripts/unused_legacy/` holds 13 old/superseded scripts. Ignore that directory.

## Where to resume

First pending paper as of this handoff: **`2102.05755`**, in
`cache/axis_case/batches/cs_batch_000.jsonl`. Before trusting that exact ID, verify it's
still accurate — files may have moved on since this was written:

```
python3 -c "
import json
with open('cache/axis_case/axis_case_cs.jsonl') as f:
    for line in f:
        d = json.loads(line)
        if d.get('notes') == 'pending_claude_code_classification':
            print(d['arxiv_id']); break
"
```

If that prints something other than `2102.05755`, use whatever it actually prints
instead, and work forward through the batch files in numeric order from there.

## Persistence: per-paper, not per-batch

Use `scripts/apply_one_classification.py` for EVERY paper, immediately after
classifying it — do not accumulate a batch in memory:

1. Write a small JSON file (e.g. `/tmp/one_classification.json`) with exactly:
   `arxiv_id`, `axis_a_case` (int 1-6), `axis_a_evidence`, `axis_b_case` (int 1-6),
   `axis_b_evidence`, `confidence` (`"high"`/`"medium"`/`"low"`), `flag_for_human`
   (bool), `notes`.
2. Run: `python3 scripts/apply_one_classification.py cs /tmp/one_classification.json`
   — applies it directly to the shared cache. It refuses and errors on anything
   malformed (missing field, wrong type, arxiv_id not found) — fix and retry, don't
   move on with an unapplied record.
3. Move to the next paper.

Every 10 papers, run `python3 scripts/build_axis_case_csv.py cs` and
`python3 scripts/build_axis_case_xlsx.py cs` so the human-readable review CSV/Excel
stay current.

You do NOT need `merge_axis_case_batches.py` or writing any `_done.jsonl` file —
`apply_one_classification.py` bypasses that indirection entirely.

## Stop condition

Ask the user how many papers to classify this session if not already told (previous
sessions in this project were typically capped at 50-100 papers at a time, to manage
usage). Once you hit that count: run the CSV/Excel rebuild one final time, and report a
clear summary — papers classified this session, cumulative total, pending remaining,
and the next paper to resume with.

If you hit a rate-limit error with a stated reset time, sleep past it yourself with
`sleep` and resume — don't just give up, but if the wait would be very long, it's fine
to stop short and report where you are.

Never let a step auto-background and then end your turn to "wait" for it — let a slow
tool call block, or poll for completion within the same turn.

## The classification schema

Each batch file is JSON-lines; each line has `arxiv_id`, `paper_text` (full extracted
text), `link_results` (list of already-verified links, each with `url`, `resolved`
(bool), `status_code`, `error`), and placeholder classification fields (ignore those —
produce fresh values).

Rules:
- If `link_results` shows a link the paper claims is available but it did not resolve,
  that is Case 5, not Case 2 or Case 3.
- "Available upon request" / "from the authors" with no immediate self-service link is
  Case 6.
- Case 4 is for data whose *existence* is acknowledged but described too thinly to
  locate or reconstruct. Case 3 is for data that *is* named/cited but simply has no
  access path given. Don't confuse these.
- A paper can be Case 1 on one axis and something else on the other — only Case 1 on
  *both* axes means the paper is fully theoretical.
- Base your answer only on the provided text; don't assume a dataset you recognize is
  linked elsewhere unless the text or `link_results` show it.
- `paper_text` can be very large (up to ~500,000 characters). If impractical to read
  whole, prioritize the opening ~2,500 characters, the closing ~3,500 characters
  (references/data-availability statement), and search the middle for the phrase-set in
  `scripts/make_batch_digest.py`'s `KEYWORD_PHRASES` list —
  `python3 scripts/make_batch_digest.py <batch_path>` gives a pre-condensed
  `_digest.jsonl` if that's faster. Evidence quotes must be verbatim excerpts from the
  real text either way.
- Do not spawn sub-agents to parallelize this — this project already tried parallel
  classification agents and all of them got killed by the same account-wide usage
  limit before finishing. Sequential, one paper at a time, is the proven approach.

## Restarting extraction (only if asked, or if the pending pool runs dry)

```
python3 scripts/detector_v2.py --group cs --input data/cs_full_category_corpus.jsonl
```

Safe to run for hours/overnight — checkpoints every 10 papers, resumes cleanly if
killed. Wrap it in a self-healing retry loop and `caffeinate -i` (macOS) if running
unattended:

```
caffeinate -i bash -c '
until python3 scripts/detector_v2.py --group cs --input data/cs_full_category_corpus.jsonl >> logs/cs_extraction.log 2>&1; do
  echo "$(date): crashed, retrying in 120s" >> logs/cs_extraction.log
  sleep 120
done
'
```

After extraction produces new material, run
`python3 scripts/axis_case_classifier.py --group cs --scope all` (live link
verification) then `python3 scripts/split_axis_case_batches.py --group cs --batch-size
50` (batching) before more classification.

## Hard constraints

- Never touch any file under the quantum group (no `*_quantum*` paths).
- Never edit `DATA_AVAILABILITY_FRAMEWORK.md`.
- Never edit any `.tex` file or any file under `plots/` — those are report-writing
  concerns, separate from this task.
- Never re-classify a paper whose `notes` in the main cache is already something other
  than `"pending_claude_code_classification"`.
- Never run any script against the real `cache/axis_case/axis_case_cs.jsonl` file with
  fake/dummy test data — a previous session accidentally corrupted a real record this
  way while testing. If you need to test `apply_one_classification.py`'s behavior, use
  a fake group name (e.g. `axis_case_testXXX.jsonl`, which doesn't exist) so it's
  physically impossible to touch real data.
- Do not touch anything in `scripts/unused_legacy/`.

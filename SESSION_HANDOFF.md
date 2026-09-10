# Session Handoff — Data Availability Classification Framework

**If you are a Claude Code agent reading this to continue the work: this file is
complete and self-sufficient. Everything you need — context, exact commands, the
classification schema, stop conditions, hard constraints — is below. You do not need
any other file to get started (though `AGENT_RESUME_PROMPT.md` exists as a short
pointer back here, in case that's what you were handed first).**

Thesis project (Abhishek Singh, as3485@rit.edu, advised by Prof. Daniel Krutz, with
Diana Velychko) comparing how often quantum computing papers vs. classical/CS
computing papers share their underlying data/code. Work from this repo's root
directory. `HANDOVER.md` also exists in this repo but is stale (describes a pipeline
design from before the current one) — ignore it, this file supersedes it.

**Before doing anything**: confirm with `ls` that you see `scripts/`,
`DATA_AVAILABILITY_FRAMEWORK.md`, and `cache/axis_case/axis_case_cs.jsonl`. If any of
those are missing, stop and tell the user — it means the large data/cache files (see
"Getting the data" below) haven't been copied into place yet, and nothing below will
work without them.

## The pipeline, as it currently exists

1. **Corpus retrieval** (`scripts/build_full_category_corpus.py`) — pulls every paper
   in a fixed set of arXiv "home" categories per side (quantum: `quant-ph`,
   `cond-mat.supr-con`, `cond-mat.mes-hall`; CS: `cs.DS`, `cs.CC`, `cs.LG`, `cs.NA`,
   `cs.IT`, `cs.CR`, `cs.AR`, `cs.PL`, `cs.DC`, `cs.ET`, `eess.SY`, `eess.SP`,
   `physics.app-ph`), 2021–present, **no keyword filtering**. Already run to
   completion: `data/quantum_full_category_corpus.jsonl` (109,321 papers) and
   `data/cs_full_category_corpus.jsonl` (345,107 papers).
2. **Extraction** (`scripts/detector_v2.py --group <group> --input
   data/<group>_full_category_corpus.jsonl`) — downloads each paper's PDF, extracts
   full text + candidate data/code links, deletes the PDF. Checkpoints to
   `cache/analysis_cache_<group>.jsonl`. **Quantum: fully done (3,478/3,478). CS: only
   15,940/345,107 extracted — this is the real bottleneck**, not classification. Not
   currently running.
3. **Live link verification** (`scripts/axis_case_classifier.py --group <group>
   --scope all`) — re-checks every extracted paper's links over HTTP (plus a
   free automatic content check for GitHub/Zenodo links — repo size, empty-or-not),
   writes a pending record (full text + link results + null classification fields)
   per paper to `cache/axis_case/axis_case_<group>.jsonl`.
4. **Batching** (`scripts/split_axis_case_batches.py --group <group> --batch-size
   50`, optionally `scripts/make_batch_digest.py <batch_path>` for a condensed
   version of long papers) — splits pending records into
   `cache/axis_case/batches/<group>_batch_NNN.jsonl` files.
5. **Classification (agent-driven, not scripted)** — read `DATA_AVAILABILITY_FRAMEWORK.md`
   plus a pending record's text and link results, assign `axis_a_case`/`axis_b_case`
   (1–6), evidence quotes, confidence, `flag_for_human`, notes. **Persist one paper at
   a time** via `scripts/apply_one_classification.py` (see exact loop below) — this is
   what every real classification session in this project has actually used, because
   it survives interruption; an older per-*batch* method
   (`merge_axis_case_batches.py`) still works but loses more progress if interrupted
   mid-batch.
6. **Review CSV/Excel** — `python3 scripts/build_axis_case_csv.py <group>` then
   `python3 scripts/build_axis_case_xlsx.py <group>` regenerate
   `data/<group>_axis_case_review.csv`/`.xlsx` from the current cache. Run after every
   ~10 papers classified so these stay current.

`scripts/unused_legacy/` holds 13 old/superseded scripts (pillar-based retrieval, the
original phase1/2/3 workflow, one-off batch scripts, an unused scope-classification
script). Ignore that directory unless doing historical archaeology.

## Current state (as of this handoff)

| | Quantum | CS |
|---|---|---|
| Full corpus (retrieved) | 109,321 | 345,107 |
| Extracted (Step 2) | 3,478 | 15,940 |
| Classified (Step 5) | 3,472 | 2,282 |

CS classification pending pool right now: **1,968**, already batched into
`cache/axis_case/batches/cs_batch_000.jsonl` onward. **First pending paper to resume
with: `2102.05755`** — before trusting this exact ID, verify it's still accurate (files
may have moved on since this was written):

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

Quantum side is not being actively worked (3,472/3,478 has been the number for a
while — the remaining 6 were flagged for a separate reason, see `TODO.md`).

## Exact resume loop for CS classification

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
`python3 scripts/build_axis_case_xlsx.py cs`.

Each batch file (`cache/axis_case/batches/cs_batch_NNN.jsonl`) is JSON-lines; each line
has `arxiv_id`, `paper_text` (full extracted text), `link_results` (list of
already-verified links, each with `url`, `resolved` (bool), `status_code`, `error`),
and placeholder classification fields (ignore those — produce fresh values). If a
batch's pending pool runs dry before you're told to stop, run
`python3 scripts/axis_case_classifier.py --group cs --scope all` then
`python3 scripts/split_axis_case_batches.py --group cs --batch-size 50` to pick up
anything extraction has produced since, and continue.

### Classification rules

- If `link_results` shows a link the paper claims is available but it did not
  resolve, that is Case 5, not Case 2 or Case 3.
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
  (references/data-availability statement), and search the middle for the phrase-set
  in `scripts/make_batch_digest.py`'s `KEYWORD_PHRASES` list —
  `python3 scripts/make_batch_digest.py <batch_path>` gives a pre-condensed
  `_digest.jsonl` if that's faster. Evidence quotes must be verbatim excerpts from the
  real text either way.
- Do not spawn sub-agents to parallelize this — this project already tried parallel
  classification agents and all of them got killed by the same account-wide usage
  limit before finishing. Sequential, one paper at a time, is the proven approach.
- Never let a step auto-background and then end your turn to "wait" for it — let a
  slow tool call block, or poll for completion within the same turn.

### Stop condition

Ask the user how many papers to classify this session if not already told (previous
sessions in this project were typically capped at 50-100 at a time, to manage usage).
Once you hit that count: run the CSV/Excel rebuild one final time, and report a clear
summary — papers classified this session, cumulative total, pending remaining, and the
next paper to resume with.

If you hit a rate-limit error with a stated reset time, sleep past it yourself with
`sleep` and resume — don't just give up, but if the wait would be very long, it's fine
to stop short and report where you are.

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

After extraction produces new material, run the verify + batch commands from "Exact
resume loop" above before more classification.

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
- Never start, stop, or touch `detector_v2.py` or `axis_case_classifier.py --scope
  all` if they're already running when you check — they may be running independently
  in the background; just consume their output.

## Two-axis, six-case framework

Defined in exactly one place: `DATA_AVAILABILITY_FRAMEWORK.md`. Every classifier
(human or agent) reads that file directly — never a separate copy. Axis A = external
data used; Axis B = self-generated data used. Cases 1–6 per axis: 1 = not present, 2 =
present & directly accessible, 3 = present but no access path given, 4 = present but
underspecified, 5 = claimed accessible but broken, 6 = accessible only on request.

## The report

`Singh_report.tex` is the main file; `\input`s `00-abstract.tex` through
`07-observations.tex` (in that flat, dash-numbered order — `08-planned-extensions.tex`
and `09-limitations.tex` exist on disk but are deliberately excluded from the input
list pending audit). `06-results.tex`'s aggregate-results subsection is an explicit
work-in-progress blueprint (marked as such in the file) drawing on `plots/plots.ipynb`
— not finished, figures/tables there are candidates, not final choices.

## Getting the data

The large corpus/cache files (`data/*_full_category_corpus.jsonl`,
`cache/axis_case/axis_case_*.jsonl`, etc. — several hundred MB to ~550MB each) are
**not in this git repo** (over GitHub's 100MB per-file limit, and 3.7GB total).
Whoever is continuing this needs those files transferred separately — ask
as3485@rit.edu for the current copies rather than re-extracting from scratch, since
regenerating the CS extraction alone (330K papers still to go) would take a very long
time.

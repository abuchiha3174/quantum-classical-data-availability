# Session Handoff — Data Availability Classification Framework

Thesis project (Abhishek Singh, as3485@rit.edu, advised by Prof. Daniel Krutz, with
Diana Velychko) comparing how often quantum computing papers vs. classical/CS
computing papers share their underlying data/code. Working directory when these paths
are used: `superconducting_qubits_review/` (this repo's root).

**This file replaces `HANDOVER.md`, which is stale (describes a pipeline design from
before the current one) — see the notice at the top of that file. Read this one.**

**For a literal, paste-into-Claude-Code prompt to resume classification** (exact
schema, rules, stop conditions, hard constraints — not just narrative overview), see
`AGENT_RESUME_PROMPT.md` instead. This file is the human-readable context; that one is
the machine-actionable instruction set.

## The pipeline, as it currently exists

1. **Corpus retrieval** (`scripts/build_full_category_corpus.py`) — pulls every paper
   in a fixed set of arXiv "home" categories per side (quantum: `quant-ph`,
   `cond-mat.supr-con`, `cond-mat.mes-hall`; CS: `cs.DS`, `cs.CC`, `cs.LG`, `cs.NA`,
   `cs.IT`, `cs.CR`, `cs.AR`, `cs.PL`, `cs.DC`, `cs.ET`, `eess.SY`, `eess.SP`,
   `physics.app-ph`), 2021–present, **no keyword filtering**. Already run to
   completion: `data/quantum_full_category_corpus.jsonl` (109,321 papers) and
   `data/cs_full_category_corpus.jsonl` (345,107 papers). These are large files —
   see "Getting the data" below, they are not in git.
2. **Extraction** (`scripts/detector_v2.py --group <group> --input
   data/<group>_full_category_corpus.jsonl`) — downloads each paper's PDF, extracts
   full text + candidate data/code links, deletes the PDF. Checkpoints to
   `cache/analysis_cache_<group>.jsonl`. **Quantum side: fully done (3,478/3,478
   from the original pillar-era pull, still the working set). CS side: only
   15,940/345,107 extracted so far — this is the real bottleneck.** Not currently
   running; restart with the self-healing wrapper pattern in `TODO.md`/earlier
   session notes if resuming.
3. **Live link verification** (`scripts/axis_case_classifier.py --group <group>
   --scope all`) — re-checks every extracted paper's links over HTTP, writes a
   pending record (full text + link results + null classification fields) per
   paper to `cache/axis_case/axis_case_<group>.jsonl`.
4. **Batching** (`scripts/split_axis_case_batches.py --group <group> --batch-size
   50`, optionally `scripts/make_batch_digest.py <batch_path>` for a condensed
   version of long papers) — splits pending records into
   `cache/axis_case/batches/<group>_batch_NNN.jsonl` files.
5. **Classification (agent-driven, not scripted)** — a Claude Code agent reads
   `DATA_AVAILABILITY_FRAMEWORK.md` plus a pending record's text and link results,
   and assigns `axis_a_case`/`axis_b_case` (1–6), evidence quotes, confidence,
   `flag_for_human`, notes. **Current method: per-paper, not per-batch** — write one
   record's classification to a small JSON file, then run
   `python3 scripts/apply_one_classification.py <group> <path_to_json>`, which
   applies it directly to `cache/axis_case/axis_case_<group>.jsonl` in place. (An
   older per-*batch* method — `merge_axis_case_batches.py` /
   `apply_batch_classifications.py` writing a whole batch's `_done.jsonl` at once —
   still works but loses more progress if interrupted mid-batch; per-paper is what
   was actually used for all recent sessions.)
6. **Review CSV/Excel** — `python3 scripts/build_axis_case_csv.py <group>` then
   `python3 scripts/build_axis_case_xlsx.py <group>` regenerate
   `data/<group>_axis_case_review.csv`/`.xlsx` from the current cache. Run after
   every batch of classification so these stay current.

`scripts/unused_legacy/` holds 13 old/superseded scripts (pillar-based retrieval, the
original phase1/2/3 workflow, one-off batch scripts, an unused scope-classification
script). Ignore that directory unless doing historical archaeology.

## Current state (as of this handoff)

| | Quantum | CS |
|---|---|---|
| Full corpus (retrieved) | 109,321 | 345,107 |
| Extracted (Step 2) | 3,478 | 15,940 |
| Classified (Step 5) | 3,472 | 2,282 |

CS classification pending pool right now: **1,968** already-extracted-and-verified
papers waiting to be classified (batched into `cs_batch_000.jsonl` through
`cs_batch_024.jsonl`, ~1,230 of the 1,968 — the rest need `split_axis_case_batches.py`
re-run to pick up). **First pending paper to resume with: `2102.05755`.**

Both the extraction process and the link-verification process were stopped
deliberately (not crashed) as of this handoff. Quantum side is not being actively
worked — 3,472/3,478 has been the number for a while; the remaining 6 were flagged
for a separate reason (see `TODO.md`).

**The real bottleneck is CS extraction**: only 15,940 of 345,107 CS papers have ever
been extracted. Classification can't outrun extraction — restarting extraction (and
letting it run for a long time, ideally unattended overnight with `caffeinate -i`) is
the highest-leverage next step, more than squeezing out more classification sessions
against the current small extracted pool.

## Two-axis, six-case framework

Defined in exactly one place: `DATA_AVAILABILITY_FRAMEWORK.md`. Every classifier
(human or agent) reads that file directly — never a separate copy. Axis A = external
data used; Axis B = self-generated data used. Cases 1–6 per axis: 1 = not present, 2 =
present & directly accessible, 3 = present but no access path given, 4 = present but
underspecified, 5 = claimed accessible but broken, 6 = accessible only on request.

## Report

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

## How to resume classification cleanly

1. Confirm you have the large data/cache files (see above) in place at the same
   relative paths.
2. `python3 scripts/split_axis_case_batches.py --group cs --batch-size 50` to make
   sure all currently-pending papers are batched.
3. Work through pending papers one at a time: for each, read its record from the
   relevant batch file, apply `DATA_AVAILABILITY_FRAMEWORK.md`, write a small JSON
   with the seven classification fields, run `apply_one_classification.py cs
   <path>`. Every ~10 papers, rebuild the CSV/Excel.
4. To extend the extracted pool (the real bottleneck), restart `detector_v2.py
   --group cs --input data/cs_full_category_corpus.jsonl` — safe to leave running
   for hours/overnight, checkpoints every 10 papers, resumes cleanly if killed.

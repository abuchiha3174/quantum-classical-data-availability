# Stage 4: Parallel Classification Agent Prompt

This document is the exact, reusable instruction set for the classification
step (Stage 4) of the pipeline, run as N independent agents in parallel —
one per batch file produced by `scripts/split_axis_case_batches.py`. Anyone
reproducing this pipeline should be able to follow this document without any
other context.

## Why this step exists and why it's parallelized this way

The two-axis, six-case data-availability framework
(`DATA_AVAILABILITY_FRAMEWORK.md`) requires reading each paper's actual
extracted text and judging which case applies on each axis — this is not a
pattern-matching task the earlier deterministic stages (candidate triage,
link verification) can do; it requires the same kind of judgment a human
reviewer applies. Doing this one paper at a time for a corpus in the
thousands is too slow, so it is split into N independent batches, each
handed to its own agent to classify concurrently. Each agent reads its own
input file and writes its own output file — no two agents ever touch the
same file, which is what makes running them in parallel safe (see the
docstring in `scripts/merge_axis_case_batches.py` for the race-condition
reasoning).

## Prerequisites

1. `scripts/split_axis_case_batches.py --group <group> --n-batches <N>` has
   been run, producing `cache/axis_case/batches/<group>_batch_<NNN>.jsonl`
   files and a `cache/axis_case/batches/<group>_manifest.json` listing each
   batch's input path, expected paper count, and output path.
2. `DATA_AVAILABILITY_FRAMEWORK.md` exists at the project root and has not
   been edited mid-run (if it needs editing, finish or restart all batches
   after the edit, not partway through).

## The prompt to give each agent

Give each agent exactly one batch. Substitute `<BATCH_PATH>` and
`<DONE_PATH>` from the manifest entry for that batch.

> You are classifying research papers using a fixed data-availability
> framework. First, read `DATA_AVAILABILITY_FRAMEWORK.md` at the project
> root in full — it defines Axis A (External Data), Axis B (Self-Generated
> Data), and six cases (1–6) applied identically to both axes, plus
> boundary notes on common judgment calls (e.g. Case 3 vs. Case 4).
>
> Then read `<BATCH_PATH>`. It is a JSON-lines file; each line is one
> paper's record with at least these fields: `arxiv_id`, `paper_text` (the
> full extracted text of the paper), `link_results` (a list of
> already-verified links found in the paper, each with `url`, `resolved`
> (boolean), `status_code`, and `error`), and placeholder classification
> fields currently set to `null` with `"notes":
> "pending_claude_code_classification"`.
>
> For every record in the file, read `paper_text` and `link_results`, apply
> the framework, and replace these fields in place:
> - `axis_a_case`: integer 1–6
> - `axis_a_evidence`: short direct quote or paraphrase from `paper_text`
>   supporting that case (empty string if Case 1)
> - `axis_b_case`: integer 1–6
> - `axis_b_evidence`: same, for Axis B
> - `confidence`: `"high"`, `"medium"`, or `"low"`
> - `flag_for_human`: `true` if confidence is not `"high"`, or a judgment
>   call was required at a case boundary; `false` otherwise
> - `notes`: one sentence explaining any judgment call made (or empty
>   string if none was needed)
>
> Do not modify `arxiv_id`, `paper_text`, `link_results`, or `verified`.
> Keep `verified` as whatever it already is (it should be `""`) — do not
> set it yourself; that field is for a human reviewer, not this step.
>
> Rules:
> - If `link_results` shows a link the paper claims is available but it
>   did not resolve, that is Case 5, not Case 2 or Case 3.
> - "Available upon request" / "from the authors" with no immediate
>   self-service link is Case 6.
> - Case 4 is for data whose *existence* is acknowledged but described too
>   thinly to locate or reconstruct (e.g. "we used 5,000 samples" with no
>   dataset name). Case 3 is for data that *is* named/cited but simply has
>   no access path given. Do not confuse these two.
> - A paper can be Case 1 on one axis and something else on the other —
>   Case 1 on one axis does NOT mean the paper is theoretical; only Case 1
>   on *both* axes means that.
> - Base your answer only on the provided text. Do not assume a dataset
>   name you recognize is definitely linked elsewhere unless the text or
>   `link_results` actually show that.
>
> When every record in the file has been classified, write the complete
> set of records (same JSON-lines format, one per line, all original
> fields preserved plus your updates) to `<DONE_PATH>`. Do not write
> anything to `<BATCH_PATH>` itself or to any other file. Report back the
> count of records classified and how many were flagged for human review.

## After all batches finish

Confirm every batch's `_done.jsonl` file exists (check against
`cache/axis_case/batches/<group>_manifest.json`), then run:

```bash
python3 scripts/merge_axis_case_batches.py --group <group>
python3 scripts/build_axis_case_csv.py <group>
```

The merge script validates every record (required fields present, case
values in range, nothing still marked pending) before writing anything, and
refuses to merge if a batch is missing or a record looks malformed — pass
`--allow-incomplete` only if you deliberately want to merge the batches that
finished and leave the rest pending for a later round.

> **STALE — do not use.** This describes a pipeline design (superconducting-qubit-only
> scope, pillar/keyword-based retrieval) that has since been fully replaced by a
> category-based, keyword-free corpus and a different classification workflow. Read
> `SESSION_HANDOFF.md` instead. Kept here only for historical reference.

# Handover — quantum vs. classical computing data-availability review

Read this first in a new session. Written to let a fresh conversation pick up
exactly where this one left off, with no prior context.

## The project

Thesis/paper (Abhishek Singh, working with Diana, advised by Prof. Daniel
Krutz) measuring how often quantum computing papers publish their underlying
data/code, compared to "regular" (classical) computing papers. Superconducting
qubits was picked as the first, narrowly-scoped quantum sub-domain (quantum
computing is too broad to search as one thing); the comparison is now
expanding into a structured multi-domain design (see below).

**User's email:** as3485@rit.edu

## Where things actually stand right now

### 1. Superconducting-qubit dataset — mature, mid-review
- `data/superconducting_qubits_papers.csv` — **1,478 papers**, built from
  arXiv (quant-ph, cond-mat.supr-con, cond-mat.mes-hall) + 7 journals
  (PRX Quantum, npj Quantum Information, Nature Physics, Quantum, PRL, PRA, PRB).
- High-recall data-availability scan (`detector_v2.py`, original mode, no
  `--group`) completed on all 1,379 arXiv papers: **581 flagged as
  candidates** (235 with an actual extracted link, 346 keyword-only),
  **798 no-signal**. ~99 journal-only (Crossref) papers were never run
  through this scanner — still on older, less-reliable labels.
- Manual + LLM-assisted verification of the candidate queue
  (`data/review_queue_link_found.xlsx` / `.csv`, 235 rows) is **58/235 done**
  as of this handover. Of those 58: **31 confirmed genuine open data**,
  **9 confirmed false positives** (script matched a citation to a
  third-party tool, not the paper's own data), rest are statement-only/
  placeholder-DOI/ambiguous cases. Red highlight in the xlsx = confirmed
  false positive; yellow = flagged ambiguous, needs a human look.
- **Best-case ratio reported to Daniel so far:** 235/1,478 ≈ 16% (explicitly
  caveated as optimistic — real verified rate is closer to ~53% of the 235,
  and doesn't include the keyword-only or unscanned buckets).

### 2. Domain expansion — quantum side defined, one CS pillar mid-run
Field restructured into 6 "pillars" (pipeline stages) per side, mirrored
1:1 between quantum and classical. Full table + arXiv category mappings:
**`DOMAIN_DEFINITIONS.md`**.

- Quantum: Hardware (= the existing SC-qubit dataset above) · Control &
  Operations · Error Correction · Algorithms · Compilation & Circuit
  Optimization · Information Theory. All 6 defined in
  `scripts/domain_definitions.py`, **none except Hardware have actually
  been pulled yet** — that's queued next, per Daniel's steer to do quantum
  before CS.
- CS: mirrored 6 pillars, same file. **Only "Classical Algorithms /
  computational complexity theory" is currently active** — the other 5 are
  commented out in `domain_definitions.py` (uncomment + rerun
  `build_pillar_paper_list.py cs` to add any back). This was Daniel's
  explicit ask: "if the script is easy to run, I'd run it for general
  computing just to give an initial inclination."
- **A background pipeline for that one CS pillar was running as of this
  handover** (`caffeinate`-wrapped, won't sleep the laptop) — check status
  with:
  ```bash
  ps aux | grep run_cs_algorithms_pipeline | grep -v grep
  tail -30 cache/cs_algorithms_pipeline.log
  ls -la data/cs_pillars_run*.jsonl data/cs_availability_run*.jsonl data/cs_papers.csv
  ```
  If it finished, `data/cs_papers.csv` should exist — that's the first-ever
  classical-computing data point for this comparison. **Nobody has looked
  at the results yet.** Report the numbers to the user as soon as you see
  them; don't assume completion without checking.

## Tooling (all in `scripts/`)

| Script | What it does |
|---|---|
| `domain_definitions.py` | **Single source of truth for pillar keywords/categories.** Edit only here; both scripts below import from it. |
| `build_pillar_paper_list.py [quantum\|cs]` | Queries arXiv per active pillar, dedupes, writes `data/{group}_pillars_run{N}.jsonl` (auto-increments, never overwrites). Pillar 1 ("hardware") reuses the existing CSV instead of re-querying. |
| `detector_v2.py [--group quantum\|cs] [--input path]` | Downloads PDF → extracts text+links → **deletes PDF immediately** → scans for data/code-availability signals (never auto-decides "no data," only flags candidates for human review) → also checks content against every pillar's keywords (domain-fit check, reuses the same extracted text, no extra download). Persistent cache (`cache/analysis_cache_{group}.jsonl`) so reruns after editing `domain_definitions.py` skip already-done papers. Every run writes a fresh numbered snapshot `data/{group}_availability_run{N}.jsonl`. No args = original backward-compatible SC-qubit-only mode. |
| `build_pillar_csv.py [quantum\|cs]` | Turns the latest pillar-list + analysis cache into a review-ready CSV, same 16-column shape as the original SC-qubit CSV plus `Searched Pillar(s)`/`Content Pillar(s)`. |
| `build_v2_comparison.py` | One-off: built the v1-vs-v2 diff CSV (`data/superconducting_qubits_papers_v2.csv`) showing where the improved detector disagreed with the original script. Already run, historical. |
| `batch50_apply.py` | One-off: hardcoded manual-review judgments for a specific 50-paper batch. Historical, not reusable as-is. |
| `phase1_arxiv.py`, `phase2_crossref.py`, `merge.py`, `build_csv.py`, `classify_domain.py`, `phase3_availability.py` | **Old v1-era scripts**, superseded by the pillar-based architecture above. Kept for reference/history only — don't build on these for new work. |

Full runnable-command reference with exact flags: **`COMMANDS.md`**
(includes the `caffeinate` incantation for keeping the laptop awake).

## Known bugs already found and fixed (don't reintroduce)

1. **`pdftohtml` without `-i` silently dumps every embedded image as a
   separate file** — caused a 74,000-file disk-bloat incident. Always keep
   the `-i` flag. Comment is in `detector_v2.py` pointing at this.
2. **PDFs must be deleted immediately after text/link extraction** — 1,400+
   cached PDFs would be ~11-12GB, not worth keeping once text is extracted.
   Already implemented; don't remove.
3. **arXiv IDs can silently lose trailing zeros** if ever round-tripped
   through something that treats them as numbers instead of strings (e.g.
   `2606.13010` → `2606.1301`) — found and fixed 22 corrupted rows in the
   review queue this way. If an arXiv ID ever looks 4-digit instead of the
   normal 5-digit post-2015 format, suspect this and cross-check against
   the URL columns, which don't have the bug.
4. **`Verified` column convention**: `Verified` = has a human checked this
   row (Yes/No), separate from `Corrected Label`/`Data Present` = what the
   actual answer is. Don't conflate them (this got mixed up once and had
   to be fixed retroactively).
5. Detector v2's false-positive pattern: any hyperlink matching a repo
   domain gets flagged as a candidate **even if it's just a citation to a
   third-party tool** (MWrap, QKeras, QICK, OQTO were all real examples) —
   this is intentional per Daniel's "never miss a true positive, false
   positives are fine" requirement, not a bug to fix, but expect ~15-20%
   of link-found candidates to be this pattern during manual review.

## Communication with Daniel (Slack)

- He responds slowly/sporadically (weekend replies, hours between
  messages) — don't assume urgency that isn't stated.
- He prefers being given concrete numbers over vague progress claims.
- He explicitly wants the detection approach to be "never silently mark
  no-data, flag everything ambiguous for human review" — this is the
  design philosophy behind detector_v2's whole Candidate/No-candidate
  split, not just a one-off request.
- Diana is a co-worker on this; splitting review work with her
  (independent overlapping samples for inter-rater reliability) was
  discussed as a good idea but not yet actually coordinated/executed.

## Reference docs in this folder

- `DOMAIN_DEFINITIONS.md` — the 6-pillar quantum/CS structure, arXiv mappings, open questions
- `COMMANDS.md` — exact runnable commands for every script, including `caffeinate` usage
- `PIPELINE.md` — Mermaid diagrams of the original (pre-pillar) pipeline architecture; still accurate for how `detector_v2.py`'s per-paper logic works, just predates the pillar/group system
- `TODO.md` — older open items (query scope refinement, review-article exclusion) from earlier in the project, some now superseded by the pillar system

## Immediate next steps (in likely priority order)

1. Check on / report results from the CS-algorithms background run (see command above).
2. Continue manual verification of the remaining ~177 link-found SC-qubit candidates.
3. Once Daniel gives feedback on the CS-algorithms initial results, decide whether to expand to more CS pillars or start pulling the other 5 quantum pillars.
4. Consider the random-sample validation of the "no-signal" bucket (793 papers) that was discussed but never executed — needed to make a defensible false-negative-rate claim for the eventual paper.
5. Coordinate actual work-splitting with Diana rather than just discussing it.

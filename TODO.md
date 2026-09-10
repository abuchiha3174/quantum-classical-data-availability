# TODO — Scope / query refinement

## Search query needs improvement
Current arXiv/Crossref pull filters on "superconducting qubit(s)" as a keyword only. This pulls in papers that use superconducting qubit *hardware* for non-quantum-computing applications, which are arguably out of scope for a "quantum computing" data-availability review.

Confirmed off-domain examples found during manual vetting so far (tagged in the CSV `Notes` column, searchable):
- `[NOT SUPERCONDUCTING DOMAIN]` — arXiv:2608.07185, "Kramers-Henneberger atom Qubit" — atomic/strong-field physics, not superconducting hardware at all. Likely a false-positive keyword match on "qubit."
- `[NOT QUANTUM COMPUTING DOMAIN]` — arXiv:2608.02733, "High-Frequency Gravitational Wave Detection with Superconducting Qubits" — real superconducting transmon hardware, but used as a quantum sensor (arXiv category hep-ph), not for computation.

## Ideas for next pass
- Use arXiv primary category as a filter (keep quant-ph / cond-mat.supr-con / cond-mat.mes-hall; flag or exclude hep-ph, astro-ph, gr-qc, physics.ins-det hits even if they match the keyword).
- Consider a secondary keyword screen for computing-specific terms (gate, processor, error correction, algorithm, circuit) vs. sensing-specific terms (detection, sensor, interferometry, haloscope) to auto-triage borderline cases.
- Keep doing spot-checks like the ones so far — they're a useful sanity check on whatever the improved filter produces.

## detector_v2 false-positive pattern: citation-list links mistaken for own data/code
Confirmed recurring case (arXiv:2607.26242 is the latest example, others found earlier:
QKeras/QICK in 2607.14293, OQTO in 2607.16151): the detector flags ANY hyperlink whose
domain matches a repo host (github.com, zenodo.org, etc.), with no check for whether the
link sits inside a numbered reference-list entry citing a third-party tool vs. an actual
"Data/Code availability" statement about the paper's own work.

This is intentional for now (recall over precision, per advisor's requirement -- false
positives get cleared by human review, false negatives are the thing to avoid). But worth
a smarter v3 pass eventually:
  - Locate the link's surrounding text and check if it's inside a numbered reference entry
    (pattern like "[36] Author, Title, ... (year)") vs. near "data availability"/"code
    availability" heading text -- reference-list hits should be down-weighted or tagged
    separately from availability-section hits, not eliminated (still worth surfacing,
    just distinguishable so a reviewer can triage faster).
  - Could also just tag each candidate_link with WHICH detection path found it (repo-domain
    href scan vs DOI regex vs keyword-adjacent) so the review queue can be sorted by
    confidence instead of all candidates looking equally weighted.

## Status
Not urgent — continuing manual vetting with current list in the meantime. Revisit when doing a full second-pass query rebuild.

## Remove unused Phase 3 code -- CORRECTED 2026-08-29, detector_v2.py is NOT dead
Original note (2026-08-28) said all three Phase 3 scripts had no output files and
could be deleted. That was wrong for one of them: `detector_v2.py` writes to
`cache/analysis_cache_{group}.jsonl`, a filename that doesn't contain "availability"
or "v2" -- the original filename-based check for `*availability*`/`*v2*` missed it
entirely. `cache/analysis_cache_quantum.jsonl` (3,478 records) is real, active output:
it's the full-text keyword/link scan and domain-pillar classification that
`axis_case_classifier.py` reads `candidate_links` from, and that every batch's
`link_results` ultimately trace back to. Confirmed in active use while diagnosing the
batch_007 over-flagging issue (2026-08-28/29) -- do not delete `detector_v2.py`.

Still genuinely dead, safe to delete once confirmed nothing else references them:
- `scripts/phase3_availability.py` -- the older detector `detector_v2.py` replaced
- `scripts/build_v2_comparison.py` -- only existed to diff v1 vs v2 output during
  that migration; no current consumer

Before deleting either: grep the rest of `scripts/` for imports/calls into them first.

Status: partially actioned -- detector_v2.py removed from scope; the other two still
deferred, not blocking batch work.

## Rework keyword lists in domain_definitions.py -- both quantum AND cs, not just cs
Found 2026-08-29 while pulling the full-breadth CS corpus: `build_pillar_paper_list.py`
was capped at 100 results per keyword and got fixed (now paginates to the true total,
see the pagination fix already landed in `build_pillar_paper_list.py`) -- but fixing the
cap exposed a deeper, separate problem the cap was masking.

CS's "algorithms" pillar keyword `"machine learning algorithm"` (exact-phrase match)
returns only 2,117 true matches, when the real ML literature on arXiv (`cs.LG` alone) is
100,000+ papers since 2021. The gap isn't the cap -- it's that almost no ML paper
actually writes the literal phrase "machine learning algorithm" in its title/abstract;
they say "we propose a transformer for...", "a reinforcement learning approach to...",
etc. Generic 2-4 word descriptive phrases massively undercount a field as
terminologically fragmented as classical CS/ML, no matter how much pagination is added.

Quantum's keyword list mostly avoids this because its terms are canonical proper nouns
("Shor's algorithm", "Grover's algorithm", "QAOA") that virtually every relevant paper
names explicitly -- quantum computing has a small, concentrated vocabulary. But quantum's
list should still be reviewed for the same failure mode, not assumed clean just because
it happens to work better right now -- some quantum pillars (e.g. `info_theory`,
`control`) may have the same generic-phrase problem to a lesser degree.

Options to fix, not yet decided:
- Pull by arXiv category alone (no keyword filter) + classify content afterward, for
  pillars where this problem is worst (especially CS `algorithms`).
- Or substantially lengthen/sharpen the keyword lists per pillar to cover real
  named methods/architectures/techniques instead of generic descriptive phrases.

Do this for BOTH quantum and cs together, not CS in isolation -- user's explicit
instruction (2026-08-29): rework one side, rework both, so the comparison stays fair.

Status: deferred, not blocking current batch/pipeline work. Decide the fix approach
before re-pulling either corpus again.

## Unify Hardware-pillar corpus construction with the common per-pillar procedure
Found 2026-08-29 while reviewing `data_availability_report.tex`: the quantum-side
Hardware pillar is built by a separate, older two-source procedure (arXiv +
Crossref cross-referencing against 7 target journals, `phase1_arxiv.py` era) instead
of the common per-pillar arXiv query procedure (`build_pillar_paper_list.py`) every
other pillar on both sides uses -- including CS's own Hardware pillar, which has no
reused dataset and already goes through the common procedure. This is a leftover
inconsistency from before the six-pillar comparison architecture existed, not a
deliberate design choice.

Decided fix (user, 2026-08-29): extend the more rigorous two-source method (arXiv +
Crossref) to every pillar on both sides, rather than dropping it in favor of the
weaker arXiv-only method for consistency. Concretely:
- Add a Crossref cross-referencing step to `build_pillar_paper_list.py`, using each
  pillar's own keyword list and an appropriately chosen set of target journals per
  pillar (the current 7-journal list was chosen for superconducting-qubit hardware
  specifically and won't fit every pillar as-is).
- Apply this to ALL pillars on both sides, including ones with completed
  classification work already (quantum Hardware specifically, and any other
  already-classified pillar) -- do not skip already-classified pillars.
- Purely additive: dedupe any newly-found papers against the existing corpus (by
  arXiv id; by fuzzy title match for journal-only records with no arXiv id, same
  procedure as the original superconducting-qubit merge) and add only the new ones.
  Never remove a paper or discard a classification already completed.

This is documented as a formal "Planned Extensions" section in
`data_availability_report.tex` (Section~\ref{sec:planned-hardware-unification}) --
that section is meant to keep growing as more such directions get identified while
reviewing the report against the actual pipeline; check there for the current list
before starting on any one item.

Status: decided, not yet implemented. Needs: (1) per-pillar journal-target lists for
Crossref queries (12 pillars total, currently only defined for quantum hardware), (2)
the dedup-and-append logic in build_pillar_paper_list.py, (3) a re-run for every
pillar on both sides once (1) and (2) are in place.

## Quantum computing vs. quantum physics scope -- resolved via domain classification, not query filtering
Found 2026-08-29 while estimating post-rework corpus size: several quantum keywords
("quantum entanglement", "quantum communication", "quantum measurement theory",
"quantum cryptography") are used as heavily in non-computing quantum physics --
sensing, foundations, optics, networking -- as in quantum computing. Pulling more
aggressively (pagination fix + keyword rework, both landed) means pulling in more of
this off-topic-for-computing material too, same pattern already documented for the
original hardware pillar in the "Search query needs improvement" TODO item above and
in classify_domain.py's exclusion list (Atomic Physics, Quantum Sensing, Quantum
Magnonics, Quantum Optomechanics, etc.).

Decided fix (user, 2026-08-29): do NOT narrow the corpus-pull query to fix this --
user explicitly wants maximum paper volume. Instead, resolve it at the
domain-classification stage (Section 2.6 of data_availability_report.tex): the
domain classifier's judgment space includes an explicit out-of-scope outcome, reusing
classify_domain.py's existing non-computing category set (Atomic Physics, Quantum
Sensing, Quantum Magnonics, Quantum Optomechanics, Photonic Quantum Computing,
Trapped-Ion Computing, Neutral-Atom Computing, Semiconductor Spin Qubits, High Energy
Physics) plus a general "Not Quantum Computing" fallback. A paper classified this way
stays in the corpus (for auditable candidate-generation yield) but is excluded from
every quantum-computing-specific statistic downstream.

This is documented in data_availability_report.tex, Section~\ref{sec:domain-classification}.
Whether CS needs an analogous out-of-scope category (e.g. "channel capacity" and
"information theoretic limit" also being generic math/comms terms with no computing
connection) is a separate, not-yet-assessed open question -- see
Section~\ref{sec:planned-cs-out-of-scope} in the same document.

Status: decided and documented for quantum; CS side not yet assessed. No
implementation yet on either side (domain classification itself hasn't been executed
at all per the earlier TODO item on this page).

## Link content verification -- Layer 1 (implemented) + Layer 2 (implemented, off by default)
Found 2026-08-29: a resolved link (HTTP 200) only proves the URL is reachable, not
that real data is actually attached -- an empty GitHub repo or a Zenodo record with
metadata but no files both resolve fine, and the scaled batch classification (unlike
the original 14-paper hand-reviewed pilot) has no way to tell the difference, since it
only ever sees precomputed link_results text, never the actual page content.

**Layer 1 (deterministic, free, DONE)**: `scripts/axis_case_classifier.py` now calls
`check_repo_content()` automatically after every successful link resolve. For GitHub
and Zenodo links (the two most common candidate-link domains), it queries that
platform's own public API for real file-level metadata (`repo_size_kb`/`repo_is_empty`
for GitHub, `file_count`/`total_size_bytes`/`is_empty` for Zenodo) and adds it to
`link_results`. No LLM cost -- same scripted-check cost profile as the existing
HTTP-resolve check. Figshare and OSF have similar public APIs but different
id-extraction rules and are not yet wired in (`check_repo_content()`'s docstring notes
this as the natural next platform to add).

**Layer 2 (agent-driven, real LLM cost, DONE, default OFF)**: a new `--agent-fetch`
CLI flag on `axis_case_classifier.py` stamps `agent_fetch_enabled` (true/false) onto
every record processed that run. When true, the classification prompt for that record
should instruct the agent to independently fetch and inspect a paper's own claimed
link (using its own fetch tool) rather than trusting `link_results` alone -- for
platforms Layer 1 doesn't cover, or genuinely ambiguous cases. This is a real
per-paper LLM cost, unlike Layer 1, which is why it defaults to off; user's explicit
instruction (2026-08-29): keep it as an opt-in mode, not always-on.

Not yet done: the classification PROMPT template (the instructions handed to a batch
classification agent) doesn't yet branch on `agent_fetch_enabled` -- the flag is
stamped onto records correctly, but no prompt currently reads or acts on it. Needs a
conditional instruction block added to the batch classification prompt before Layer 2
actually changes agent behavior on a real run.

Status: Layer 1 code done and active on every future `axis_case_classifier.py` run.
Layer 2 flag/plumbing done; prompt-side wiring still needed before it does anything.

# Data Availability Classification Framework

Two-axis, six-case framework used by `scripts/axis_case_classifier.py` to
label individual papers, beyond the binary Candidate/No-candidate triage
`detector_v2.py` already does. The literal text below is duplicated as
`FRAMEWORK_TEXT` in `axis_case_classifier.py` (used directly in the LLM
prompt) -- edit both places together if this changes.

## Axes

**Axis A — External Data.** Whether the paper draws on data that already
existed independently of the paper — a pre-collected dataset, real-world
records, an established benchmark, existing designs or artifacts — and
performs its analysis on that.

**Axis B — Self-Generated Data.** Whether the paper produces its own data by
running an experiment, simulation, or generative procedure — random
instance generation, physics-based simulation, hardware simulation,
training-run outputs, etc. — and performs its analysis on that.

A paper is scored independently on each axis; it may use both, either, or
neither. A paper is theoretical (no empirical component) only when **both**
axes independently return Case 1.

## Cases (applied identically to both axes)

**Case 1 — Not present.** This axis does not apply to the paper. For Axis
A: no external data was used at all. For Axis B: no self-generated data was
produced at all.

**Case 2 — Present and directly accessible.** The data is named and
accompanied by a working access path (URL, DOI, or repository) that lets an
independent party retrieve the identical material. Ideally version- or
commit-pinned.

**Case 3 — Present but not handed over.** The data is named, described, or
cited, but no access path is given. An independent party must locate it
themselves using only the name or description provided.

**Case 4 — Present but underspecified.** The data is acknowledged to exist
but described too vaguely or incompletely to independently identify or
reconstruct it — e.g., missing dataset name/version (Axis A), or missing
generation parameters/methodology (Axis B).

**Case 5 — Claimed accessible but unverifiable.** The paper explicitly
states the data is available and gives a specific access path, but that
path does not resolve. Distinct from Case 3 (no claim of access is made) in
that access was affirmatively promised and failed to hold.

**Case 6 — Conditionally accessible on request.** The paper states the data
will be provided if the authors are contacted directly, without any
immediate, self-service access path. Distinct from Case 3 (no offer at all)
and Case 5 (no claim of present availability, only a conditional future
one).

## Boundary notes (things that have caused confusion in manual review)

- **Case 1 on one axis does not mean the paper is theoretical.** It only
  means that axis's type of data wasn't used. A paper can be Axis A = Case 3
  / Axis B = Case 1 and still be a fully empirical paper — it just never
  generated its own data.
- **Case 3 vs. Case 4**: "we used 5,000 samples" (no dataset name at all) is
  Case 4 (underspecified). "We used the XYZ dataset" (named, no link) is
  Case 3 (present, not handed over). The presence of a name/identifier is
  the dividing line, not the presence of a link.
- **Case 5 requires an affirmative, checked-and-failed claim** — a paper
  that never claims availability at all and simply has no link is Case 3,
  not Case 5. Only mark Case 5 once the specific stated URL/DOI has been
  independently verified to fail.
- **A paper can, and often does, land on both axes simultaneously** (e.g.,
  trains on a real external dataset *and* separately validates against its
  own simulated data) — score each axis independently; do not force a
  single overall label for the paper.

## Scope caveat for automated runs

`detector_v2.py`'s Candidate/No-candidate split is a narrower question
("does this paper contain an availability keyword or repo-domain link?")
than Axis A ("does this paper use external data at all?"). A paper can
clearly trigger Axis A (e.g., "we evaluate on CIFAR-10 and ImageNet") with
zero availability language and zero link, landing in detector_v2's
"No candidate" bucket. Running `axis_case_classifier.py --scope candidates`
only covers the higher-yield "Candidate" subset; `--scope all` is required
for a classification that doesn't have this gap, at proportionally higher
LLM-call cost.

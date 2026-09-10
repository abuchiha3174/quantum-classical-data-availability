# Known Pipeline Gaps

Issues found during manual Stage 4 classification that reflect real limitations in the
automated Stage 2/3 scanning, collected here rather than left scattered across individual
paper records' `notes` fields. Each entry names the affected paper(s) so the classification
can be revisited once the underlying gap is fixed. None of these have been fixed yet except
where noted -- fixing them does not retroactively rescan papers already processed by
Stage 2/3; a fix only takes effect on a future Stage 2 re-run.

## 1. `REPO_DOMAINS` (in `detector_v2.py`) is missing several real data/code-hosting domains

Papers whose explicit data/code-availability statement gives a URL on a domain not in
`REPO_DOMAINS` get `link_results = []` even though a real, specific access path is stated
in the text -- the statement is only visible by reading the paper text itself, not from
the automated link extraction.

Confirmed missing domains found so far:

| Domain | Found in | Status |
|---|---|---|
| `modelscope.cn` | 2607.12996 ("data and code... openly available at modelscope.cn/datasets/...") | **Fixed** -- added to `REPO_DOMAINS` in `detector_v2.py`. |
| `onrender.com` | 2606.27384 ("Full corpus accessible at https://c2qa-materials-explorer.onrender.com") | **Fixed** -- added to `REPO_DOMAINS` in `detector_v2.py`. |

**Neither fix is retroactive**: the full quantum corpus was already scanned before these
fixes, so `2607.12996` and `2606.27384` still have stale `link_results` in the shared cache.
**Action needed**: re-run Stage 2 for just these two paper IDs (`detector_v2.py ... 2607.12996
2606.27384`, using the `ids` positional argument), then re-run Stage 4 classification for
those two papers only. No need to re-scan the other ~3,470 papers.

## 2. Institutional-repository DOIs (e.g. 4TU-style `10.4121/...`) not always resolving to a captured link

At least one paper's own data-availability reference is a `doi.org/10.4121/...` DOI
(4TU.ResearchData, a Dutch institutional repository) that was not captured in
`candidate_links` / `link_results`, unlike Zenodo DOIs (`10.5281/zenodo...`), which are
reliably captured and verified elsewhere in this same batch.

Confirmed example: 2606.17866 -- data availability statement cites Ref [50], a
`doi.org/10.4121/...` DOI, which was never live-verified; only the paper's separate GitHub
code link was captured and verified.

**Fixed** -- `detector_v2.py`'s `is_repo_like()` now also checks a `KNOWN_DOI_PREFIXES` list
(currently: Zenodo `10.5281`, figshare `10.6084`, Dryad `10.5061`, 4TU.ResearchData `10.4121`,
OSF `10.17605`, Harvard Dataverse `10.7910`) against bare DOI citations, not just resolved
domain names. Verified against the 4TU example above and confirmed no false positive on an
unrelated Physical Review Letters DOI. **Not retroactive** -- same action needed as gap 1:
re-run Stage 2 for `2606.17866` specifically, then re-run its Stage 4 classification.

## 3. Transient network failures on link verification (Stage 3) can look like a broken link if not retried

Example: 2608.07106's Zenodo DOI returned a timeout on one Stage 3 run despite being
independently confirmed live (both earlier in manual review, and by this same
`axis_case_classifier.py` script on a different run).

**Fixed** -- `verify_link()` now retries up to twice (3s apart) before giving up, but only
for network-level failures (timeout, connection reset, DNS hiccup). A definitive HTTP error
(404, 403, etc.) is never retried, since that's a real answer rather than a transient one.
This fix applies automatically to any future Stage 3 run; papers already checked under the
old single-attempt behavior are not automatically rechecked.

## 4. Link rot / inconsistent results between separate review passes on the same paper

Example: 2604.09796 was classified as Axis B Case 2 ("openly available at a working Zenodo
DOI") in the earlier hand-reviewed 14-paper quantum pilot sample. Independently re-verifying
the exact same cited DOI (10.5281/zenodo.19303492) during this later Stage 4 batch pass found
it now returns HTTP 404. This may be genuine link rot (the record was taken down or
renumbered between passes) rather than an error in either review -- but it means a paper's
case assignment is not necessarily stable over time, and a case built on a live-link check
should record the check's date so a later discrepancy like this one is legible as "changed"
rather than "wrong." Recommend a human re-check on this specific paper before finalizing its
case, and consider whether `verify_link()` should log a timestamp per check for exactly this
reason.

## How to use this file going forward

When Stage 4 classification (manual or agent-driven) notices a paper whose text contains an
explicit, specific access statement that isn't reflected in `link_results`, add a row/entry
here (paper ID, domain or DOI pattern involved, one-line description) instead of only noting
it in that paper's own classification record. Revisit this file before or during any future
Stage 2 re-run to decide which fixes are worth making first.

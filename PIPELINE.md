# How this pipeline works

This document explains the scripts in `scripts/` and how data flows between
them. Diagrams are in Mermaid — they render natively on GitHub, in VS Code's
markdown preview, and in most modern markdown viewers.

## 1. Big picture

```mermaid
flowchart TD
    A[arXiv API] -->|query: "superconducting qubit(s)"<br>2021-01-01 to present| B(phase1_arxiv.py)
    C[Crossref API] -->|query: superconducting qubit<br>7 target journals| D(phase2_crossref.py)
    B --> E[cache/arxiv_papers.jsonl<br>1379 papers]
    D --> F[cache/crossref_papers.jsonl<br>1887 raw hits]
    E --> G(merge.py<br>fuzzy title dedupe)
    F --> G
    G --> H[cache/merged_papers.jsonl<br>1478 papers]
    H --> I(build_csv.py)
    I --> J[data/superconducting_qubits_papers.csv<br>the master list]

    H --> K(detector_v1 / phase3_availability.py<br>ar5iv HTML text scan only)
    K -.->|first-pass auto-flag<br>known false pos/neg issues| J

    H --> L(detector_v2.py<br>PDF-native, high-recall)
    L -->|candidate flags + evidence| M[cache/detector_v2_results.jsonl]
    M --> N[merged into CSV v2<br>for comparison against v1]

    J --> O[Manual verification<br>one paper at a time]
    N --> O
    O -->|Verified = Yes| J
```

## 2. Why there are two detectors

| | v1 (`phase3_availability.py`) | v2 (`detector_v2.py`) |
|---|---|---|
| Source text | ar5iv HTML rendering | Full PDF text (`pdftotext`) + PDF hyperlink annotations (`pdftohtml -xml`) |
| Output | Confident label: Yes / No / Statement-only | Binary: **Candidate** (any signal) / **No candidate** |
| Design goal | Fully automated classification | Screening tool for a human to review — advisor's explicit requirement: **zero false negatives are acceptable losses, false positives are not** |
| Known issues found by manual spot-checking | Missed PDF-annotation-only links (false negative), missed line-wrapped URLs (false negative), mistook citation links to third-party tools for the paper's own repo (false positive) | Built specifically to fix the two false-negative classes above; false positives are expected and left for human review |

v1 is kept as the historical "before" snapshot. v2 is the active detector.
The point of running both over the same paper list is to produce a
before/after diff — concretely showing how many papers the improved script
catches that the first version missed.

## 3. What `detector_v2.py` does, per paper

```mermaid
flowchart TD
    A[arXiv ID from<br>cache/merged_papers.jsonl] --> B{Already in<br>results.jsonl?}
    B -->|yes| Z[Skip - already done]
    B -->|no| C[Download PDF<br>from arxiv.org/pdf]
    C --> D[pdftotext:<br>extract plain text]
    C --> E[pdftohtml -xml:<br>extract hyperlink hrefs]
    D --> F[Delete the PDF<br>text/links already captured]
    E --> F
    F --> G[Flatten text:<br>rejoin line-wrapped URLs<br>and de-hyphenate]
    G --> H[Scan for repo-domain<br>hyperlinks: GitHub, Zenodo,<br>Figshare, OSF, Dryad, etc.]
    G --> I[Scan flattened body text<br>for DOI patterns and<br>plain-text URLs matching<br>repo domains]
    G --> J[Scan for ~30 keyword phrases:<br>"data availab-", "code availab-",<br>"upon request", "deposited at", etc.]
    H --> K{Any hit at all?}
    I --> K
    J --> K
    K -->|yes| L[Status: Candidate -<br>needs human check]
    K -->|no| M[Status: No candidate<br>signal found]
    L --> N[Append record to<br>cache/detector_v2_results.jsonl]
    M --> N
```

**Why the PDF gets deleted immediately:** keeping ~1,400 PDFs (avg ~8.5MB
each) would use ~11-12GB of disk, most of which was already tight on this
machine. The extracted text and links are all the pipeline actually needs
going forward, so the PDF itself is disposable once that's captured.

**Why it's resumable:** every processed paper is appended to
`cache/detector_v2_results.jsonl` as soon as it's done. If the script is
stopped and restarted, it re-reads that file first and skips anything
already in it — so a restart never redoes work or loses progress.

## 4. The human-in-the-loop step

Neither detector's output is the final answer for any paper. Both v1 and v2
labels are inputs to manual verification: opening the actual paper, reading
the availability statement (if any) in context, and setting `Verified =
Yes` in the CSV once confirmed. The `Notes` column records what was found
and why, including any correction made to the automated label.

This matters because both detectors have asymmetric failure modes:
- v1 was found to have both false positives and false negatives.
- v2 is deliberately tuned to only have false positives (over-flagging) --
  every "Candidate" still needs a human to confirm it's real, but a "No
  candidate" is meant to be trustworthy without further checking (though
  spot-checking a random sample of that bucket is still recommended before
  relying on it in the paper itself).

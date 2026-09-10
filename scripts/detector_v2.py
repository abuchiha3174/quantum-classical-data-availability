"""
High-recall data/code availability detector (v2), now also doing
domain-pillar classification on the same extracted text.

Design goal (per advisor requirement): NEVER silently classify a paper as
having no data if there's any plausible signal. Cast a wide net -> every
paper with any signal becomes a "Candidate" for human review. Only papers
with zero signal across all patterns land in "No candidate found". False
positives are acceptable and expected (a human clears them); false
negatives are not.

Fixes vs the v1 ar5iv-based scanner:
  1. Reads full PDF text + PDF hyperlink annotations (pdftohtml -xml),
     not just ar5iv HTML rendering, which drops link annotations and
     sometimes fails to render very recent papers at all.
  2. Flattens line-wrapped text before regex matching, so a URL/DOI split
     across a PDF line break (e.g. "https:\n//doi.org/...") isn't missed.
  3. Much broader keyword phrase list and repository-domain list, plus
     generic DOI/URL pattern scanning independent of nearby keywords.
  4. Output is Candidate / No-candidate, not a confident Yes/No/Statement
     label -- labeling happens after human review.

New in this version:
  5. Domain-pillar classification: the same full text already downloaded
     for the data-availability scan is also checked against every pillar's
     keyword list (domain_definitions.py), so a paper that was pulled under
     one pillar's search but whose actual content doesn't support that
     pillar gets flagged for a human to double-check -- no second download.
  6. A persistent per-paper cache (keyed by arxiv_id) replaces the old
     pure-append results file, so re-runs after editing
     domain_definitions.py don't redo already-processed papers.
  7. Every invocation writes a fresh, auto-incrementing snapshot file
     (e.g. data/quantum_availability_run3.jsonl) capturing the full
     current result set, so successive runs can be diffed against each
     other instead of silently overwriting history.
  8. Still deletes each PDF immediately after its text/links are
     extracted, and pdftohtml is still run with -i (no image extraction)
     -- both fixes carried over unchanged from the disk-bloat incident
     earlier in this project. Text is the only thing this script cares
     about; nothing here processes images.
"""
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_definitions import GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
DATA_DIR = ROOT / "data"
PDF_DIR = CACHE / "pdfs"
TXT_DIR = CACHE / "pdftext"
MERGED_PATH = CACHE / "merged_papers.jsonl"  # original superconducting-qubit-only list

UA = "Mozilla/5.0 (research; systematic-review-tool; contact:as3485@rit.edu)"

KEYWORD_PHRASES = [
    "data availab", "code availab", "materials availab", "software availab",
    "data underlying", "supporting data", "source data", "reproducibility package",
    "supplementary data", "supplementary dataset", "supplementary information",
    "openly available", "publicly available", "publicly accessible",
    "deposited at", "deposited in", "available upon", "available on reasonable",
    "available at http", "available from http", "available via http",
    "dataset is available", "datasets are available", "code is available",
    "code used in this", "released at", "hosted at", "archived at",
    "data and code", "code and data", "raw data are available",
    "raw data is available", "underlying data", "accompanying dataset",
    "data repository", "code repository", "github repository",
]

REPO_DOMAINS = [
    "github.com", "github.io", "gitlab.com", "bitbucket.org",
    "zenodo.org", "figshare.com", "osf.io", "dataverse.harvard.edu",
    "datadryad.org", "dryad.org", "data.4tu.nl", "materialscloud.org",
    "nomad-lab.eu", "huggingface.co", "kaggle.com", "data.gov",
    "springernature.figshare.com", "physionet.org", "data.mendeley.com",
    "dataone.org", "researchdata", "data.caltech.edu", "data.stanford.edu",
    # Added after a manual Stage 4 pass on the quantum corpus found a paper
    # (2607.12996) whose explicit "data and code are openly available at
    # modelscope.cn/datasets/..." statement was missed entirely by the
    # candidate scan, because modelscope.cn wasn't recognized as a
    # repo-like domain -- this addition is NOT retroactive: papers already
    # scanned by Stage 2 before this fix (the full quantum corpus, as of
    # this writing) keep whatever candidate_links they were already given
    # and won't pick up modelscope.cn links unless Stage 2 is re-run.
    "modelscope.cn",
    # Added for the same reason: paper 2606.27384 cited "Full corpus
    # accessible at https://c2qa-materials-explorer.onrender.com" and this
    # was never captured either. See PIPELINE_GAPS.md.
    "onrender.com",
]

# Known institutional/repository DOI prefixes, checked independently of
# REPO_DOMAINS below. A citation often gives a bare "10.xxxx/..." DOI
# without ever writing out the resolving domain name (e.g. a paper citing
# "10.4121/22122209-..." for a 4TU.ResearchData deposit never writes
# "data.4tu.nl" anywhere in the visible text), so domain-name matching
# alone misses these. Found via a Stage 4 pass on paper 2606.17866, whose
# own data DOI (10.4121/...) was never verified because of this gap --
# see PIPELINE_GAPS.md. Extend this list as new institutional repositories
# turn up; 10.5281 (Zenodo), 10.6084 (figshare), 10.5061 (Dryad) are
# already covered by the plain substring checks in is_repo_like() below
# and are listed here too only for documentation completeness.
KNOWN_DOI_PREFIXES = [
    "10.5281",   # Zenodo
    "10.6084",   # figshare
    "10.5061",   # Dryad
    "10.4121",   # 4TU.ResearchData
    "10.17605",  # OSF
    "10.7910",   # Harvard Dataverse
]

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>\)\]]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s\"'<>\)\]]+", re.IGNORECASE)


def strip_trailing_punct(s: str) -> str:
    return s.rstrip(".,;:)")


def flatten(text: str) -> str:
    text = re.sub(r"-\n", "", text)
    text = re.sub(r"(https?:)\s*\n\s*(//)", r"\1\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(/)\n(?=\S)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text


def download_pdf(arxiv_id: str) -> Path | None:
    dest = PDF_DIR / f"{arxiv_id}.pdf"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    url = f"https://arxiv.org/pdf/{arxiv_id}v1"
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 1000:
            return None
        dest.write_bytes(data)
        return dest
    except Exception:
        return None


def extract_text(pdf_path: Path) -> str:
    txt_path = TXT_DIR / (pdf_path.stem + ".txt")
    if txt_path.exists():
        return txt_path.read_text(errors="ignore")
    try:
        out = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True, timeout=60, text=True,
        )
        text = out.stdout
        txt_path.write_text(text)
        return text
    except Exception:
        return ""


def extract_links(pdf_path: Path) -> list[str]:
    try:
        # -i = ignore images. Without this flag, pdftohtml silently dumps
        # every embedded image as a separate file next to the PDF -- that
        # caused a 74,000-file disk-bloat incident earlier in this project.
        # Text is all this pipeline needs; never remove -i.
        out = subprocess.run(
            ["pdftohtml", "-i", "-xml", "-stdout", str(pdf_path)],
            capture_output=True, timeout=60, text=True,
            cwd=str(PDF_DIR),
        )
        return re.findall(r'href="([^"]*)"', out.stdout)
    except Exception:
        return []


def find_snippet(flat_text: str, idx: int, span: int = 90) -> str:
    start = max(0, idx - span)
    end = min(len(flat_text), idx + span)
    return flat_text[start:end].strip()


def classify_pillars(flat_lower: str, group: str | None) -> dict:
    """Check the paper's own full text against every pillar's keyword list
    in the given group. Reuses text already extracted for the data-
    availability scan -- no extra download. Returns which pillars the
    content actually supports, separate from which pillar(s) it was
    *searched* under (that comes from the paper-list file itself)."""
    if group is None or group not in GROUPS:
        return {"content_pillars": [], "content_pillar_hits": {}}

    content_pillars = []
    hits_by_pillar = {}
    for pillar in GROUPS[group]:
        matched = [kw for kw in pillar["keywords"] if kw.lower() in flat_lower]
        if matched:
            content_pillars.append(pillar["id"])
            hits_by_pillar[pillar["id"]] = matched
    return {"content_pillars": content_pillars, "content_pillar_hits": hits_by_pillar}


def analyze(arxiv_id: str, searched_pillars: list[str], group: str | None) -> dict:
    pdf_path = download_pdf(arxiv_id)
    if pdf_path is None:
        return {
            "arxiv_id": arxiv_id,
            "status": "Unclear - could not fetch PDF",
            "candidate_links": [],
            "keyword_hits": [],
            "searched_pillars": searched_pillars,
            "content_pillars": [],
            "content_pillar_hits": {},
        }

    raw_text = extract_text(pdf_path)
    flat = flatten(raw_text)
    flat_lower = flat.lower()

    def is_repo_like(s: str) -> bool:
        s = s.lower()
        if any(dom in s for dom in REPO_DOMAINS):
            return True
        if any(tok in s for tok in ("zenodo", "figshare", "dryad", "dataverse")):
            return True
        # Bare DOI citations (e.g. "10.4121/22122209-...") never mention a
        # resolving domain name at all, so the checks above miss them --
        # match on the DOI prefix itself instead. See KNOWN_DOI_PREFIXES.
        return any(s.startswith(p.lower()) or f"doi.org/{p.lower()}" in s or f"/{p.lower()}" in s
                   for p in KNOWN_DOI_PREFIXES)

    hrefs = extract_links(pdf_path)

    # Delete the PDF now that its text + links are extracted and cached --
    # keeping ~1400 PDFs (avg ~8.5MB each, ~11-12GB total) isn't worth the
    # disk space when the extracted text/links are all we actually need.
    try:
        pdf_path.unlink()
    except OSError:
        pass

    candidate_links = set(
        strip_trailing_punct(h) for h in hrefs if is_repo_like(h)
    )
    for m in DOI_RE.findall(flat):
        if is_repo_like(m):
            candidate_links.add(strip_trailing_punct(m))
    for m in URL_RE.findall(flat):
        if is_repo_like(m):
            candidate_links.add(strip_trailing_punct(m))
    candidate_links = sorted(candidate_links)

    keyword_hits = []
    for phrase in KEYWORD_PHRASES:
        for m in re.finditer(re.escape(phrase), flat_lower):
            keyword_hits.append({
                "phrase": phrase,
                "snippet": find_snippet(flat, m.start()),
            })
    seen_snips = set()
    deduped_hits = []
    for h in keyword_hits:
        key = (h["phrase"], h["snippet"][:40])
        if key not in seen_snips:
            seen_snips.add(key)
            deduped_hits.append(h)

    status = "Candidate - needs human check" if (candidate_links or deduped_hits) else "No candidate signal found"

    pillar_info = classify_pillars(flat_lower, group)

    return {
        "arxiv_id": arxiv_id,
        "status": status,
        "candidate_links": candidate_links,
        "keyword_hits": deduped_hits[:15],
        "detection_method": "full PDF text + hyperlink annotation scan (v2)",
        "searched_pillars": searched_pillars,
        "content_pillars": pillar_info["content_pillars"],
        "content_pillar_hits": pillar_info["content_pillar_hits"],
    }


def cache_path_for(group: str | None) -> Path:
    name = f"analysis_cache_{group}.jsonl" if group else "detector_v2_results.jsonl"
    return CACHE / name


def load_cache(group: str | None) -> dict:
    """Persistent per-paper cache keyed by arxiv_id, so re-runs (e.g. after
    editing domain_definitions.py) skip papers already analyzed instead of
    re-downloading and re-scanning them."""
    path = cache_path_for(group)
    cache = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                try:
                    d = json.loads(line)
                    cache[d["arxiv_id"]] = d
                except Exception:
                    pass
    return cache


def save_cache(group: str | None, cache: dict):
    path = cache_path_for(group)
    with open(path, "w") as f:
        for d in cache.values():
            f.write(json.dumps(d) + "\n")


def next_run_path(group: str | None) -> Path:
    prefix = group if group else "superconducting_qubits"
    n = 1
    while (DATA_DIR / f"{prefix}_availability_run{n}.jsonl").exists():
        n += 1
    return DATA_DIR / f"{prefix}_availability_run{n}.jsonl"


def load_paper_list(input_path: Path) -> list[dict]:
    papers = []
    with open(input_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("arxiv_id"):
                papers.append(d)
    return papers


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=list(GROUPS), default=None,
                         help="Which pillar group this input belongs to (enables domain-pillar classification). "
                              "Omit for the original superconducting-qubit-only run.")
    parser.add_argument("--input", type=str, default=None,
                         help="Path to a paper-list JSONL (e.g. from build_pillar_paper_list.py). "
                              "Defaults to the original merged superconducting-qubit list.")
    parser.add_argument("ids", nargs="*", help="Optional: only process these specific arXiv IDs")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else MERGED_PATH
    papers = load_paper_list(input_path)

    if args.ids:
        papers = [p for p in papers if p["arxiv_id"] in args.ids]

    cache = load_cache(args.group)
    todo = [p for p in papers if p["arxiv_id"] not in cache]

    print(f"input: {input_path}")
    print(f"group: {args.group or '(none -- original superconducting-qubit run)'}")
    print(f"total papers: {len(papers)}, already cached: {len(papers) - len(todo)}, todo: {len(todo)}")

    for i, p in enumerate(todo):
        aid = p["arxiv_id"]
        searched_pillars = p.get("pillars", [])
        result = analyze(aid, searched_pillars, args.group)
        cache[aid] = result
        if (i + 1) % 10 == 0:
            save_cache(args.group, cache)  # periodic checkpoint
        if (i + 1) % 25 == 0:
            print(f"processed {i+1}/{len(todo)} (last: {aid} -> {result['status']})")
        time.sleep(0.5)

    save_cache(args.group, cache)

    # Every invocation writes a fresh, run-numbered snapshot of the FULL
    # current result set (not just this run's new papers), so successive
    # runs after a domain_definitions.py edit can be diffed against each
    # other rather than overwriting history.
    snapshot_papers = {p["arxiv_id"] for p in papers}
    snapshot = [cache[aid] for aid in cache if aid in snapshot_papers]
    out_path = next_run_path(args.group)
    with open(out_path, "w") as f:
        for r in snapshot:
            f.write(json.dumps(r) + "\n")

    print(f"\nwrote {len(snapshot)} results to {out_path}")
    print("done.")


if __name__ == "__main__":
    main()

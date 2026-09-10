"""
Axis/Case data-availability classifier.

Applies the two-axis, six-case framework (see DATA_AVAILABILITY_FRAMEWORK.md)
to individual papers, on top of the existing detector_v2.py pipeline.

Scope note (read this before running at full corpus size): detector_v2.py's
"Candidate / No-candidate" split only flags papers that match an
availability KEYWORD or a repo-domain LINK. Axis A ("does this paper use
external data at all") is a broader question than that -- a paper can name
a dataset ("we use CIFAR-10") with zero availability language and zero
link, and still clearly trigger Axis A (Case 3: present, not handed over).
Those papers currently sit in detector_v2's "No candidate" bucket and will
NOT be picked up by --scope candidates below. Use --scope all once you're
ready to pay the LLM-call cost of a full-corpus pass; start with
--scope candidates for a fast, cheap first pass over the highest-yield
subset.

This script deliberately does HALF the job -- extraction, not classification:
  1. Reuse cached PDF text if detector_v2.py already ran on it
     (cache/pdftext/{arxiv_id}.txt); otherwise download + extract fresh,
     using the same pdftotext/pdftohtml approach and the same "delete PDF
     immediately" rule as detector_v2.py.
  2. Deterministically verify every link detector_v2.py already extracted
     for that paper (HTTP HEAD, falling back to a small ranged GET for
     servers that reject HEAD) -- resolves / broken / timeout / redirected.
     This is the automated version of the manual link-checking done
     throughout the pilot review (it's what caught the GQG 404 and
     confirmed the ARMOR embargo by hand).
  3. Write one record per paper -- including the full extracted text --
     to cache/axis_case/axis_case_{group}.jsonl, with axis_a_case /
     axis_b_case left as null and notes="pending_claude_code_classification".

The actual classification (step 4: read the text, apply the Axis/Case
framework, decide the case for each axis) is NOT done here and is NOT an
API call to a hosted LLM. It's done by a Claude Code agent reading
DATA_AVAILABILITY_FRAMEWORK.md and then this script's output file directly,
overwriting the null fields in place -- see the long comment above
classify_with_claude_code() below for the exact handoff. Every record is
left with Verified="" regardless of who/what classified it, for a human to
confirm -- same convention as review_queue_link_found.csv.

Usage:
    python3 scripts/axis_case_classifier.py --group cs --scope candidates
    python3 scripts/axis_case_classifier.py --group cs --scope all --limit 50
    python3 scripts/axis_case_classifier.py --group quantum --scope candidates
    python3 scripts/axis_case_classifier.py --group cs --ids 2608.05055 2608.01552
    # then, in a Claude Code session:
    #   "read DATA_AVAILABILITY_FRAMEWORK.md, then classify every pending
    #    record in cache/axis_case/axis_case_cs.jsonl and write the results
    #    back into that file"
    # then:
    python3 scripts/build_axis_case_csv.py cs
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from domain_definitions import GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
DATA_DIR = ROOT / "data"
PDF_DIR = CACHE / "pdfs"
TXT_DIR = CACHE / "pdftext"
AXIS_CACHE_DIR = CACHE / "axis_case"

UA = "Mozilla/5.0 (research; systematic-review-tool; contact:as3485@rit.edu)"

PDF_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR.mkdir(parents=True, exist_ok=True)
AXIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# The framework is NOT duplicated here as a hardcoded string. It lives in
# exactly one place -- DATA_AVAILABILITY_FRAMEWORK.md -- and this module
# loads that file at runtime. This makes the .md file the single source of
# truth (SSOT): edit the framework there, and every consumer (this script's
# prompt-building, a Claude Code agent's own reading of the same file, any
# future scripted API call) picks up the change automatically, with no
# second copy that can silently drift out of sync.
# ---------------------------------------------------------------------------
FRAMEWORK_MD_PATH = ROOT / "DATA_AVAILABILITY_FRAMEWORK.md"

PROMPT_RULES = """
Rules:
- If link-verification results show a link the paper claims is available but
  it returned an error/timeout, that is Case 5, not Case 2 or Case 3.
- If the paper says data is available "upon request" / "from the authors"
  with no immediate self-service link, that is Case 6.
- Case 4 is for data whose EXISTENCE is acknowledged but whose description
  is too thin to locate or reconstruct it (e.g. "we used 5,000 samples"
  with no dataset name). Case 3 is for data that IS named/cited but simply
  has no access path given. Do not confuse these two.
- Set flag_for_human=true whenever confidence is not "high", or whenever a
  judgment call was required at a case boundary (this mirrors the project's
  policy of never silently finalizing an ambiguous call).
- Base your answer only on the provided text. Do not assume a dataset name
  you recognize (e.g. "MNIST") is definitely linked elsewhere unless the
  text or link-verification results actually show that.
""".strip()


def load_framework_text() -> str:
    """Read the framework straight from DATA_AVAILABILITY_FRAMEWORK.md.
    Fails loudly if the file is missing, rather than silently falling back
    to some stale embedded copy -- there must be exactly one place this
    definition lives."""
    if not FRAMEWORK_MD_PATH.exists():
        raise FileNotFoundError(
            f"{FRAMEWORK_MD_PATH} not found. The classification framework "
            "is defined only in that file (no hardcoded fallback exists in "
            "this script by design) -- restore it before running."
        )
    return FRAMEWORK_MD_PATH.read_text()


def build_system_prompt() -> str:
    """Built fresh each call (cheap: one file read) so a mid-session edit
    to DATA_AVAILABILITY_FRAMEWORK.md is picked up on the next paper
    without restarting anything."""
    framework_text = load_framework_text()
    return f"""You are classifying a research paper's data-availability
practices using a fixed two-axis, six-case framework. Read the extracted
paper text (and the link-verification results, if any links were found) and
return ONLY a JSON object, no other text, with this exact shape:

{{
  "axis_a_case": <1-6>,
  "axis_a_evidence": "<short direct quote or paraphrase from the text, or empty string if Case 1>",
  "axis_b_case": <1-6>,
  "axis_b_evidence": "<short direct quote or paraphrase from the text, or empty string if Case 1>",
  "confidence": "<high|medium|low>",
  "flag_for_human": <true|false>,
  "notes": "<one sentence explaining any judgment call, e.g. Case 3 vs Case 4 boundary>"
}}

Framework definitions (loaded from {FRAMEWORK_MD_PATH.name}):
{framework_text}

{PROMPT_RULES}
"""


# ---------------------------------------------------------------------------
# Reused from detector_v2.py's approach: download/extract, but prefer the
# already-cached text so a corpus already scanned by detector_v2 doesn't
# get re-downloaded.
# ---------------------------------------------------------------------------

def get_cached_text(arxiv_id: str) -> str | None:
    txt_path = TXT_DIR / f"{arxiv_id}.txt"
    if txt_path.exists():
        return txt_path.read_text(errors="ignore")
    return None


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
        txt_path.write_text(out.stdout)
        return out.stdout
    except Exception:
        return ""


def get_text_for(arxiv_id: str) -> str:
    """Prefer the cache detector_v2.py already built; only hit the network
    if this paper was never scanned before."""
    cached = get_cached_text(arxiv_id)
    if cached is not None:
        return cached
    pdf_path = download_pdf(arxiv_id)
    if pdf_path is None:
        return ""
    text = extract_text(pdf_path)
    try:
        pdf_path.unlink()  # same disk-space rule as detector_v2.py -- never keep PDFs
    except OSError:
        pass
    return text


# ---------------------------------------------------------------------------
# NEW: deterministic link verification. detector_v2.py only ever extracted
# links; it never checked whether they resolve. This is what would have
# caught the GQG 404 and the ARMOR-embargo distinction automatically.
# ---------------------------------------------------------------------------

def _verify_link_once(url: str, timeout: int) -> dict:
    """One full HEAD-then-GET attempt. See verify_link() for the retry
    wrapper around this -- a single timeout here is not treated as a
    confirmed break."""
    headers = {"User-Agent": UA}
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, headers=headers, method=method)
            if method == "GET":
                req.add_header("Range", "bytes=0-512")
            with urlopen(req, timeout=timeout) as resp:
                status = resp.status
                final_url = resp.geturl()
                return {
                    "url": url,
                    "status_code": status,
                    "resolved": 200 <= status < 400,
                    "final_url": final_url if final_url != url else None,
                    "error": None,
                }
        except HTTPError as e:
            # A real HTTP error (404, 403, etc.) -- no point retrying with GET
            # if HEAD already got a definitive error code back, and no point
            # retrying the whole thing later either: this is a definitive
            # answer, not a transient failure.
            return {
                "url": url, "status_code": e.code, "resolved": False,
                "final_url": None, "error": f"HTTP {e.code}",
            }
        except URLError as e:
            if method == "HEAD":
                continue  # try GET before giving up
            return {
                "url": url, "status_code": None, "resolved": False,
                "final_url": None, "error": str(e.reason),
            }
        except Exception as e:
            if method == "HEAD":
                continue
            return {
                "url": url, "status_code": None, "resolved": False,
                "final_url": None, "error": str(e),
            }
    return {"url": url, "status_code": None, "resolved": False,
            "final_url": None, "error": "unreachable (both HEAD and GET failed)"}


def verify_link(url: str, timeout: int = 10, retries: int = 2, retry_delay: float = 3.0) -> dict:
    """Best-effort check of whether a URL resolves, retrying transient
    failures before recording a link as broken. Added after a case
    (2608.07106's Zenodo DOI) where a single timeout on one run looked like
    a broken link despite the same URL resolving fine on every other check
    -- see PIPELINE_GAPS.md item 3. A definitive HTTP error (404, 403, ...)
    is never retried, since that's a real answer, not a transient blip;
    only a network-level failure (timeout, connection reset, DNS hiccup)
    gets a second chance."""
    result = _verify_link_once(url, timeout)
    attempt = 1
    while not result["resolved"] and result["status_code"] is None and attempt <= retries:
        time.sleep(retry_delay)
        result = _verify_link_once(url, timeout)
        attempt += 1
    if attempt > 1:
        result["retries_used"] = attempt - 1
    result = check_repo_content(result, timeout)
    return result


def verify_links(urls: list[str]) -> list[dict]:
    results = []
    for u in urls:
        results.append(verify_link(u))
        time.sleep(0.3)  # politeness delay, same spirit as the arXiv fetch delay
    return results


# ---------------------------------------------------------------------------
# LAYER 1 (2026-08-29): a resolved link (HTTP 200) only proves the URL is
# reachable -- it says nothing about whether real data is actually attached.
# An empty GitHub repo, or a Zenodo record with metadata but no files, both
# resolve fine. For the handful of repository platforms candidate_links
# actually come from (detector_v2.py's REPO_DOMAINS), each has a public API
# that reports real file-level content -- no scraping, no LLM judgment,
# same deterministic/scriptable cost profile as the resolve check above.
# Runs automatically for every resolved link; unsupported domains (anything
# outside GitHub/Zenodo for now) are left untouched, not guessed at.
# ---------------------------------------------------------------------------

def _github_repo_content(url: str, timeout: int) -> dict:
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", url)
    if not m:
        return {}
    owner, repo = m.group(1), re.sub(r"\.git$", "", m.group(2))
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        req = Request(api_url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        size_kb = data.get("size", 0)  # GitHub reports repo size in KB; 0 = empty repo
        return {
            "repo_size_kb": size_kb,
            "repo_is_empty": size_kb == 0,
            "repo_pushed_at": data.get("pushed_at"),
        }
    except Exception as e:
        return {"content_check_error": f"github: {e}"}


def _zenodo_record_content(url: str, timeout: int) -> dict:
    m = re.search(r"zenodo\.org/records?/(\d+)", url)
    if not m:
        return {}
    record_id = m.group(1)
    api_url = f"https://zenodo.org/api/records/{record_id}"
    try:
        req = Request(api_url, headers={"User-Agent": UA})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        files = data.get("files", [])
        return {
            "file_count": len(files),
            "total_size_bytes": sum(f.get("size", 0) for f in files),
            "is_empty": len(files) == 0,
        }
    except Exception as e:
        return {"content_check_error": f"zenodo: {e}"}


def check_repo_content(result: dict, timeout: int = 10) -> dict:
    """Dispatch to a platform-specific content check once a link has already
    resolved. figshare.com and osf.io have public APIs with the same shape
    but different id-extraction rules -- not yet wired in; left as a
    follow-up rather than guessed at."""
    if not result.get("resolved"):
        return result
    url = result["url"]
    if "github.com" in url:
        result.update(_github_repo_content(url, timeout))
    elif "zenodo.org" in url:
        result.update(_zenodo_record_content(url, timeout))
    return result


# ---------------------------------------------------------------------------
# Classification step -- INTENTIONALLY NOT AN API CALL.
#
# This project classifies papers with a Claude Code agent reading the
# extracted text directly (the same manual process used for the 14-paper
# pilot review), not by scripting a call out to a hosted LLM API. This
# function is therefore a deliberate no-op: this script's job stops at
# "extract text + verify links, write a pending record," and a Claude Code
# session picks up from there.
#
# Concretely, the agent step is:
#   1. Run this script (below) to populate cache/axis_case/axis_case_{group}.jsonl
#      with one pending record per paper: full extracted text, verified
#      link results, and axis_a_case/axis_b_case left as null.
#   2. In a Claude Code session, read DATA_AVAILABILITY_FRAMEWORK.md, then
#      open cache/axis_case/axis_case_{group}.jsonl, and for each pending
#      record: read paper_text (and link_results), apply the framework, and
#      overwrite that record's axis_a_case / axis_a_evidence / axis_b_case /
#      axis_b_evidence / confidence / flag_for_human / notes fields in place
#      (same schema this script already writes, so build_axis_case_csv.py
#      needs no changes either way).
#   3. Re-run build_axis_case_csv.py to regenerate the review CSV.
#
# If you ever DO want to script this step against a hosted API instead,
# build_system_prompt() above already builds the exact framework
# instructions this would need (loaded live from
# DATA_AVAILABILITY_FRAMEWORK.md) -- reintroduce a client call here using
# that prompt.
# ---------------------------------------------------------------------------

def classify_with_claude_code(paper_text: str, link_results: list[dict], arxiv_id: str) -> dict:
    """Deliberately unimplemented -- see the module-level comment just above.
    Left in place (rather than deleted) so it's obvious where the
    classification step plugs in, and so the schema returned here documents
    exactly what fields a Claude Code agent (or, later, a scripted API call)
    is expected to fill in per paper."""
    return {
        "axis_a_case": None,
        "axis_a_evidence": "",
        "axis_b_case": None,
        "axis_b_evidence": "",
        "confidence": "n/a",
        "flag_for_human": True,
        "notes": "pending_claude_code_classification",
    }


# ---------------------------------------------------------------------------
# Cache / resumability -- same pattern as detector_v2.py.
# ---------------------------------------------------------------------------

def cache_path_for(group: str) -> Path:
    return AXIS_CACHE_DIR / f"axis_case_{group}.jsonl"


def load_cache(group: str) -> dict:
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


def save_cache(group: str, cache: dict):
    path = cache_path_for(group)
    with open(path, "w") as f:
        for d in cache.values():
            f.write(json.dumps(d) + "\n")


def next_run_path(group: str) -> Path:
    n = 1
    while (DATA_DIR / f"{group}_axis_case_run{n}.jsonl").exists():
        n += 1
    return DATA_DIR / f"{group}_axis_case_run{n}.jsonl"


# ---------------------------------------------------------------------------
# Selecting which papers to run over.
# ---------------------------------------------------------------------------

def load_detector_results(group: str) -> dict:
    """Load whatever detector_v2.py has already produced for this group, so
    we can pull its candidate_links and reuse its status for scoping."""
    path = CACHE / f"analysis_cache_{group}.jsonl"
    if not path.exists():
        # original (no --group) superconducting-qubit-only run
        path = CACHE / "detector_v2_results.jsonl"
    results = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                results[d["arxiv_id"]] = d
    return results


def select_papers(group: str, scope: str, ids: list[str] | None) -> list[dict]:
    detector = load_detector_results(group)
    if ids:
        return [detector.get(i, {"arxiv_id": i, "candidate_links": [], "status": "?"}) for i in ids]
    if scope == "candidates":
        return [d for d in detector.values() if d.get("status") == "Candidate - needs human check"]
    if scope == "all":
        return list(detector.values())
    raise ValueError(f"unknown scope: {scope}")


# ---------------------------------------------------------------------------

def process_one(paper: dict, agent_fetch: bool = False) -> dict:
    """Deterministic half of the pipeline: get text, verify links, and stash
    both plus a not-yet-classified placeholder. paper_text is included in
    the output record (not just used transiently) specifically so a Claude
    Code agent can read cache/axis_case/axis_case_{group}.jsonl directly and
    classify from it without re-extracting anything.

    agent_fetch (LAYER 2, 2026-08-29, default OFF): stamps agent_fetch_enabled
    onto the record. Layer 1 (check_repo_content, above) already covers
    GitHub/Zenodo deterministically at zero extra LLM cost; this flag is only
    for the harder remainder -- a link on a platform with no public content
    API, where only a live look at the actual page can tell a real dataset
    apart from a placeholder. When True, the classification prompt handed to
    the agent for this record should instruct it to use its own fetch tool to
    open a link central to the paper's own availability claim, rather than
    trusting link_results' resolved/status_code alone. Off by default because
    that's a per-paper LLM-driven fetch, not a scripted check -- real added
    cost, not the free deterministic pass Layer 1 is."""
    arxiv_id = paper["arxiv_id"]
    text = get_text_for(arxiv_id)
    if not text:
        return {
            "arxiv_id": arxiv_id,
            "paper_text": "",
            "axis_a_case": None, "axis_a_evidence": "",
            "axis_b_case": None, "axis_b_evidence": "",
            "confidence": "low", "flag_for_human": True,
            "notes": "could not obtain paper text",
            "link_results": [],
            "verified": "",
            "agent_fetch_enabled": agent_fetch,
        }

    candidate_links = paper.get("candidate_links", [])
    link_results = verify_links(candidate_links) if candidate_links else []

    judgment = classify_with_claude_code(text, link_results, arxiv_id)

    return {
        "arxiv_id": arxiv_id,
        "paper_text": text,
        **judgment,
        "link_results": link_results,
        "verified": "",  # blank until a human confirms -- same convention as review_queue_link_found.csv
        "agent_fetch_enabled": agent_fetch,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", choices=list(GROUPS), required=True)
    parser.add_argument("--scope", choices=["candidates", "all"], default="candidates",
                         help="candidates = only papers detector_v2 already flagged (fast, cheap, "
                              "may undercount Axis A -- see module docstring). "
                              "all = every paper in this group's corpus (slow, complete).")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number of papers processed this run.")
    parser.add_argument("--agent-fetch", action="store_true", default=False,
                         help="LAYER 2 (default OFF): stamp agent_fetch_enabled=true on every record "
                              "processed this run, so the classification prompt can instruct the agent "
                              "to independently fetch and inspect a paper's own claimed link rather than "
                              "trusting link_results' resolved/status_code alone. Real added LLM cost per "
                              "paper -- Layer 1 (check_repo_content) already covers GitHub/Zenodo for free; "
                              "only turn this on for a corpus slice where that's not enough.")
    parser.add_argument("ids", nargs="*", help="Optional: only process these specific arXiv IDs")
    args = parser.parse_args()

    papers = select_papers(args.group, args.scope, args.ids or None)
    if args.limit:
        papers = papers[: args.limit]

    cache = load_cache(args.group)
    todo = [p for p in papers if p["arxiv_id"] not in cache]

    print(f"group: {args.group}, scope: {args.scope}, agent_fetch: {args.agent_fetch}")
    print(f"total selected: {len(papers)}, already cached: {len(papers) - len(todo)}, todo: {len(todo)}")
    print("this run only does extraction + link verification -- classification "
          "fields are left null (notes='pending_claude_code_classification') "
          "for a Claude Code agent to fill in next; see the comment above "
          "classify_with_claude_code().")

    for i, p in enumerate(todo):
        result = process_one(p, agent_fetch=args.agent_fetch)
        cache[result["arxiv_id"]] = result
        if (i + 1) % 5 == 0:
            save_cache(args.group, cache)
        if (i + 1) % 10 == 0:
            print(f"processed {i+1}/{len(todo)} (last: {result['arxiv_id']} -> text+links extracted, classification pending)")
        time.sleep(0.2)

    save_cache(args.group, cache)

    snapshot_ids = {p["arxiv_id"] for p in papers}
    snapshot = [cache[aid] for aid in cache if aid in snapshot_ids]
    out_path = next_run_path(args.group)
    with open(out_path, "w") as f:
        for r in snapshot:
            f.write(json.dumps(r) + "\n")

    print(f"\nwrote {len(snapshot)} results to {out_path}")
    n_flagged = sum(1 for r in snapshot if r.get("flag_for_human"))
    print(f"{n_flagged}/{len(snapshot)} flagged for human review (low/medium confidence or judgment-call cases)")
    print("done. Every row has Verified='' -- confirm each in the review CSV before treating it as final.")


if __name__ == "__main__":
    main()

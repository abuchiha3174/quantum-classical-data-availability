#!/usr/bin/env python3
"""
Phase 3: best-effort data-availability auto-flagging.

For arXiv rows: try ar5iv full-text HTML, scan for signal phrases and
repository URLs.
For journal-only (Crossref-only) rows: only attempt for genuinely open
venues (Quantum, npj Quantum Information, PRX Quantum); otherwise mark
paywalled/unclear without fetching.

Writes cache/availability_results.jsonl keyed by a row identifier
(arxiv_id or title) so it can be resumed. Prioritizes most-recent papers
first (by year descending).
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

WORKDIR = "/Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review"
CACHE_DIR = os.path.join(WORKDIR, "cache")
MERGED_JSONL = os.path.join(CACHE_DIR, "merged_papers.jsonl")
RESULTS_JSONL = os.path.join(CACHE_DIR, "availability_results.jsonl")

USER_AGENT = "qDATA-systematic-review-bot/1.0 (mailto:as3485@rit.edu; academic research on data availability statements)"

OPEN_ACCESS_VENUES = ["Quantum", "npj Quantum Information", "PRX Quantum"]

SIGNAL_PHRASES = [
    "data availability",
    "data are available",
    "data is available",
    "data underlying",
    "supporting data",
    "code availability",
    "code is available",
    "reproducibility",
]

REPO_DOMAINS = ["github.com", "zenodo.org", "figshare.com", "osf.io", "data.gov", "dataverse"]

RESERVED_REQUEST_PHRASES = [
    "available upon reasonable request",
    "available on reasonable request",
    "available from the corresponding author",
    "upon request",
]

URL_RE = re.compile(r'https?://[^\s<>"\'\)\]]+', re.IGNORECASE)

# ar5iv (and similar rendering services) inject boilerplate chrome into every
# page -- notably a "report an issue with this article" footer link that
# points at github.com/dginev/ar5iv/issues/new. That link matches our
# github.com repo-domain signal on essentially every successfully-fetched
# page and must be excluded, or almost every row gets a false "Yes".
BOILERPLATE_URL_SUBSTRINGS = [
    "github.com/dginev/ar5iv",
    "github.com/arxiv-vanity",
    "arxiv.org/abs/",
    "arxiv.org/pdf/",
]

# time budget in seconds for this run; stop gracefully if exceeded so we
# always have a valid checkpoint / partial CSV.
TIME_BUDGET_SECONDS = int(os.environ.get("PHASE3_TIME_BUDGET", "5400"))


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def row_key(row):
    return row.get("arxiv_id") or row.get("doi") or row["norm_title"]


def fetch_url(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = resp.read()
            try:
                return data.decode("utf-8", errors="ignore")
            except Exception:
                return None
    except Exception:
        return None


def clean_url(u):
    u = u.rstrip('.,;:)')
    return u


def scan_text(text):
    """Return (data_present, links, method_detail)."""
    lower = text.lower()
    found_repo_links = set()
    for m in URL_RE.finditer(text):
        url = clean_url(m.group(0))
        url_lower = url.lower()
        if any(b in url_lower for b in BOILERPLATE_URL_SUBSTRINGS):
            continue
        for dom in REPO_DOMAINS:
            if dom in url_lower:
                found_repo_links.add(url)
                break

    signal_found = any(p in lower for p in SIGNAL_PHRASES)
    reserved_only = any(p in lower for p in RESERVED_REQUEST_PHRASES)

    if found_repo_links:
        return "Yes (repository link)", sorted(found_repo_links), "repository URL found in full text"
    if signal_found:
        if reserved_only:
            return "Statement only, no link", [], "availability statement found (reasonable request / no concrete link)"
        return "Statement only, no link", [], "availability language found but no repository URL detected"
    return "No", [], "no availability language or repository link detected"


def main():
    merged = load_jsonl(MERGED_JSONL)
    if not merged:
        print("No merged_papers.jsonl found — run merge.py first.", file=sys.stderr)
        sys.exit(1)

    # sort by year descending (most recent first), None/blank years last
    def year_key(r):
        try:
            return -int(r.get("year") or 0)
        except Exception:
            return 0
    merged.sort(key=year_key)

    done = {}
    if os.path.exists(RESULTS_JSONL):
        with open(RESULTS_JSONL) as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    done[rec["key"]] = rec

    start_time = time.time()
    processed_this_run = 0

    with open(RESULTS_JSONL, "a") as out:
        for row in merged:
            key = row_key(row)
            if key in done:
                continue

            elapsed = time.time() - start_time
            if elapsed > TIME_BUDGET_SECONDS:
                print(f"Time budget ({TIME_BUDGET_SECONDS}s) reached, stopping. Processed {processed_this_run} this run.")
                break

            arxiv_id = row.get("arxiv_id", "")
            venue = row.get("venue", "")
            doi = row.get("doi", "")

            result = {"key": key}

            if arxiv_id:
                url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
                text = fetch_url(url)
                if text:
                    data_present, links, detail = scan_text(text)
                    result["data_present"] = data_present
                    result["data_links"] = links
                    result["method"] = "ar5iv full-text scan"
                    result["notes"] = detail
                else:
                    result["data_present"] = "Not yet checked"
                    result["data_links"] = []
                    result["method"] = "not yet processed"
                    result["notes"] = "ar5iv fetch failed or 404"
                time.sleep(3)
            elif any(v in venue for v in OPEN_ACCESS_VENUES):
                # Crossref-only, open-access venue: try DOI resolution to public page
                if doi:
                    url = f"https://doi.org/{doi}"
                    text = fetch_url(url)
                    if text:
                        data_present, links, detail = scan_text(text)
                        result["data_present"] = data_present
                        result["data_links"] = links
                        result["method"] = "publisher page full-text scan"
                        result["notes"] = detail
                    else:
                        result["data_present"] = "Not yet checked"
                        result["data_links"] = []
                        result["method"] = "not yet processed"
                        result["notes"] = "DOI resolution failed"
                    time.sleep(3)
                else:
                    result["data_present"] = "Not yet checked"
                    result["data_links"] = []
                    result["method"] = "not yet processed"
                    result["notes"] = "no DOI available"
            else:
                # paywalled venue, don't bother scraping
                result["data_present"] = "Unclear — paywalled, needs manual check"
                result["data_links"] = []
                result["method"] = "not checked - paywalled"
                result["notes"] = f"venue '{venue}' treated as subscription/paywalled"

            out.write(json.dumps(result) + "\n")
            out.flush()
            done[key] = result
            processed_this_run += 1
            if processed_this_run % 25 == 0:
                print(f"Processed {processed_this_run} rows this run (elapsed {elapsed:.0f}s)...")

    print(f"Phase 3 run complete. Processed {processed_this_run} rows this run. Total done: {len(done)} / {len(merged)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Merge arXiv and Crossref caches into a single row-list, deduplicating by
fuzzy title match. Writes cache/merged_papers.jsonl (one JSON object per
row, matching the eventual CSV schema minus Data Present/Link/Method/Notes
which Phase 3 fills in).
"""
import json
import os
import re
import difflib

WORKDIR = "/Users/abhisheksingh/Documents/qDATA/superconducting_qubits_review"
CACHE_DIR = os.path.join(WORKDIR, "cache")
ARXIV_JSONL = os.path.join(CACHE_DIR, "arxiv_papers.jsonl")
CROSSREF_JSONL = os.path.join(CACHE_DIR, "crossref_papers.jsonl")
MERGED_JSONL = os.path.join(CACHE_DIR, "merged_papers.jsonl")


def zero_pad_date(d):
    """Crossref date-parts join (e.g. '2026-8-10') isn't zero-padded; fix
    for consistency with arXiv's YYYY-MM-DD dates."""
    if not d:
        return d
    parts = d.split("-")
    try:
        parts = [p.zfill(2) if i > 0 else p.zfill(4) for i, p in enumerate(parts)]
    except Exception:
        return d
    return "-".join(parts)


def clean_title(t):
    """Strip HTML/MathML/JATS tags that Crossref sometimes embeds in titles,
    and collapse whitespace."""
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_title(t):
    t = clean_title(t)
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Domain terms used to filter Crossref-only (no arXiv match) results down to
# genuinely on-topic superconducting-qubit papers. Crossref's
# query.bibliographic search is a loose relevance search that otherwise pulls
# in many unrelated condensed-matter-superconductivity and non-superconducting
# -qubit papers (verified by manual inspection of a sample).
DOMAIN_TERMS = [
    "supercond", "transmon", "fluxonium", "gatemon", "josephson junction",
    "josephson qubit", "flux qubit", "charge qubit", "phase qubit",
]


def is_on_topic(norm_title):
    return "qubit" in norm_title and any(term.replace(" ", "") in norm_title.replace(" ", "") or term in norm_title for term in DOMAIN_TERMS)


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


def main():
    arxiv_rows = load_jsonl(ARXIV_JSONL)
    crossref_rows = load_jsonl(CROSSREF_JSONL)
    print(f"Loaded {len(arxiv_rows)} arXiv rows, {len(crossref_rows)} Crossref rows")

    merged = []
    for a in arxiv_rows:
        merged.append({
            "title": clean_title(a["title"]),
            "norm_title": normalize_title(a["title"]),
            "authors": "; ".join(a["authors"]),
            "year": a["year"],
            "published_date": a["published"][:10],
            "venue": "arXiv",
            "arxiv_id": a["arxiv_id"],
            "doi": "",
            "paper_link": a["abs_link"],
            "pdf_link": a["pdf_link"],
            "primary_category": a.get("primary_category", ""),
            "abstract": a.get("abstract", ""),
            "notes": "",
        })

    # index arxiv by normalized title for fuzzy match
    norm_titles = [(m["norm_title"], i) for i, m in enumerate(merged)]

    matched_count = 0
    new_from_crossref = 0
    skipped_offtopic = 0
    for c in crossref_rows:
        cnorm = normalize_title(c["title"])
        best_ratio = 0.0
        best_idx = None
        for nt, idx in norm_titles:
            # quick length-based skip for speed
            if abs(len(nt) - len(cnorm)) > max(20, len(cnorm) * 0.3):
                continue
            ratio = difflib.SequenceMatcher(None, nt, cnorm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = idx
        if best_idx is not None and best_ratio > 0.9:
            # merge onto existing arxiv row
            m = merged[best_idx]
            m["doi"] = c["doi"]
            if "arXiv" in m["venue"] and c["venue"] not in m["venue"]:
                m["venue"] = f"arXiv / {c['venue']}"
            elif c["venue"] not in m["venue"]:
                m["venue"] = m["venue"] + f" / {c['venue']}"
            m["notes"] = (m["notes"] + f" title fuzzy-matched to Crossref entry, confidence {best_ratio:.2f}").strip()
            matched_count += 1
        else:
            # Candidate for a new, Crossref-only row. Crossref's
            # query.bibliographic search is loose relevance matching, not an
            # exact-phrase search, so it returns many condensed-matter /
            # non-qubit superconductivity papers and non-superconducting
            # qubit papers that are off-topic for this review. Apply a
            # title-based domain-relevance filter before adding a new row.
            if not is_on_topic(cnorm):
                skipped_offtopic += 1
                continue
            merged.append({
                "title": clean_title(c["title"]),
                "norm_title": cnorm,
                "authors": c["authors"],
                "year": c["year"],
                "published_date": zero_pad_date(c["published_date"]),
                "venue": c["venue"],
                "arxiv_id": "",
                "doi": c["doi"],
                "paper_link": c["doi_link"],
                "pdf_link": "",
                "primary_category": "",
                "abstract": "",
                "notes": "Crossref-only, no arXiv match found; kept via title domain-relevance filter (contains 'qubit' + superconducting-qubit-type term)",
            })
            new_from_crossref += 1

    print(f"Matched {matched_count} Crossref rows onto existing arXiv rows")
    print(f"Added {new_from_crossref} new Crossref-only rows")
    print(f"Skipped {skipped_offtopic} Crossref-only rows as off-topic (Crossref bibliographic search noise: title lacks 'qubit' + a superconducting-qubit-type term)")
    print(f"Total merged rows: {len(merged)}")

    with open(MERGED_JSONL, "w") as f:
        for m in merged:
            f.write(json.dumps(m) + "\n")

    print(f"Wrote {MERGED_JSONL}")


if __name__ == "__main__":
    main()

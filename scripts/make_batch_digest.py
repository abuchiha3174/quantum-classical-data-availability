"""
Condense a batch file's paper_text down to the excerpts actually relevant to
data-availability classification, so a reviewer (human or Claude Code,
working directly rather than via a spawned agent) can read many papers'
worth of signal without loading full raw text that averages tens of
thousands of characters per paper and can run past half a million for a
single outlier.

This does NOT modify the original batch file. It writes a companion
"_digest.jsonl" containing, per paper: arxiv_id, link_results (unchanged),
and a condensed "digest" string built from:
  - the first ~2000 characters (title/abstract/intro, where papers usually
    state what data/benchmark they use)
  - the last ~3000 characters (references and, commonly, a Data
    Availability Statement)
  - a 300-character window around every case-insensitive hit of a
    data/code-availability keyword anywhere else in the text (the same
    keyword list detector_v2.py uses), so a relevant sentence buried in the
    middle of the paper (e.g. a mid-paper "Data and code are available at
    ...") isn't missed by only looking at the head and tail.

Classification should still be based on this digest plus link_results, the
same way it would be based on the full text -- nothing about the framework
or its application changes, only how much raw text is loaded to do it.
Evidence quotes should still be drawn from the digest text, which is a
verbatim excerpt of the original, not a paraphrase or summary.

After classifying from the digest, use apply_batch_classifications.py to
write the actual classification fields onto the ORIGINAL full records
(preserving the original paper_text in full, unmodified) -- the digest is a
reading aid only, never the thing that gets persisted.

Usage:
    python3 scripts/make_batch_digest.py cache/axis_case/batches/quantum_batch_000.jsonl
"""
import json
import re
import sys
from pathlib import Path

HEAD_CHARS = 2000
TAIL_CHARS = 3000
KEYWORD_WINDOW = 300

KEYWORD_PHRASES = [
    "data availab", "code availab", "materials availab", "software availab",
    "data underlying", "supporting data", "source data", "reproducibility package",
    "supplementary data", "supplementary dataset", "openly available",
    "publicly available", "publicly accessible", "deposited at", "deposited in",
    "available upon", "available on reasonable", "available at http",
    "available from http", "available via http", "dataset is available",
    "datasets are available", "code is available", "released at", "hosted at",
    "archived at", "data and code", "code and data", "raw data are available",
    "raw data is available", "underlying data", "data repository", "code repository",
    "github repository", "zenodo", "figshare", "upon request", "upon reasonable request",
]


def extract_digest(text: str) -> str:
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text  # short paper -- just use all of it, no need to condense

    head = text[:HEAD_CHARS]
    tail = text[-TAIL_CHARS:]

    middle = text[HEAD_CHARS:-TAIL_CHARS]
    lower = middle.lower()
    snippets = []
    seen_spans = []
    for phrase in KEYWORD_PHRASES:
        for m in re.finditer(re.escape(phrase), lower):
            start = max(0, m.start() - KEYWORD_WINDOW // 2)
            end = min(len(middle), m.end() + KEYWORD_WINDOW // 2)
            if any(not (end <= s or start >= e) for s, e in seen_spans):
                continue  # overlaps a snippet already captured
            seen_spans.append((start, end))
            snippets.append(middle[start:end])

    parts = [f"[HEAD]\n{head}"]
    if snippets:
        parts.append("[KEYWORD CONTEXT FROM MIDDLE OF PAPER]\n" + "\n---\n".join(snippets))
    else:
        parts.append("[NOTE: no data/code-availability keyword found in the middle "
                      "of the paper outside the head/tail excerpts shown here]")
    parts.append(f"[TAIL]\n{tail}")
    return "\n\n".join(parts)


def main():
    if len(sys.argv) != 2:
        print(f"usage: python3 {Path(__file__).name} <batch_file.jsonl>")
        sys.exit(1)

    batch_path = Path(sys.argv[1])
    digest_path = batch_path.with_name(batch_path.stem + "_digest.jsonl")

    n = 0
    total_in, total_out = 0, 0
    with open(batch_path) as fin, open(digest_path, "w") as fout:
        for line in fin:
            d = json.loads(line)
            text = d.get("paper_text", "")
            digest = extract_digest(text)
            total_in += len(text)
            total_out += len(digest)
            fout.write(json.dumps({
                "arxiv_id": d["arxiv_id"],
                "link_results": d.get("link_results", []),
                "digest": digest,
            }) + "\n")
            n += 1

    print(f"wrote {n} digests to {digest_path}")
    print(f"original text: {total_in:,} chars -> digest: {total_out:,} chars "
          f"({100 * total_out // max(total_in, 1)}% of original)")


if __name__ == "__main__":
    main()

import csv
import json
import re

CACHE = "cache/merged_papers.jsonl"
CSV_PATH = "data/superconducting_qubits_papers.csv"

# Manual overrides confirmed by hand during chat-based spot checks — these win over the heuristic.
MANUAL_OVERRIDES = {
    "2608.07185": "Atomic Physics",      # Kramers-Henneberger atom qubit
    "2608.02733": "Quantum Sensing",     # HFGW detection with SC qubits
    "2607.27771": "Quantum Magnonics",   # topical review, quantum magnonics
    "2607.29666": "Quantum Optomechanics",  # release-free phononic crystal
    "2607.26161": "Quantum Optomechanics",  # piezo-optomechanical transducer
}


def norm_title(t):
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def classify(title, abstract, category):
    text = f"{title} {abstract}".lower()
    cat = (category or "").lower()

    def has(*words):
        return any(w in text for w in words)

    # --- Non-quantum-computing domains, checked first ---
    if has("kramers-henneberger") or (has("strong-field") and has(" atom ", "atomic") and not has("superconducting")):
        return "Atomic Physics"

    if cat.startswith("hep-") or cat.startswith("astro-ph") or cat == "gr-qc":
        if has("gravitational wave", "haloscope", "dark matter", "axion", "dark photon"):
            return "Quantum Sensing"

    if has("gravitational wave", "haloscope") and has("qubit"):
        return "Quantum Sensing"

    if has("magnon", "magnonic", "magnonics") and not has("quantum processor", "quantum error correction", "logical qubit"):
        return "Quantum Magnonics"

    if has("phononic crystal", "piezo-optomechanical", "optomechanical crystal", "microwave-to-optical") and not has(
        "transmon qubit", "flux qubit", "qubit gate", "qubit readout"
    ):
        return "Quantum Optomechanics"

    if has("neutrino", "collider", "dark sector") and not has("qubit"):
        return "High Energy Physics"

    if has("photonic qubit", "linear optics quantum") and not has("superconducting"):
        return "Photonic Quantum Computing"

    if has("trapped ion", "ion trap") and not has("superconducting"):
        return "Trapped-Ion Computing"

    if has("neutral atom", "rydberg atom") and not has("superconducting"):
        return "Neutral-Atom Computing"

    if has("spin qubit") and has("semiconductor", "quantum dot") and not has("superconducting", "transmon", "fluxonium", "josephson"):
        return "Semiconductor Spin Qubits"

    # --- Default: in scope ---
    return "Quantum Computing"


def main():
    lookup_by_arxiv = {}
    lookup_by_title = {}
    with open(CACHE) as f:
        for line in f:
            d = json.loads(line)
            key = d.get("arxiv_id") or ""
            if key:
                lookup_by_arxiv[key] = d
            nt = d.get("norm_title") or norm_title(d.get("title", ""))
            lookup_by_title[nt] = d

    with open(CSV_PATH, newline="") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    domain_idx = header.index("Domain")
    arxiv_idx = header.index("arXiv ID")
    title_idx = header.index("Title")

    counts = {}
    matched = 0
    unmatched = 0

    for row in rows[1:]:
        arxiv_id = row[arxiv_idx].strip()
        title = row[title_idx]
        d = lookup_by_arxiv.get(arxiv_id)
        if d is None:
            d = lookup_by_title.get(norm_title(title))
        if d is None:
            unmatched += 1
            domain = "Quantum Computing"  # fallback, can't classify without abstract
        else:
            matched += 1
            abstract = d.get("abstract") or ""
            category = d.get("primary_category") or ""
            domain = classify(title, abstract, category)

        if arxiv_id in MANUAL_OVERRIDES:
            domain = MANUAL_OVERRIDES[arxiv_id]

        row[domain_idx] = domain
        counts[domain] = counts.get(domain, 0) + 1

    with open(CSV_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)

    print("matched:", matched, "unmatched (title/abstract missing):", unmatched)
    print("Domain distribution:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main()

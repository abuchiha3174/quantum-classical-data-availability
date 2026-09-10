"""
Detect which countries (and continents/regions) a paper's authors are
affiliated with, using the author/affiliation block that always appears at
the very start of a paper's extracted text (the same text already captured
in every digest's [HEAD] section, or the first ~3000 characters of
paper_text for records that don't have a digest yet).

Approach: pure pattern matching against a curated country name list plus a
US state list (needed because many US-affiliated papers give "City, ST
ZIP" without ever writing the word "USA"), no model call involved. This
will not be perfect -- ambiguous or omitted country info, unusual
institution naming, and multi-country author lists with inconsistent
formatting are all real limitations -- but it is fast, deterministic, and
reproducible, and gets the large majority of cases right since author
affiliations follow fairly standard conventions.

Region classification is a paper-level SET, not a single label: a
multi-institution collaboration spanning e.g. the US, Germany, and China
gets all three countries and both the "North America"/"Europe"/"Asia"
regions recorded, not forced into one bucket.

Usage:
    python3 scripts/extract_countries.py --group quantum
    python3 scripts/extract_countries.py --group quantum \\
        --input cache/axis_case/batches/quantum_batch_000.jsonl --out-suffix batch_000
    python3 scripts/extract_countries.py --group cs --ids 2608.05055 2608.01552
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AXIS_CACHE_DIR = ROOT / "cache" / "axis_case"
TXT_DIR = ROOT / "cache" / "pdftext"

HEAD_CHARS = 3000

# canonical name -> region.
COUNTRY_TO_REGION = {
    "united states": "North America", "canada": "North America", "mexico": "North America",
    "united kingdom": "Europe", "germany": "Europe", "france": "Europe", "switzerland": "Europe",
    "netherlands": "Europe", "belgium": "Europe", "austria": "Europe", "sweden": "Europe",
    "norway": "Europe", "denmark": "Europe", "finland": "Europe",
    "italy": "Europe", "spain": "Europe", "portugal": "Europe",
    "poland": "Europe", "czech republic": "Europe", "hungary": "Europe", "romania": "Europe",
    "greece": "Europe", "ireland": "Europe", "russia": "Europe", "ukraine": "Europe",
    "slovenia": "Europe", "slovakia": "Europe", "croatia": "Europe",
    "china": "Asia", "japan": "Asia", "south korea": "Asia", "singapore": "Asia",
    "india": "Asia", "taiwan": "Asia", "hong kong": "Asia", "israel": "Asia",
    "united arab emirates": "Asia", "saudi arabia": "Asia", "thailand": "Asia", "vietnam": "Asia",
    "australia": "Oceania", "new zealand": "Oceania",
    "brazil": "South America", "argentina": "South America", "chile": "South America",
    "south africa": "Africa", "egypt": "Africa",
}

# alias/variant phrase -> canonical name in COUNTRY_TO_REGION. Every phrase
# actually searched for in the text lives here (including the canonical
# names themselves, as self-aliases), so multiple phrasings of the same
# country (e.g. "usa" and "united states of america") always collapse to
# one entry instead of appearing as separate "countries" in the output.
# Longer/more specific phrases are listed first so matching order can
# prefer them if ever needed.
COUNTRY_ALIASES = {
    "united states of america": "united states", "usa": "united states", "u.s.a.": "united states",
    "the netherlands": "netherlands", "korea": "south korea", "england": "united kingdom",
    "scotland": "united kingdom", "uk": "united kingdom", "czechia": "czech republic",
    **{name: name for name in COUNTRY_TO_REGION},
}

US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode island", "south carolina", "south dakota", "tennessee", "texas",
    "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming",
]
# US state postal abbreviations, matched only with strict word boundaries
# and only when followed by a plausible ZIP code, to avoid false hits on
# unrelated two-letter tokens (e.g. "IN" the word, "OR" the word).
US_STATE_ABBR_ZIP_RE = re.compile(
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|"
    r"WV|WI|WY)\s+\d{5}(-\d{4})?\b"
)

# Institution/company names observed in this corpus whose affiliation line
# gives no city, state, or country at all (e.g. "1 NVIDIA, 2 IQM Quantum
# Computers, ..." with nothing else). These are recorded as a plain label
# -- NOT resolved to a country -- per instruction: no inference, just note
# which known institution was seen. Extend this list as new no-geography
# institutions turn up; it is deliberately not exhaustive.
KNOWN_INSTITUTION_LABELS = [
    "NVIDIA", "IQM Quantum Computers", "IQM", "Conductor Quantum",
    "EeroQ Corporation", "EeroQ", "Infleqtion", "Vector Institute",
    "National Physical Laboratory", "Fermi National Accelerator Laboratory",
    "Fermilab", "Google Quantum AI", "IBM Quantum", "Rigetti Computing",
    "Rigetti", "Quantinuum", "PsiQuantum", "Quantum Machines", "Qolab",
    "Keysight Technologies", "QC Design GmbH", "Q.M Technologies",
    "Quantum Elements", "TraverseQuantum",
]


def detect_institution_labels(head_text: str) -> list[str]:
    found = []
    for name in KNOWN_INSTITUTION_LABELS:
        if re.search(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", head_text):
            found.append(name)
    return sorted(set(found))


def extract_head(record: dict) -> str:
    if "digest" in record and record["digest"]:
        m = re.search(r"\[HEAD\]\n(.*?)(?:\n\[|\Z)", record["digest"], re.DOTALL)
        if m:
            return m.group(1)
    return record.get("paper_text", "")[:HEAD_CHARS]


def detect_countries(head_text: str) -> dict:
    lower = head_text.lower()
    countries = set()

    for phrase, canonical in COUNTRY_ALIASES.items():
        if re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", lower):
            countries.add(canonical)

    if "united states" not in countries:
        if any(re.search(r"(?<![a-z])" + re.escape(state) + r"(?![a-z])", lower) for state in US_STATES):
            countries.add("united states")
        elif US_STATE_ABBR_ZIP_RE.search(head_text):
            countries.add("united states")

    regions = sorted({COUNTRY_TO_REGION[c] for c in countries})
    display_names = {"united states": "United States", "united kingdom": "United Kingdom",
                      "united arab emirates": "United Arab Emirates", "south korea": "South Korea",
                      "south africa": "South Africa", "new zealand": "New Zealand",
                      "hong kong": "Hong Kong", "czech republic": "Czech Republic",
                      "saudi arabia": "Saudi Arabia"}

    return {
        "countries": sorted(display_names.get(c, c.title()) for c in countries),
        "regions": regions,
    }


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", required=True)
    parser.add_argument("--input", type=str, default=None,
                         help="Path to a specific batch/records file (e.g. "
                              "cache/axis_case/batches/quantum_batch_000.jsonl). "
                              "Defaults to the full group cache if omitted.")
    parser.add_argument("--out-suffix", type=str, default=None,
                         help="Suffix for the output filename, e.g. 'batch_000' -> "
                              "countries_{group}_batch_000.jsonl. Defaults to no suffix.")
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()

    src_path = Path(args.input) if args.input else (AXIS_CACHE_DIR / f"axis_case_{args.group}.jsonl")
    records = load_jsonl(src_path)
    if args.ids:
        records = [r for r in records if r["arxiv_id"] in args.ids]

    suffix = f"_{args.out_suffix}" if args.out_suffix else ""
    out_path = AXIS_CACHE_DIR / f"countries_{args.group}{suffix}.jsonl"
    n_with_country = 0
    n_with_institution_only = 0
    with open(out_path, "w") as f:
        for r in records:
            head = extract_head(r)
            result = detect_countries(head)
            institutions = [] if result["countries"] else detect_institution_labels(head)
            if result["countries"]:
                n_with_country += 1
            elif institutions:
                n_with_institution_only += 1
            f.write(json.dumps({"arxiv_id": r["arxiv_id"], **result, "institution_labels": institutions}) + "\n")

    print(f"source: {src_path}")
    print(f"processed {len(records)} papers")
    print(f"  {n_with_country} with at least one detected country")
    print(f"  {n_with_institution_only} with no country but at least one known institution label")
    print(f"  {len(records) - n_with_country - n_with_institution_only} with neither")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()

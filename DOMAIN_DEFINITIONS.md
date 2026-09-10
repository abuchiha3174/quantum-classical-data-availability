# Domain definitions — quantum vs. classical computing comparison groups

This document defines the candidate research domains for the quantum-vs-regular-computing
data-availability comparison (per Daniel's request to scope "regular computing" and to
consider several groups on both sides). The quantum side is broken into 6 pipeline-stage
pillars; the CS side mirrors that structure so each pillar has a same-shape counterpart.

Status: candidate definitions, not yet all built into paper-pull scripts. Only the
"Superconducting qubits" quantum pillar (#1, restricted to the hardware-fabrication slice)
has an actual running dataset (`data/superconducting_qubits_papers.csv`, ~1,478 papers).

## Quantum Computing

| Domains | Topics | arXiv mapping |
|---|---|---|
| **1. Quantum Hardware** | Superconducting processors, transmon qubits, Josephson junctions, chip fabrication, cryogenics, TLS defects, coherence, noise/decoherence, crosstalk, leakage, readout errors | `quant-ph` (primary) + `cond-mat.supr-con`, `cond-mat.mes-hall` — this is the scope already running |
| **2. Quantum Control & Operations** | Gates, gate fidelity, microwave control, pulse shaping, calibration, optimal control, dynamical decoupling, error characterization/mitigation | `quant-ph` almost entirely — no dedicated category; occasionally cross-listed to `eess.SY` |
| **3. Quantum Error Correction** | Surface codes, LDPC codes, bosonic codes, fault-tolerant gates, logical qubits, syndrome extraction, decoders, thresholds | `quant-ph` (primary) + `cs.IT` (code-theoretic papers), `cs.CC` (threshold/complexity papers) |
| **4. Quantum Algorithms** | Shor, Grover, QAOA, VQE, simulation, QML, Hamiltonian simulation, quantum linear algebra, amplitude estimation, quantum walks, VQAs | `quant-ph` (primary) + `cs.DS`, `cs.CC`, `cs.LG` (quantum ML specifically) |
| **5. Quantum Compilation & Circuit Optimization** | Circuit optimization, gate decomposition, qubit mapping, routing, SWAP optimization, scheduling, transpilation, hardware/noise-aware compilation | `quant-ph` (primary) + `cs.AR`, `cs.PL` |
| **6. Quantum Information Theory** | Entanglement, quantum channels, measurement, complexity, communication, cryptography, information-theoretic limits | `quant-ph` (primary) + `cs.IT`, `cs.CR` (quantum crypto specifically) |

## Computer Science (mirrored structure)

| Domains | Topics | arXiv mapping |
|---|---|---|
| **1. Classical Hardware** | CMOS/transistor fabrication, semiconductor device physics, chip fabrication, device noise characterization, interconnect crosstalk, signal leakage, sensing-circuit errors | `cond-mat.mes-hall`, `physics.app-ph` + `cs.AR`, `cs.ET` |
| **2. Classical Control & Operations** | Digital/analog circuit control, timing calibration, signal filtering, feedback control, noise mitigation, circuit testing | `eess.SY`, `eess.SP` + `cs.AR` |
| **3. Classical Error-Correcting Codes / Coding Theory** | LDPC codes (classical origin), turbo codes, Reed-Solomon codes, fault-tolerant computing, redundancy/logical encoding, decoders, error thresholds | `cs.IT` (primary) + `cs.DC` (distributed fault tolerance) |
| **4. Classical Algorithms** | Sorting/searching, optimization, ML algorithms, simulation algorithms, linear algebra, graph algorithms, cryptographic algorithms | `cs.DS` (primary) + `cs.CC`, `cs.LG`, `cs.NA` |
| **5. Compiler & Circuit Optimization** | Compiler optimization, instruction scheduling, register allocation, circuit synthesis, place-and-route, hardware-aware compilation, logic synthesis | `cs.PL` (primary) + `cs.AR` |
| **6. Classical Information Theory** | Channel capacity, communication theory, information-theoretic limits, cryptography, complexity theory | `cs.IT` (primary) + `cs.CR` |

## Notes / open questions

- **Pillar 2 (Control & Operations) is the weakest pairing on both sides.** Neither quantum
  control nor classical control-systems research has a single dedicated arXiv category —
  both will need keyword-based scoping rather than clean category filtering.
- **Pillars 3-6 are largely platform-agnostic** on the quantum side (don't require
  "superconducting" or any specific hardware keyword to match), unlike pillars 1-2 which are
  naturally tied to a specific hardware platform. Keep this distinction in mind when writing
  search queries — a pillar-3-6 query should NOT require a hardware-platform keyword, or it
  will silently miss most of the relevant papers.
- **Excluded from this comparison entirely:** quantum sensing/metrology (e.g. gravitational-
  wave detection, dark-matter search using qubits as sensors) — already flagged as
  off-domain in the existing superconducting-qubit dataset, since the qubit is used as a
  detector rather than for computation.
- **Full arXiv taxonomy reference:** https://arxiv.org/category_taxonomy — top-level groups
  Physics, Computer Science, Electrical Engineering and Systems Science (eess.*), Mathematics,
  Quantitative Biology, Quantitative Finance, Statistics, Economics. Only Physics, Computer
  Science, and eess.* are relevant to this comparison; the rest were checked and ruled out.

## Next steps

Tooling for this is already built (see `COMMANDS.md` for the full command reference):

1. `python3 scripts/build_pillar_paper_list.py quantum` — queries arXiv once per pillar
   keyword (edit `scripts/domain_definitions.py` to change pillars/keywords), dedupes
   across pillars, writes one combined file: `data/quantum_pillars_run{N}.jsonl`
   (auto-incrementing, never overwrites a previous pull).
2. `python3 scripts/detector_v2.py --group quantum --input data/quantum_pillars_run{N}.jsonl`
   — scans for data/code-availability signals AND classifies each paper's actual content
   against every pillar's keyword list, flagging mismatches between the pillar it was
   searched under and what its content actually supports. Writes
   `data/quantum_availability_run{N}.jsonl`.
3. Manual + LLM-agent verification of flagged candidates, same process as the
   superconducting-qubit dataset.
4. Same two commands with `cs` instead of `quantum`, once the CS side is ready to start
   (currently on hold per instruction — quantum pillars first).

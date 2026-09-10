"""
Domain definitions for the quantum-vs-classical computing data-availability
comparison. Edit THIS file to change pillar keywords/categories -- both
build_pillar_paper_list.py and detector_v2.py import from here, so a single
edit here propagates through the whole pipeline on the next run without
touching any other script.

See DOMAIN_DEFINITIONS.md at the project root for the reasoning behind this
6-pillar structure and the quantum-to-CS pairing rationale.

Status: CS_PILLARS is now the active group, all 6 pillars enabled (started
as an algorithms-only quick look per Daniel's request, then expanded to the
full set). QUANTUM_PILLARS beyond pillar 1 (hardware, already running as
the existing superconducting-qubit dataset) haven't been pulled yet.
"""

# Pillar 1 (Quantum Hardware) already has a running, manually-verified dataset
# (data/superconducting_qubits_papers.csv, ~1,478 papers) -- reused rather
# than re-queried. All other pillars are new and need a fresh arXiv pull.

QUANTUM_PILLARS = [
    {
        "id": "hardware",
        "name": "Quantum Hardware",
        "keywords": [
            "superconducting qubit", "transmon qubit", "josephson junction qubit",
            "quantum chip fabrication", "cryogenic qubit", "TLS defect qubit",
            "qubit coherence", "qubit decoherence", "qubit crosstalk",
            "qubit leakage", "qubit readout error",
        ],
        "arxiv_categories": ["quant-ph", "cond-mat.supr-con", "cond-mat.mes-hall"],
        "existing_dataset": "data/superconducting_qubits_papers.csv",
        "platform_specific": True,
    },
    {
        "id": "control",
        "name": "Quantum Control & Operations",
        "keywords": [
            "quantum gate fidelity", "microwave control qubit", "pulse shaping qubit",
            "qubit calibration", "optimal control qubit", "dynamical decoupling",
            "quantum error mitigation", "quantum error characterization",
        ],
        "arxiv_categories": ["quant-ph"],
        "platform_specific": False,
    },
    {
        "id": "qec",
        "name": "Quantum Error Correction",
        "keywords": [
            "surface code quantum", "quantum LDPC code", "bosonic quantum code",
            "fault-tolerant quantum gate", "logical qubit", "syndrome extraction",
            "quantum decoder", "quantum error threshold", "hardware-efficient QEC",
        ],
        "arxiv_categories": ["quant-ph", "cs.IT", "cs.CC"],
        "platform_specific": False,
    },
    {
        "id": "algorithms",
        "name": "Quantum Algorithms",
        "keywords": [
            "Shor's algorithm", "Grover's algorithm", "QAOA",
            "variational quantum eigensolver", "quantum simulation algorithm",
            "quantum machine learning", "Hamiltonian simulation",
            "quantum linear algebra", "amplitude estimation", "quantum walk",
            "variational quantum algorithm",
        ],
        "arxiv_categories": ["quant-ph", "cs.DS", "cs.CC", "cs.LG"],
        "platform_specific": False,
    },
    {
        "id": "compilation",
        "name": "Quantum Compilation & Circuit Optimization",
        "keywords": [
            "quantum circuit optimization", "quantum gate decomposition",
            "qubit mapping", "quantum circuit routing", "SWAP optimization",
            "quantum transpilation", "hardware-aware quantum compilation",
            "noise-aware quantum compilation",
        ],
        "arxiv_categories": ["quant-ph", "cs.AR", "cs.PL"],
        "platform_specific": False,
    },
    {
        "id": "info_theory",
        "name": "Quantum Information Theory",
        "keywords": [
            "quantum entanglement", "quantum channel capacity", "quantum measurement theory",
            "quantum complexity theory", "quantum communication", "quantum cryptography",
            "quantum information theoretic", "quantum Shannon theory", "entanglement entropy",
        ],
        "arxiv_categories": ["quant-ph", "cs.IT", "cs.CR"],
        "platform_specific": False,
    },
]

# Mirrors the quantum structure 1:1. Started as algorithms-only (a quick
# initial-look run per Daniel's request), then expanded to all 6 pillars.
# To narrow back down to a subset, comment out individual pillar dicts below
# and re-run build_pillar_paper_list.py cs -- nothing else needs to change.
CS_PILLARS = [
    {
        "id": "hardware",
        "name": "Classical Hardware",
        "keywords": [
            "CMOS fabrication", "transistor device physics", "semiconductor device noise",
            "interconnect crosstalk", "chip fabrication process",
        ],
        "arxiv_categories": ["cond-mat.mes-hall", "physics.app-ph", "cs.AR", "cs.ET"],
        "platform_specific": True,
    },
    {
        "id": "control",
        "name": "Classical Control & Operations",
        "keywords": [
            "digital circuit calibration", "feedback control system", "signal processing filtering",
            "circuit noise mitigation", "circuit testing verification",
            "model predictive control", "adaptive control system",
        ],
        "arxiv_categories": ["eess.SY", "eess.SP", "cs.AR"],
        "platform_specific": False,
    },
    {
        "id": "coding_theory",
        "name": "Classical Error-Correcting Codes / Coding Theory",
        "keywords": [
            "LDPC code", "turbo code", "Reed-Solomon code", "fault-tolerant computing",
            "error correcting code decoder", "error threshold coding theory",
            "polar code", "convolutional code",
        ],
        "arxiv_categories": ["cs.IT", "cs.DC"],
        "platform_specific": False,
    },
    {
        "id": "algorithms",
        "name": "Classical Algorithms",
        "keywords": [
            "sorting algorithm", "search algorithm complexity", "optimization algorithm",
            "machine learning algorithm", "simulation algorithm", "graph algorithm",
            "cryptographic algorithm",
            "convolutional neural network", "transformer architecture", "reinforcement learning",
            "graph neural network", "generative adversarial network", "dynamic programming",
            "approximation algorithm", "combinatorial optimization",
        ],
        "arxiv_categories": ["cs.DS", "cs.CC", "cs.LG", "cs.NA"],
        "platform_specific": False,
    },
    {
        "id": "compilation",
        "name": "Compiler & Circuit Optimization",
        "keywords": [
            "compiler optimization", "instruction scheduling", "register allocation",
            "circuit synthesis", "place and route", "hardware-aware compilation",
            "logic synthesis",
        ],
        "arxiv_categories": ["cs.PL", "cs.AR"],
        "platform_specific": False,
    },
    {
        "id": "info_theory",
        "name": "Classical Information Theory",
        "keywords": [
            "channel capacity", "communication theory", "information theoretic limit",
            "cryptography protocol", "computational complexity theory",
            "Shannon capacity", "differential privacy", "zero-knowledge proof",
        ],
        "arxiv_categories": ["cs.IT", "cs.CR"],
        "platform_specific": False,
    },
]

GROUPS = {"quantum": QUANTUM_PILLARS, "cs": CS_PILLARS}

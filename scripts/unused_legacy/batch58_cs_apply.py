import csv

# (Verified, Corrected Label, Research Type, Data Source, Simulated/Experimental, Notes)
# All determinations below are from a full re-download + full-text read of each paper
# (not just the cached detector snippets), per explicit instruction to verify with the
# same rigor as the quantum side.
J = {
'2608.18910': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Simulation',
  'Full-text re-check: no explicit availability statement found anywhere, but repo (MIS-KSAT-code) name strongly matches paper topic (Maximum Independent Set / k-SAT).'),
'2608.18780': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed on full read: explicit "the source code is available at" statement.'),
'2608.18727': ('Yes','No - needs closer look','Algorithms/Software','Unclear','Experimental',
  'CORRECTED after full-text re-check: no availability statement and no confirmable repo link found in the fresh full-text read (the cached snippet evidence for this one turned out to be about a different, unrelated section). Recommend a manual open before trusting the original candidate links (some were malformed/concatenated URLs from PDF extraction).'),
'2608.18145': ('Yes','No','Hardware/Fabrication','Not applicable','Experimental',
  'Confirmed: pqm4 is a well-known third-party post-quantum-crypto ARM Cortex-M4 benchmarking suite, not own code. No availability statement anywhere in full text.'),
'2608.17592': ('Yes','No','Algorithms/Software','Not applicable','Simulation',
  'Confirmed: both links (ZCM, wandb) are reference-list citations to third-party tools, not own data/code.'),
'2608.16884': ('Yes','No','Theory','Not applicable','Theory/Analytical',
  'Confirmed: link is to Google JAX, a general third-party ML framework, not own data. No availability statement found.'),
'2608.14288': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "Code is available at Floss on GitHub" statement.'),
'2608.12751': ('Yes','No - needs closer look','Algorithms/Software','Unclear','Experimental',
  'Confirmed ambiguous on full read: repo (CB-EVO) appears twice but no availability statement anywhere, and name does not obviously match paper own tool name (SynAct).'),
'2608.08462': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Experimental',
  'CORRECTED after full-text re-check: no genuine availability statement found (the earlier "code and data" keyword hit was a false match on unrelated prose about "partition-local code and data locality," not a real statement). Repo name (ARMOR.git) still matches paper title exactly, so likely real, but not confirmed by text.'),
'2608.07897': ('Yes','Yes','Algorithms/Software','Original (released)','Simulation',
  'Confirmed: explicit "Code available:" statement.'),
'2608.07471': ('Yes','Yes','Algorithms/Software','Derived from external dataset','Experimental',
  'Confirmed: explicit Data Availability Statement citing the Kaggle Credit Card Fraud Detection dataset -- external, already-published, not newly collected.'),
'2608.07106': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: "two distinct datasets that are publicly available to reproduce" -- own synthetic LiDAR data via Zenodo. KITTI is an external baseline citation, PointNet a third-party tool.'),
'2608.06916': ('Yes','No','Hardware/Fabrication','Not applicable','Experimental',
  'Confirmed: both links are third-party frameworks (VexiiRiscv, Baremetal-NN), no availability statement anywhere.'),
'2608.05055': ('Yes','Yes','Hardware/Fabrication','Original (released)','Experimental',
  'Confirmed: "our GitHub repository" referenced explicitly twice for their own evidence/attack data. OpenROAD/MacroPlacement are third-party benchmark citations.'),
'2608.04466': ('Yes','Yes','Algorithms/Software','Original (released, anonymized)','Experimental',
  'Confirmed: explicit "DATA AVAILABILITY The tool and dataset are available at" statement with an anonymized double-blind link (anonymous.4open.science). SVF and retdec are third-party tool citations.'),
'2608.02612': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "Code and Data Availability... available at" statement, repo matches paper own benchmark name.'),
'2608.01552': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "openly available at" statement, repo matches paper title.'),
'2608.01220': ('Yes','Yes','Algorithms/Software','Derived from external dataset','Experimental',
  'Confirmed: explicit Data Availability Statement citing MNIST via a Kaggle mirror -- external, not newly collected.'),
'2607.28907': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "code is available at" statement, repo matches paper own method name.'),
'2607.27370': ('Yes','No','Algorithms/Software','Not applicable','Experimental',
  'Confirmed: the only link is a reference-list citation to Hop Protocol own airdrop data, not this paper own analysis code. No own-code statement found.'),
'2607.25122': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "code is publicly available at" statement plus a Zenodo DOI.'),
'2607.24998': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "fully open-sourced and can be accessed through our GitHub repository" statement.'),
'2607.24581': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Simulation',
  'Confirmed ambiguous on full read: no availability statement found despite repo (tsp-framework) matching paper topic closely.'),
'2607.22262': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "publicly available on" statement, repo matches paper topic.'),
'2607.20124': ('Yes','Statement only, no link','Algorithms/Software','Original (restricted)','Experimental',
  'CORRECTED after full-text re-check: the explicit Data Availability Statement says "data that support the findings of this study are available from the corresponding author, Y. R., upon reasonable request" -- request-based, no actual repository link confirmed anywhere in the full text (the cair/pyTsetlinMachine link from the cached scan was not corroborated in this re-check). Downgraded from an initial Yes.'),
'2607.17389': ('Yes','No','Algorithms/Software','Not applicable','Experimental',
  'Confirmed: all links are well-known third-party programs used as a compiler test corpus (zstd, cJSON, SmallerC, json-c, chibicc, tmux), no own-code statement found.'),
'2607.17106': ('Yes','No','Algorithms/Software','Not applicable','Theory/Analytical',
  'Confirmed: link (moderngpu) is a third-party GPU library; "data repository" mentions refer to standard external graph benchmark datasets (Stanford Network Repository, SuiteSparse), not own data.'),
'2607.16473': ('Yes','No','Hardware/Fabrication','Not applicable','Experimental',
  'Confirmed: links are Google Coral (hardware platform citation) and HuggingFace pages for third-party pretrained LLMs used as workloads. No genuine availability statement (only a negative mention of lacking a public power-measurement API).'),
'2607.15884': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "codebase and datasets used in this study are publicly available at" statement, repo matches paper method.'),
'2607.15745': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit reproducibility statement ("made publicly available to ensure reproducibility"); repo (astar-batch-selection-CNN, from the original cached scan) matches paper own method name.'),
'2607.14745': ('Yes','Yes','Algorithms/Software','Original (released)','Theory/Analytical',
  'Confirmed: explicit "publicly available in our GitHub repository" statement, repo relates to the paper own algorithmic contribution.'),
'2607.14589': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Simulation',
  'Confirmed ambiguous on full read: no availability statement found despite repo name matching paper title almost verbatim.'),
'2607.14112': ('Yes','No','Theory','Not applicable','Theory/Analytical',
  'Confirmed: the links found are external benchmark datasets being analyzed/aggregated (evaleval/benchmark-saturation, lechmazur/writing), not this paper own new data release.'),
'2607.13630': ('Yes','Yes','Theory','Original (released)','Simulation',
  '[QUANTUM DOMAIN OVERLAP] Quantum-optimization-algorithms paper (quant-ph), pulled into CS via shared "optimization algorithm" keyword. Confirmed: explicit "Data and code availability... available on Zenodo at" statement. Recommend excluding from the final CS-side count -- this is quantum research.'),
'2607.13105': ('Yes','No','Theory','Not applicable','Theory/Analytical',
  '[QUANTUM DOMAIN OVERLAP] Quantum error-correction paper (cat qubits, quant-ph), pulled into CS "coding_theory" via shared "Reed-Solomon code" keyword. Confirmed: no availability statement anywhere; the one link is a hackathon-winner repo, not a formal data release. Recommend excluding from the final CS-side count.'),
'2607.12382': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "Code and Data Availability... publicly available on GitHub at" statement.'),
'2607.12244': ('Yes','Yes','Hardware/Fabrication','Original (released)','Experimental',
  'Confirmed: explicit "source code is available as part of the OpenROAD project" statement -- own contribution integrated into the OpenROAD ecosystem.'),
'2607.11850': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "publicly available at" statement, repo matches paper title exactly.'),
'2607.08746': ('Yes','No','Algorithms/Software','Not applicable','Theory/Analytical',
  'Confirmed: link is Google PAIR own UMAP explainer page, a third-party educational resource, not own code. No availability statement found.'),
'2607.08429': ('Yes','Yes','Algorithms/Software','Derived from external dataset','Experimental',
  'Confirmed: explicit citation of the external VISEM medical dataset, not newly collected. The yolov5 link does not appear in the confirmable full-text context and looks incidental.'),
'2607.07738': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "Data and Code Availability... openly available at" statement, repo matches paper own tool name (Reforge). Ghidra is a third-party tool citation.'),
'2607.07527': ('Yes','Yes','Algorithms/Software','Original (released)','Experimental',
  'Confirmed: explicit "implementation is available at" statement.'),
'2607.05078': ('Yes','Yes','Algorithms/Software','Original (released)','Theory/Analytical',
  'Confirmed: two explicit statements -- a library implementation link plus "code and data needed to reproduce all results, is available at" a repo matching the paper title.'),
'2607.04716': ('Yes','Yes','Theory','Original (released)','Theory/Analytical',
  'Confirmed: multiple self-citation reference-list entries to the authors own prior GitHub repos (consistent "Lcrypto"/"5g-ldpc-min-distance" author pattern), same self-citation style seen repeatedly on the quantum side.'),
'2606.29687': ('Yes','Yes','Theory','Original (released)','Theory/Analytical',
  '[QUANTUM DOMAIN OVERLAP] Quantum-optimization (QAOA) paper, pulled into CS via shared "optimization" keyword. Confirmed: explicit "CODE AND DATA AVAILABILITY... available in the repository" statement. Recommend excluding from the final CS-side count.'),
'2606.29108': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Experimental',
  'Confirmed ambiguous on full read: no availability statement found despite repo (Symbolon) matching paper own tool name exactly. Other links are third-party tools cited as evaluation targets.'),
'2606.28478': ('Yes','Yes','Theory','Original (released)','Theory/Analytical',
  'Confirmed: explicit "Code Availability" statement covering code and data files, repo matches paper title.'),
'2606.26168': ('Yes','Yes','Algorithms/Software','Original (released)','Simulation',
  'Confirmed: explicit "Data/Code available at:" statement, repo matches paper topic exactly.'),
'2606.23838': ('Yes','Yes (partial)','Algorithms/Software','Original (released, partial)','Simulation',
  'Confirmed: raw data is "shared on reasonable request," but code is explicitly open-source at a repo matching the paper title -- genuinely partial release (code open, data gated).'),
'2606.23727': ('Yes','Yes','Theory','Original (released)','Simulation',
  '[QUANTUM DOMAIN OVERLAP] Quantum-optimization/circuit-cutting paper, pulled into CS via shared "optimization" keyword. Confirmed: explicit "Data availability... openly available at" statement. Recommend excluding from the final CS-side count.'),
'2606.23718': ('Yes','No - needs closer look','Theory','Unclear','Simulation',
  '[QUANTUM DOMAIN OVERLAP] QAOA (quantum) paper, pulled into CS via shared "optimization" keyword. No availability statement or repo link confirmed in the full-text re-check (the cached Zenodo DOI candidate was a bare DOI with no protocol prefix, not captured by this pass hyperlink-only check -- worth a follow-up look). Recommend excluding from the final CS-side count regardless once domain status is confirmed.'),
'2606.22210': ('Yes','No - needs closer look','Algorithms/Software','Unclear','Experimental',
  'CORRECTED after full-text re-check: no availability statement and no repo link confirmed anywhere in the fresh full-text read, despite the cached scan having found two candidate links. Recommend a manual open before trusting the original links.'),
'2606.22053': ('Yes','No','Algorithms/Software','Not applicable','Experimental',
  'Confirmed: link is Keras Tuner, a well-known third-party library, not own data. No availability statement found.'),
'2606.22034': ('Yes','No','Theory','Not applicable','Theory/Analytical',
  'Confirmed: the only link is to an unrelated personal project (a Euromillions lottery API wrapper) by the same GitHub username, no evident connection to this paper topic. No availability statement found.'),
'2606.20513': ('Yes','Yes','Theory','Original (released)','Simulation',
  '[QUANTUM DOMAIN OVERLAP] Quantum LDPC decoder paper, pulled into CS "coding_theory" via shared "LDPC code" keyword. Confirmed: explicit "Code availability... is available at" statement, repo (frontier) matches paper own decoder name. PyMatching/tesseract-decoder/BeamSearchDecoder are third-party QEC tool citations. Recommend excluding from the final CS-side count.'),
'2606.20216': ('Yes','No','Algorithms/Software','Not applicable','Experimental',
  'Confirmed: the explicit statement found is about the ABSENCE of public baseline implementations ("no publicly available implementations found online, therefore we implemented ourselves"), not an offer to share their own new code.'),
'2606.18418': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Experimental',
  'Confirmed ambiguous on full read: no availability statement found despite repo (p2ce) matching paper own method name exactly.'),
'2606.18281': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)','Theory/Analytical',
  'Confirmed ambiguous on full read: no availability statement found despite repo (crsurvlearners) matching paper topic closely.'),
}

path = 'data/cs_review_queue_link_found.csv'
with open(path, newline='') as f:
    rows = list(csv.reader(f))
header = rows[0]
idx_id = header.index('arXiv ID')
idx_type = header.index('Research Type')
idx_sim = header.index('Simulated/Experimental')
idx_source = header.index('Data Source')
idx_verified = header.index('Verified')
idx_label = header.index('Corrected Label')
idx_notes = header.index('Notes')

updated = []
for row in rows[1:]:
    aid = row[idx_id]
    if aid in J:
        v, l, t, s, sim, n = J[aid]
        row[idx_verified] = v
        row[idx_label] = l
        row[idx_type] = t
        row[idx_source] = s
        row[idx_sim] = sim
        row[idx_notes] = n
        updated.append(aid)

with open(path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerows(rows)

print('updated', len(updated), 'rows')
missing = [k for k in J if k not in updated]
print('not found in file (check IDs):', missing)

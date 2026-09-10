import csv

# (Verified, Corrected Label, Research Type, Data Source, Notes)
J = {
'2607.12118': ('Yes','Yes','Theory','Original (released)',
  'Explicit DATA AVAILABILITY: data deposited in Zenodo (10.5281/zenodo.21336494). QEC decoder study for defective qubit arrays.'),
'2607.08767': ('Yes','Statement only - restricted','Algorithms/Software','Original (restricted)',
  'DATA AVAILABILITY says data "available from the authors" (request-based, not a direct link). Plaquette is explicitly a COMMERCIAL product of QC Design; a Zenodo DOI was found as a candidate link but its exact context needs closer manual check to confirm what it actually covers. Flag for closer look.'),
'2607.01085': ('Yes','Yes','Theory','Original (released)',
  'Explicit DATA AND CODE AVAILABILITY, GitHub repo name (fisher_glass_data) matches project. Borderline domain: general quenched-sensor metrology theory covering NV centers, SC qubits, and spin qubits together, not SC-qubit-exclusive -- kept in-domain since SC qubits are explicitly one of the studied systems, not just background citation.'),
'2606.22853': ('Yes','No','Theory','Not applicable',
  'FALSE POSITIVE: github.com/PECOS-packages/PECOS is a well-known third-party open-source QEC simulator, cited as a tool used for the exhaustive code search, not this paper own data/code. No availability language found anywhere in text.'),
'2606.21762': ('Yes','Yes','Algorithms/Software','Original (released)',
  'Explicit CODE AVAILABILITY, GitHub repo name (UTrack.jl) matches paper method name (Universal optimal Tracking). Genuine own release.'),
'2606.20441': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: two Qiskit-org GitHub links (qiskit-addon-pna, samplomatic) found but NO explicit data/code availability statement text detected anywhere. Repo names are plausibly their own IBM-released contribution, or could be pre-existing Qiskit tooling they used. Recommend a manual open-and-check rather than trusting either guess.'),
'2606.18755': ('Yes','No','Theory','Not applicable',
  'FALSE POSITIVE: github.com/qgrad/qgrad is a general third-party gradient-based quantum control package, cited as a tool, not own data. No availability language found.'),
'2606.17866': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit DATA AVAILABILITY: 4TU data repository DOI + GitHub repo (andersenqubitlab/fluxonium-mist), same lab as the flip-chip paper verified earlier in session. Genuine release.'),
'2606.16854': ('Yes','Yes','Theory','Original (released)',
  'Explicit Data Availability AND Code Availability sections, both pointing to real Zenodo DOIs. Quantum simulation of 3D Ising criticality with real experimental gate-fidelity data (98-99% CZ fidelities) -- has real hardware-experiment character despite Theory classification.'),
'2606.13010': ('Yes','Yes','Control Electronics','Original (released)',
  'Explicit DATA AND CODE AVAILABILITY, two Zenodo DOIs plus authors own GitHub repo (amachino/qubex) alongside related infrastructure repos (e7awg_sw, qube-calib, quelware) -- genuine, well-documented release of an integrated control hardware/software system.'),
'2606.10970': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit DATA AVAILABILITY: "publicly available" with real Zenodo DOI. Flux-crosstalk characterization study.'),
'2603.09870': ('Yes','Yes','Theory','Original (released)',
  'Explicit DATA AVAILABILITY: numerical data via 4TU data repository DOI + GitHub repo (andersenqubitlab/crosstalk-in-larger-fluxonium-processors), same lab (AndersenQubitLab) as two other papers in this batch. Genuine release.'),
'2512.04990': ('Yes','No','Algorithms/Software','Not applicable',
  '[REVIEW/TUTORIAL ARTICLE] Title is "Introduction to quantum control" -- a tutorial-style book chapter, not primary research. FALSE POSITIVE on data: only link is to nlopt, a general third-party optimization library citation, no availability statement.'),
'2511.22930': ('Yes','Statement only - placeholder DOI','Characterization/Metrology','Original (pending)',
  'Data/materials availability statement exists but the cited Zenodo DOI is a literal placeholder ("10.5281/zenodo.xxxxxxx", not yet assigned) -- data is not actually retrievable via that link at the time of this preprint version. Claimed but not yet functional.'),
'2511.22580': ('Yes','Likely Yes - needs confirmation','Algorithms/Software','Original (released, unconfirmed)',
  'No explicit "data availability" section detected in the keyword scan, but the single link found (github.com/LeoVanDamme/GRAPE_SCQ) strongly name-matches the paper subject (GRAPE-optimized gates for Superconducting Qubits). Plausible genuine own release without a formally labeled availability section -- worth a quick manual open to confirm the repo actually contains this paper code before marking fully verified.'),
'2511.12227': ('Yes','Statement only','Theory','Not applicable',
  'Data availability statement says data is "included in the article and supplementary" material -- not an external repository. The GitHub link found (DiCarloLab-Delft .../Starmon7_FactSheet.pdf) is a hardware factsheet citation for the processor used, unrelated to this paper own data.'),
'2511.08336': ('Yes','Yes','Theory','Original (released)',
  'Explicit "openly available" Data Availability statement with real Zenodo DOI. The GitHub link (epsteinlib) is a third-party math library citation used for calculations, not their own data -- own data is the Zenodo entry.'),
'2510.26845': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: a Zenodo DOI link was found, but no explicit data-availability keyword phrase was detected anywhere in the text -- unusual combination, suggests the DOI may be a citation to a third-party tool rather than a data statement. Recommend manual check.'),
'2510.22001': ('Yes','Yes','Theory','Original (released)',
  'Explicit Data Availability: "found on our GitHub repository" (JacobSPalmer/quantum-ddq-toolkit). Clear genuine own release.'),
'2510.18145': ('Yes','Yes','Theory','Original (released)',
  'The "Code and data for Altermon..." hit is a self-citation reference entry (same pattern as the flip-chip paper verified earlier: authors cite their own Zenodo deposit as a numbered reference) rather than a third-party citation. Genuine own release.'),
'2510.08894': ('Yes','No','Algorithms/Software','Not applicable',
  'FALSE POSITIVE: github.com/Qiskit-Extensions/circuit-knitting-toolbox is IBM official general-purpose Qiskit tooling, cited as a comparison/baseline tool, not own data. No availability language found.'),
'2604.25884': ('Yes','Yes','Algorithms/Software','Original (released)',
  'Explicit Data and Code Availability: benchmark dataset on HuggingFace, evaluation code on GitHub, model weights on HuggingFace, all under the nvidia org matching the paper own benchmark name (QCalEval). Strong, complete, genuine release.'),
'2604.24912': ('Yes','No - needs closer look','Algorithms/Software','Unclear',
  'AMBIGUOUS: paper is explicitly "Data-Driven" in title (meta-learning framework named HAML) but the only link found (volkerkarle/UnitaryTransformations.jl) does not obviously match that name and may be a dependency-library citation. No availability statement text found. Recommend manual check given the title emphasis on data.'),
'2604.11722': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: a Zenodo DOI candidate link exists but no data-availability keyword phrase was found. Recommend manual check.'),
'2604.09796': ('Yes','Yes','Hardware/Fabrication','Original (released)',
  'Explicit DATA AVAILABILITY: "openly available" with real Zenodo DOI. A second link (aewallin/allantools) is a well-known third-party Allan-deviation analysis library citation, not own data.'),
'2604.02809': ('Yes','Yes (partial)','Characterization/Metrology','Original (released, partial)',
  'Explicit DATA AVAILABILITY: source data files on figshare (real, direct link), but text also says "other data are available from [request]" -- meaning part of the dataset is open, part is request-gated. Worth noting as partial release, not full.'),
'2603.29525': ('Yes','Statement only - promised, not yet available','Theory','Original (pending)',
  'Data/Code availability sections state data "will be deposited at a public archival repository (Zenodo or figshare) upon acceptance" -- an explicit future promise, not currently available at this preprint stage. Distinct from a placeholder-DOI case: here nothing is deposited yet at all.'),
'2603.16203': ('Yes','Likely Yes - needs confirmation','Control Electronics','Original (released, unconfirmed)',
  'Title explicitly frames this as "A Scalable Open-Source QEC System" -- own system likely released as yale-paragon/EosCore (matches a Yale-affiliated author group naming pattern). The other link (RISC-Q) appears alongside ARTIQ/QICK/QubiC in a sentence discussing existing open-source frameworks generally, likely a citation to a different, pre-existing tool rather than their own. Worth a quick manual confirm on which repo is actually theirs.'),
'2603.13837': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: single link (dkweiss31/floquet) with no accompanying availability statement -- could be a personal general-purpose Floquet-simulation library citation rather than paper-specific data. Recommend manual check.'),
'2603.08801': ('Yes','Yes','Algorithms/Software','Original (released)',
  'Three GitHub links all under the same "clelandlab" org (HAL, Grapher, QuICK) -- these read as the authors own lab prior open-source tool releases, cited as supporting infrastructure for this new LLM-assisted framework, not third-party citations.'),
'2603.03157': ('Yes','Yes','Theory','Original (released)',
  '[NOT QUANTUM COMPUTING DOMAIN] Explicit "openly available" Data Availability statement -- genuine release exists, but this is a dark-matter/axion search paper using a transmon as a quantum sensor, not a computing application (same category as the earlier gravitational-wave detection paper). Which of the 3 candidate links (axion-limits plotting tool vs 2 Zenodo DOIs) is the actual own-data reference needs a quick manual confirm.'),
'2602.22117': ('Yes','Statement only','Characterization/Metrology','Original (restricted)',
  '[BORDERLINE DOMAIN] DATA AVAILABILITY says data "available from the [authors/upon request]" (request-based, weak). GitHub link (steelelab-delft/stlab) is the lab general-purpose measurement software framework used across many papers, not this paper specific dataset. Domain: mechanical resonators coupled to SC circuits -- same borderline bucket as the earlier phononic-crystal/optomechanics papers, no qubit computation demonstrated.'),
'2602.20002': ('Yes','Yes','Hardware/Fabrication','Original (released)',
  'Explicit "openly available" Data availability statement with real Zenodo DOI. Room-temperature JJ tuning study.'),
'2602.19671': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit DATA AVAILABILITY: source data deposited on Zenodo, real link. Magnon squeezing enabled via dispersive magnon-SC-qubit coupling -- kept in-domain consistent with earlier precedent (qubit is an explicit physical mechanism, not incidental).'),
'2602.04831': ('Yes','No','Algorithms/Software','Not applicable',
  '[REVIEW ARTICLE] Title explicitly "Review of Superconducting Qubit Devices...". FALSE POSITIVE: the only link is the same Zenodo DOI (10.5281/ZENODO.4618153) as the Qiskit Metal citation seen in the earlier neural-network qubit-design paper -- confirms it is a citation to that software tool, not this paper own data. The one keyword hit ("hosted at") is an unrelated false trigger about dilution-refrigerator cooling power.'),
'2602.04719': ('Yes','No','Algorithms/Software','Not applicable',
  'FALSE POSITIVE: the only textual match is a reference-list citation to an existing Qiskit-community tool ("povm toolbox"), not a data availability statement. No explicit availability language found anywhere else.'),
'2601.07825': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit Data and code availability: "available in the manuscript or the supplementary material or are deposited at Zenodo". Real demonstrated two-qubit gates via mechanical resonator -- kept in-domain (actual gate implementation shown, not just an interconnect proposal).'),
'2601.02183': ('Yes','No','Theory','Not applicable',
  '[REVIEW/PERSPECTIVE ARTICLE] Explicitly labeled "This Perspective" in the abstract. FALSE POSITIVE: only link (PsiQ/bartiq) is PsiQuantum third-party resource-estimation tool citation; the one keyword hit is a citation to Preskill lecture notes, unrelated to this paper data.'),
'2512.19685': ('Yes','Yes','Algorithms/Software','Original (released)',
  'Explicit Code availability with own GitHub repo (tvle2/qcss-partition) plus datasets on Zenodo, both clearly stated together in one sentence. Genuine complete release.'),
'2512.18198': ('Yes','Yes','Hardware/Fabrication','Original (released)',
  '"Designs hosted at" GitHub, matches lab name (Boulder-CryogenicQuantum-Testbed). Genuine release of hardware design files.'),
'2512.18156': ('Yes','Statement only - placeholder DOI','Theory','Original (pending)',
  'Data availability statement exists but cited Dryad DOI is a literal placeholder ("10.5061/dryad.XXXXXXXXX", not yet assigned) -- same pattern as 2511.22930. Claimed but not yet functional at this preprint stage.'),
'2512.14513': ('Yes','Yes','Theory','Original (released)',
  'Explicit DATA AVAILABILITY with real Zenodo DOI.'),
'2512.07808': ('Yes','Yes (mixed)','Control Electronics','Derived from external dataset + own code',
  'Text explicitly says they use "the publicly available superconducting-qubit readout dataset" -- an existing external dataset, not newly collected. A Zenodo DOI candidate link likely covers their own FPGA/architecture code release separately from that reused dataset. GitHub link (Xilinx/logicnets) is a third-party FPGA tool citation. Worth noting this is a mixed case: own code plausibly released, underlying training data is reused from elsewhere.'),
'2512.02284': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: the only candidate link is the exact same Zenodo DOI (10.5281/zenodo.11398048) that also appeared in the unrelated Plaquette paper (2607.08767) in this same batch -- a duplicate DOI across two different papers strongly suggests a generic/shared citation (e.g. a common tool or format reference) rather than paper-specific data, but this needs manual confirmation since no availability statement text was found either way.'),
'2606.07339': ('Yes','Statement only','Characterization/Metrology','Original (restricted)',
  'DATA AVAILABILITY says data "available from the [authors/upon request]" (request-based, weak). GitHub link (hmmlearn/hmmlearn) is a well-known third-party Hidden Markov Model Python library citation, not own data.'),
'2606.02761': ('Yes','Yes','Theory','Original (released)',
  'Explicit "Code and data availability" statement with real Zenodo DOI. Materials theory for altermagnetic Josephson junctions.'),
'2605.19854': ('Yes','No - needs closer look','Theory','Unclear',
  'AMBIGUOUS: a Zenodo DOI candidate link exists but no data-availability keyword phrase was found anywhere in the text. Recommend manual check.'),
'2605.15554': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit Data availability statement: experimental data AND COMSOL simulation model files, real Zenodo DOI link.'),
'2605.12588': ('Yes','Yes','Theory','Original (released)',
  'Explicit "Code and data availability in Zenodo" statement with real DOI. Andreev-quasiparticle-based spinmon qubit theory proposal, same family as the earlier Andreev spin qubit paper kept in-domain -- no flag needed.'),
'2605.06372': ('Yes','Yes','Characterization/Metrology','Original (released)',
  'Explicit DATA AND CODE AVAILABILITY, self-citation reference entries to own 4TU data repository + GitHub (AndersenQubitLab/coherence_cos2phi_transmon) -- same lab as several other papers in this batch, same genuine self-citation pattern as the flip-chip paper.'),
}

path = 'data/review_queue_link_found.csv'
with open(path, newline='') as f:
    rows = list(csv.reader(f))
header = rows[0]
idx_id = header.index('arXiv ID')
idx_type = header.index('Research Type')
idx_source = header.index('Data Source')
idx_verified = header.index('Verified')
idx_label = header.index('Corrected Label')
idx_notes = header.index('Notes')

updated = []
for row in rows[1:]:
    aid = row[idx_id]
    if aid in J:
        v, l, t, s, n = J[aid]
        row[idx_verified] = v
        row[idx_label] = l
        row[idx_type] = t
        row[idx_source] = s
        row[idx_notes] = n
        updated.append(aid)

with open(path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerows(rows)

print('updated', len(updated), 'rows')
missing = [k for k in J if k not in updated]
print('not found in file (check IDs):', missing)

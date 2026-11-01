# Running threads

## Widening the therapeutic window of T-cell engagers
Can CD3-redirected killing be confined to tumour cells, and which lever — affinity, format geometry, logic gating, or effector choice — actually does the work?

- Eps 28, 48 and 54 pursue conditional assembly or activation: CD33-gated induction of an anti-CD123 CAR (28), split single-chain Fab prodrugs that exchange chains only on antigen-positive cells (48), and synapse-gated affinity-tuned trispecifics (54). None reported quantified normal-tissue sparing in vivo in the material we had.
- Eps 63 and 69 attack the same problem biophysically: a CDRL3 allosteric pH switch giving a 789-fold binding difference between pH 6.5 and 7.4 (63), and a 2+1 avidity format that kills at ~1,000 EGFR/cell while covering cetuximab-resistance variants (69) — though 69 concedes normal epithelium carries 40,000–100,000 EGFR/cell.
- Ep 71 is the only clinical datapoint: IMA401's deliberately low-affinity CD3 arm gave 38% CRS, all grade 1–2, zero ICANS, and 20% ORR at RP2D — evidence the affinity-attenuation route survives first-in-human.
- Eps 60 and 76 change the effector rather than the targeting arm: Vγ9Vδ2 engagement spared 5T4-positive healthy tissue (60), and a CD2 costimulator restored killing at sub-efficacious TCE doses with ≤2-fold IL-6/TNF rises versus up to 200-fold for CD28 (76). Eps 88 and 92 move the same lever off CD3 entirely: dropping the TfR1 arm from ~0.1 nM to 124 nM kept ~85% CCR6 degradation while stopping co-degradation of TfR1 itself (88), and a tetravalent IL-10R agonist hit 2.1 pM on myeloid TNF suppression while staying silent in T cells because its geometry gated signalling on receptor density (92) — a 2- to 18-fold margin, no more generous than Ep 69's.
- Ep 86 shows the format arithmetic is not yet solved even for a one-domain binder: its C11–OKT3 single-chain bispecific ran as a monomer plus a mispaired non-covalent dimer, the dimer beat the monomer at low concentrations, N-terminal placement of the nanobody beat C-terminal, and antigen-independent killing at high dose was only reduced by a two-mutation variant that also cut potency.
- Eps 59 and 83 add the format-arithmetic problem: recruiting myeloid cells into the T-cell/tumour synapse beat a matched bispecific but without a cytokine profile at equi-efficacious doses (59); and in 83 the lead TCR-mimic's monomeric IgG affinity (~0.1 nM) versus the monovalent Fab in the CD3 bispecific (35 nM pHLA, 14.6 nM CD3) leaves the avidity loss on reformatting unaddressed.

Watch for: any of these designs tested against a matched, non-gated, non-attenuated control in the same model — most claims so far are versus the parental molecule, not versus simple affinity reduction, and Eps 88 and 92 compare a weak effector arm only against a strong one.

## Does peptide–HLA targeting survive contact with the proteome?
Targeting an intracellular antigen means targeting a short peptide on an HLA allele — can that recognition be shown specific enough to redirect T cells safely?

- Ep 23 (MUNIS, >650,000 HLA class I ligands, bimodal binding-plus-processing model, validated on EBV) and Ep 67 (deep peptide recognition profiles from ~10⁹-member yeast libraries for 21 HLA-B*27:05 TCRs, used to predict activation and nominate autoantigens) both establish that recognition is a motif over many peptides, not a single sequence.
- Ep 74 builds binders the other way — ProteinMPNN-guided design plus yeast display for TCR-like antibodies to KRAS G12D on HLA-C*08:02 — but the display step did the real selection work, and AlphaFold2 failed on the interface.
- Ep 83 supplies the sharpest negative result: of 26 WT1/HLA-A*02:01 antibodies with clean SPR and 25/26 non-binding to MAGE-A4 on the same allele, 13 bound off-target M13L and 14 bound PIGQ on peptide-pulsed T2 cells, with only 8 binding neither; X-Scan phage display across 172 nine-mer substitution variants showed the lead depended on positions 3,4,6,7,8 while comparators ESK1 and 11D06 tolerated substitutions broadly, and proteome homology search from those footprints returned only the target peptide for the leads versus 4–12 candidates for the comparators.
- Ep 83's bispecific then killed endogenous WT1+/HLA-A2+ TF-1 and SET-2 at sub-nanomolar EC50 in two donors — but the authors state outright that a WT1-negative, HLA-A2-positive killing control was not run, and the proteome off-target list was never synthesised and tested.
- Ep 86 sidesteps the polymorphism half of the problem and inherits the other half: MR1 is near-non-polymorphic and presents a defined microbial metabolite, so C11's 1.8 nM binding to MR1–5-OP-RU against ~20 µM for the Ac-6-FP complex is ligand discrimination with a structural basis (CDR3 Ser100 to the ribityl hydroxyl; CDR1 flipped out and buried surface 1,155 → 830 Å² on the wrong ligand) — but every tumour-killing experiment pulsed targets with 10 µM synthetic antigen, the same stringency-test-not-density move as Ep 83's 50 µM peptide pulsing, and C11 bound pyridoxal-pulsed cells weakly.
- Ep 71 is where the stakes land: a TCER against a MAGE-A4/MAGE-A8 peptide dosed into 61 patients, i.e. this specificity question is already being answered in humans rather than on T2 cells.

Watch for: a WT1-negative/HLA-A2-positive cytotoxicity control, and whether algorithmically predicted proteome off-targets bind when actually synthesised and pulsed — the two experiments that would convert a mutational-tolerance motif into a specificity claim. Ep 86's version of the same bar: a target presenting an endogenous ligand at native density, killed with a knockout arm in the same assay.

## Does in silico design earn trust before the wet lab?
How much of protein and antibody engineering can be decided computationally, and what does honest validation look like?

- Ep 81 is the anchor: a blinded prospective benchmark where a non-ML positional consensus placed third (540 pM, perfect developability), only ~10–14% of AI cluster-ranking entries beat the most-abundant-clone heuristic, and the top 2.9 pM design outright failed HIC.
- Eps 17, 19, 45, 67 and 74 all report hybrid wins — theory-derived features feeding gradient-boosted trees (45), single-mutation data plus evolutionary priors in augmented ridge regression (19), AbMAP's 82% hit rate on SARS-CoV-2 binders (17), pLMs fine-tuned on billion-member yeast-display recognition profiles (67), and ProteinMPNN seeding a yeast-display library that then did the real work (74, where AlphaFold2 failed to predict the interface).
- Ep 1 is the cautionary case: AF-cluster's metamorphic-protein predictions were no better than random MSA subsampling, with confidence scores inconsistent with the predicted conformations. Ep 2 sits at the far end — an entirely computational vaccine design with no wet step at all.
- Eps 70, 36, 27 and 46 push scaling and transfer claims (log-linear contact-prediction gains to 6B parameters, 70; threading plus deep-learning restraints, 36; AlphaFold distances as restraints for disordered ensembles capped at 22 Å, 27; a transferable coarse-grained force field, 46) — none benchmarked blind against the others.

- Ep 90 is the second blinded prospective benchmark and it indicts the scoring layer, not the generators: across 12,000 CD20 minibinders from 28 teams, team hit rates ran 0.6% to 38.4%, 42% of designs vanished from the pool, 98.9% of those dropouts came from MPNN pipelines, and pLDDT, ipTM, Rosetta interface energy, ProteinMPNN likelihood and ESM-2 pseudo-log-likelihood all predicted nothing while a lysine-glutamate-helix feature separated recovered from non-recovered at 0.91 AUC and a plain DNA-composition filter nearly doubled the functional hit rate.
- Ep 86 is the control case for how much of this is design at all: a ~1,500-fold affinity gain came from error-prone PCR plus a stepped-monomer sort, with no model anywhere in the loop.

Resolution: blinded, prospective, experimentally-scored challenges like Ep 81's and Ep 90's, run on data-poor antigens rather than the most-sequenced target available — and, from Ep 90, a prospective re-run at ProteinMPNN temperature 1.0 to test whether the shared failure mode is really the sampler's amino-acid bias.

## The tumour microenvironment as the real checkpoint
If PD-1 blockade fails in most solid tumours, which non-canonical feature of the microenvironment is responsible?

- Eps 6, 37 and 50 each nominate a different suppressor: mechanical stiffness acting through Piezo1→Osr2 to drive exhaustion (6), glioblastoma-instructed astrocytes blunting tumour-specific T cells (37), and cancer-induced nerve injury promoting anti-PD-1 resistance (50).
- Ep 8's Three Cs review (Camouflage/Coercion/Cytoprotection) is the framework the others get slotted into — and it concedes that intratumoral heterogeneity may mean different regions rely on different Cs.
- Ep 5 adds a dimension the others ignore: TIL number, PD-1 expression and exhaustion ratio oscillate across the day under endothelial-clock control, with timed dosing changing efficacy.
- Eps 3 and 57 argue immune composition matters as much as suppression — an HLA-DR+ antigen-presenting neutrophil state driven by leucine metabolism (3), and MCPyV-associated spatial myeloid–CD8 aggregates rather than diffuse infiltrate (57).
- Ep 65 treats the barrier as physical rather than immunological, downregulating Claudin-5/Occludin/ZO-1 to let CAR T cells into glioblastoma — but only in a flank xenograft with no real BBB.

Watch for: spatially resolved profiling that shows one dominant evasion mechanism per region and predicts which patients fail ICB — Ep 8 flags this as the open test and nobody has run it.

## Engineering the delivery vehicle instead of the drug
Several episodes argue the payload is solved and the bottleneck is getting it to the right cell in the right state.

- Eps 7, 10 and 26 convert something already in or near the tumour into the therapeutic: PIB-reprogrammed tumour cells become cDC1-like vaccines (7), engineered E. coli Nissle delivers neoantigens to the cytosol via listeriolysin O (10), and iPSC-derived M1 CAR macrophages kill by apoptosis plus efferocytosis (26).
- Eps 65 and 78 build the vehicle in situ: an oncolytic adenovirus secreting an IL-13Rα2xCD3 BiTE (65), and galactose-oxidase-driven covalent anchoring of self-assembling anti-CD3 nanostructures onto PD-L1 glycans, dropping the peptide's critical aggregation concentration from 38.26 to 2.18 µM (78).
- Eps 9, 24 and 51 solve the allogeneic and trafficking problems: FGxGT motif mutation decoupling TCR recognition from CD3 signalling (9), triple knockdown of CD11a/CD49d/PSGL1 to block extravasation into normal tissue while keeping tumour killing (24), and glycan shielding claiming TCR knockout is unnecessary (51).
- Eps 18 and 35 are the non-cancer cases: non-cationic 9-mer CPPs selected by cathepsin counter-selection for cytosolic escape (18), and a bespoke LNP base editor dosed in one infant with CPS1 deficiency (35).

- Ep 88 hijacks a vehicle that is already running: tethering a GPCR to constitutively cycling transferrin receptor 1 routes it to the lysosome, which turned a nanobody with only modest signalling inhibition at micromolar into a 30 pM RXFP1 antagonist with the same binding arm, and worked on constitutively active EBV BILF1 that no neutralising antibody could address.

Resolution: almost all of these are preclinical (26 explicitly notes CAR-iMACs do not persist in vivo; 24's in vivo separation was weaker than in vitro; 88's only in vivo model was six days in receptor-transgenic mice with both arms handicapped). The thread advances when one reaches a first-in-human readout.

## Taking the brakes off immunity — where does it break?
Every inhibitory pathway that protects tumours is doing something useful elsewhere; what is the cost of removing it?

- Ep 4 makes the tension explicit: ITPRIPL1 is testis-enriched and its knockout increases testicular T cell infiltration, so systemic blockade risks immune-privilege breakdown.
- Ep 33 moves a checkpoint out of oncology entirely — microglial TIM-3 restrains amyloid-β phagocytosis, and its deletion reduced plaque burden in 5xFAD mice, but removing a CNS inhibitory receptor raises unaddressed neuroinflammation risk.
- Ep 21 shows the tradeoff within a single pathway: scratch-induced substance P→MrgprB2 mast cell activation drives both allergic inflammation and protection against *S. aureus*.
- Ep 25 quantifies the price in a trial: obinutuzumab improved complete renal response (46.4% vs 33.1%) but raised serious adverse events to 32.4% vs 18.2%, mostly infections.
- Eps 86 and 92 run the ledger in both directions. Blocking an infection sensor has a price: C11 suppressed MAIT accumulation in Francisella-infected mice and raised splenic bacterial burden toward MR1-deficient levels, and the authors twice name unknown steady-state MR1–5-OP-RU display at barrier surfaces as the on-target safety question (86). Adding a brake has the mirror problem: IL-10's clinical window closed because the same agonism that suppresses myeloid TNF activates T and B cells, and the fix — making signalling strictly TYK2-dependent — designs in a drug-drug interaction with TYK2 inhibitors already in clinical use that the paper does not discuss (92).
- Ep 22 is the same accounting in a different modality: ARIA is the dominant liability of anti-amyloid antibodies, forced higher by poor BBB penetration, and gantenerumab cleared amyloid without cognitive benefit.

Watch for: whether any of these can be split pharmacologically — Ep 21's open question (separating the allergic from the antibacterial arm downstream of mast cell activation) is the cleanest formulation.

## What counts as causal evidence outside the lab
Several episodes lean on design rather than randomisation; the recurring question is when that is enough.

- Eps 32, 73 and 80 are the strong cases: a birthdate discontinuity with the effect appearing for dementia and not other outcomes (32), occupation-level WFH exposure instrumented with the pre-pandemic Dingel–Neiman index giving a 1.3% employment gain per point of WFH and 68–85% of the disability employment rise (73), and registry-linked conscription scores revealing SES-staggered Flynn reversals that cancelled in the national mean (80).
- Eps 66 and 79 show the limits: half the conservative–liberal comorbidity divergence is unexplained by observable sorting, and the trust mechanism comes from a separate 2024 survey, not the same individuals (66); a 1-second maternal vocal response window predicts later ADHD/DBD in 158 dyads, but with six autism cases and degraded VHS audio (79).
- Eps 42 and 55 are observational designs where the causal question is untested — soil and cherry microbiome predicting coffee flavour without inoculation trials (42), and guideline-era exposure standing in for individual adherence to early allergen introduction (55).
- Ep 82 is the extreme of inference from a found sample: three undiagnosed rabies deaths among 239,251 deceased organ donors scale to ~34 US rabies deaths a year and ~7% surveillance detection — but the whole numerator is n = 3, the CI (213–2,220 deaths) captures only Poisson noise, and the load-bearing assumption is that donors carry average national risk. Its virtue is stating the falsification bar numerically (donors would need ~14-fold elevated rabies risk), which Eps 42, 55 and 66 never do.
- Eps 72 and 77 randomise the exposure instead: preregistered elite-rhetoric quotes shifting Trump voters toward censorship support while non-Trump voters backlashed (72), and anonymised text negotiations where observers guessed gender at 43% — worse than chance — yet women still generated higher subjective value (77).
- Ep 11's SURD framework, with its redundant/unique/synergistic decomposition and "causality leak" term, is the methodological backbone the show keeps reaching for, though it had no applied-domain demonstration in the notes.

Watch for: whether Ep 73's effect reverses under return-to-office mandates; whether Ep 82's estimate survives its own proposed direct test (a defined-denominator series of unexplained fatal encephalitis deaths assayed for rabies); and whether Eps 87 and 89, which audit found data against a definition rather than randomising anything, are ever given a counted baseline.

## Does the instrument decide the finding?
Before asking what an estimate identifies, ask whether the instrument that produced it could have returned a different answer.

- Ep 84 is the best-disciplined case and still shows the problem: 4.9% of non-Hispanic white adults endorsed white nationalism (CI 3.6–6.2; 13.5% among white men 18–29), with pre-set equivalence tests retiring the status-threat predictors — but reverse-keyed wording moved endorsement 9 points, and the NORC response rate was 2.7% with non-responses coded "no."
- Ep 91 is the sharpest version, because the headline is an absence: 29 of 31 young men spontaneously described anxiety and 26 described shame, but the guide never asked how sex feels and four of its seven questions pointed at uncertain or non-consensual encounters, which is exactly the instrument that would manufacture an absence of described enjoyment. The authors say the counts are spontaneous mentions in one self-selected cohort, not prevalence.
- Ep 93 measured the exposure per person and still with the wrong instrument: a 124-item questionnaire built to estimate nutrients, not processing, with ambiguous items assigned from population-level data, a validity coefficient of 0.66, and a null taken across an interquartile range of 36–50% of energy from ultra-processed food.
- Eps 87 and 89 are missing the yardstick rather than the measurement. Ep 87 shows wording move deportation support 14 points (52% → 38% once consequences are named) and group-specific support run 97% to 5%, yet never states what vote share or poll margin would have counted as a mandate; Ep 89 calls congressional inaction a historic departure with no counted series of hearings, riders or termination votes to place it against.

Watch for: an estimate reported alongside a prespecified instrument check — the discipline Eps 93 and 82 show when they name the confounding or risk multiple that would overturn them (2.1-fold, 14-fold) and Eps 87, 89 and 91 do not.

## Is the dominant framework in a field actually load-bearing?
A recurring meta-thread: when do accumulated anomalies mean a paradigm should be replaced rather than patched?

- Ep 31 argues the somatic mutation theory of cancer has failed, citing driver mutations in histologically normal tissue and cancers with no identifiable drivers — while conceding it offers no falsification criteria for its cell-state alternative.
- Ep 12 complicates both sides: ecDNA species co-segregate non-randomly via intermolecular interactions and transcription, which is genetic but not Mendelian, and shapes targeted-therapy response.
- Ep 34 is the model of how to do this properly — a preregistered adversarial collaboration where neither GNWT nor IIT passed in full, forcing revision rather than confirmation of either. Ep 41 supplies the older version of the same worry: objective reduction works by moving away from the subjective viewpoint, which is precisely what consciousness research must explain.
- Ep 38 offers a candidate reframe — cross-tissue multicellular coordination rewired in cancer — but the supplied material had no cohort sizes or statistics to assess it.
- Ep 70's "world model" claim is the newest instance: layer-wise decoupling of function and structure is argued as evidence of internal organisation, not demonstrated by causal intervention on the model's features.

- Ep 93 is the cleanest test of a category rather than a theory: total ultra-processed intake was unassociated with colorectal cancer (HR 0.97, top vs bottom quintile) while its components split along ordinary dietary guidance — calcium 0.77 per 300 mg/day and fibre 0.72 per 10 g from UPF sources against meat 1.08 per serving — which is what you would see if Nova group 4 is not the causally relevant unit. The authors could not test the additive mechanism the category is usually defended by.
- Ep 90 is the same question asked of a field's instruments rather than its theories: the confidence scores the design community ranks on carried no signal, and a DNA-composition statistic did.

Watch for: Ep 31's unanswered challenge — why mutation-targeted therapies work at all if mutations are not causal — whether any successor framework adopts Ep 34's preregistered adversarial format, and whether an ultra-processing study ever separates processing from composition (Ep 93).

## Antibody format, size, and the penetration–residence tradeoff
Does molecular architecture, independent of affinity, determine where an antibody goes and what it does?

- Ep 40's three-paper survey sets the tradeoff: transport into tumour competes with systemic and antigen-mediated clearance, small formats penetrate better but clear faster, and size is a principal determinant of fragment biodistribution.
- Eps 47 and 52 locate function in geometry rather than binding strength — domain rearrangement on dual antigen engagement as the source of activity enhancement (47), and hinge plasticity in intact IgG (52, DOI only; numbers still need backfilling).
- Eps 88 and 92 are the strongest form of the geometry claim because the binders are held fixed. Reversing the order of two nanobodies on one arm abolished IL-10R signalling and a symmetric variant was a better myeloid agonist that brought back ~20% of native IL-10's T cell response, with a 3.14 Å cryo-EM map rather than a simulation behind it (92); and optimal target-to-TfR1 valency differed for every receptor tested — 2:1 for RXFP1, bivalent TfR1 for AT1R, 1:1 for CCR6 (88).
- Ep 44 moves the lever outside the CDRs entirely, tuning stability and function via rational framework mutations, with the unresolved risk that non-germline framework residues raise immunogenicity.
- Ep 63's pH switch is the same principle in a different guise: the causative mutations (T89LD, Q90LE) do not contact antigen, acting through loop rigidification and a ~2° VH/VL tilt — both inferred from constant-pH simulation, not structures at both pH values.
- Ep 81 supplies the discipline check — developability was scored across five assays, and a composite threshold let a 2.9 pM design pass despite an outright HIC failure.

Resolution: matched-format, matched-affinity head-to-heads in a single tumour model, plus experimental structures at both states for the rearrangement and pH-switch claims — Ep 88's pH experiment is the counter-example, since the His31-to-alanine mutation that removed pH sensitivity also reduced binding, leaving the two confounded.

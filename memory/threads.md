# Running threads

## Widening the therapeutic window of T-cell engagers
Can CD3-redirected killing be confined to tumour cells, and which lever — affinity, format geometry, logic gating, or effector choice — actually does the work?

- Eps 28, 48 and 54 pursue conditional assembly or activation: CD33-gated induction of an anti-CD123 CAR (28), split single-chain Fab prodrugs that exchange chains only on antigen-positive cells (48), and synapse-gated affinity-tuned trispecifics (54). None reported quantified normal-tissue sparing in vivo in the material we had.
- Eps 63 and 69 attack the same problem biophysically: a CDRL3 allosteric pH switch giving a 789-fold binding difference between pH 6.5 and 7.4 (63), and a 2+1 avidity format that kills at ~1,000 EGFR/cell while covering cetuximab-resistance variants (69) — though 69 concedes normal epithelium carries 40,000–100,000 EGFR/cell.
- Ep 71 is the only clinical datapoint: IMA401's deliberately low-affinity CD3 arm gave 38% CRS, all grade 1–2, zero ICANS, and 20% ORR at RP2D — evidence the affinity-attenuation route survives first-in-human.
- Eps 60 and 76 change the effector rather than the targeting arm: Vγ9Vδ2 engagement spared 5T4-positive healthy tissue (60), and a CD2 costimulator restored killing at sub-efficacious TCE doses with ≤2-fold IL-6/TNF rises versus up to 200-fold for CD28 (76).
- Ep 59 adds the third-cell variant — recruiting myeloid cells into the T-cell/tumour synapse beat a matched bispecific — but the cytokine-release profile at equi-efficacious doses is exactly what the notes do not report.

Watch for: any of these designs tested against a matched, non-gated, non-attenuated control in the same model — most claims so far are versus the parental molecule, not versus simple affinity reduction.

## Does in silico design earn trust before the wet lab?
How much of protein and antibody engineering can be decided computationally, and what does honest validation look like?

- Ep 81 is the anchor: a blinded prospective benchmark where a non-ML positional consensus placed third (540 pM, perfect developability), only ~10–14% of AI cluster-ranking entries beat the most-abundant-clone heuristic, and the top 2.9 pM design outright failed HIC.
- Eps 17, 19, 45, 67 and 74 all report hybrid wins — theory-derived features feeding gradient-boosted trees (45), single-mutation data plus evolutionary priors in augmented ridge regression (19), AbMAP's 82% hit rate on SARS-CoV-2 binders (17), pLMs fine-tuned on billion-member yeast-display recognition profiles (67), and ProteinMPNN seeding a yeast-display library that then did the real work (74, where AlphaFold2 failed to predict the interface).
- Ep 1 is the cautionary case: AF-cluster's metamorphic-protein predictions were no better than random MSA subsampling, with confidence scores inconsistent with the predicted conformations. Ep 2 sits at the far end — an entirely computational vaccine design with no wet step at all.
- Eps 70, 36, 27 and 46 push scaling and transfer claims (log-linear contact-prediction gains to 6B parameters, 70; threading plus deep-learning restraints, 36; AlphaFold distances as restraints for disordered ensembles capped at 22 Å, 27; a transferable coarse-grained force field, 46) — none benchmarked blind against the others.

Resolution: blinded, prospective, experimentally-scored challenges like Ep 81's, run on data-poor antigens rather than the most-sequenced target available.

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

Resolution: almost all of these are preclinical (26 explicitly notes CAR-iMACs do not persist in vivo; 24's in vivo separation was weaker than in vitro). The thread advances when one reaches a first-in-human readout.

## Taking the brakes off immunity — where does it break?
Every inhibitory pathway that protects tumours is doing something useful elsewhere; what is the cost of removing it?

- Ep 4 makes the tension explicit: ITPRIPL1 is testis-enriched and its knockout increases testicular T cell infiltration, so systemic blockade risks immune-privilege breakdown.
- Ep 33 moves a checkpoint out of oncology entirely — microglial TIM-3 restrains amyloid-β phagocytosis, and its deletion reduced plaque burden in 5xFAD mice, but removing a CNS inhibitory receptor raises unaddressed neuroinflammation risk.
- Ep 21 shows the tradeoff within a single pathway: scratch-induced substance P→MrgprB2 mast cell activation drives both allergic inflammation and protection against *S. aureus*.
- Ep 25 quantifies the price in a trial: obinutuzumab improved complete renal response (46.4% vs 33.1%) but raised serious adverse events to 32.4% vs 18.2%, mostly infections.
- Ep 22 is the same accounting in a different modality: ARIA is the dominant liability of anti-amyloid antibodies, forced higher by poor BBB penetration, and gantenerumab cleared amyloid without cognitive benefit.

Watch for: whether any of these can be split pharmacologically — Ep 21's open question (separating the allergic from the antibacterial arm downstream of mast cell activation) is the cleanest formulation.

## Non-specific immune stimulation and the durability of responses
Does generic immune activation, rather than antigen-specific design, explain a lot of what we attribute to targeted immunology?

- Ep 56 is the sharpest version: an mRNA vaccine with no tumour antigen sensitised mouse tumours to checkpoint blockade, with a retrospective survival association in patients.
- Ep 32 makes the same shape of claim outside oncology — a birthdate-cutoff natural experiment reporting ~20% lower dementia incidence after live zoster vaccination, with viral suppression and non-specific live-vaccine effects both left open.
- Ep 16 supplies a candidate durability mechanism with nothing to do with antigen: a day-7 platelet/megakaryocyte transcriptional signature predicting antibody longevity across six vaccines in seven trials, with TPO enhancing durability.
- Ep 20 is the counterweight — prior vaccination *dampened* innate overactivation during breakthrough infection, so "more stimulation" is not uniformly the goal.

Resolution: Ep 56 needs a prospective randomised trial of vaccination timed to ICB initiation; Ep 32 needs a Shingrix comparison, which would separate viral suppression from live-vaccine immune effects.

## What counts as causal evidence outside the lab
Several episodes lean on design rather than randomisation; the recurring question is when that is enough.

- Eps 32, 73 and 80 are the strong cases: a birthdate discontinuity with the effect appearing for dementia and not other outcomes (32), occupation-level WFH exposure instrumented with the pre-pandemic Dingel–Neiman index giving a 1.3% employment gain per point of WFH and 68–85% of the disability employment rise (73), and registry-linked conscription scores revealing SES-staggered Flynn reversals that cancelled in the national mean (80).
- Eps 66 and 79 show the limits: half the conservative–liberal comorbidity divergence is unexplained by observable sorting, and the trust mechanism comes from a separate 2024 survey, not the same individuals (66); a 1-second maternal vocal response window predicts later ADHD/DBD in 158 dyads, but with six autism cases and degraded VHS audio (79).
- Eps 42 and 55 are observational designs where the causal question is untested — soil and cherry microbiome predicting coffee flavour without inoculation trials (42), and guideline-era exposure standing in for individual adherence to early allergen introduction (55).
- Ep 82 is the extreme of inference from a found sample: three undiagnosed rabies deaths among 239,251 deceased organ donors scale to ~34 US rabies deaths a year and ~7% surveillance detection — but the whole numerator is n = 3, the CI (213–2,220 deaths) captures only Poisson noise, and the load-bearing assumption is that donors carry average national risk. Its virtue is stating the falsification bar numerically (donors would need ~14-fold elevated rabies risk), which Eps 42, 55 and 66 never do.
- Eps 72 and 77 randomise the exposure instead: preregistered elite-rhetoric quotes shifting Trump voters toward censorship support while non-Trump voters backlashed (72), and anonymised text negotiations where observers guessed gender at 43% — worse than chance — yet women still generated higher subjective value (77).
- Ep 11's SURD framework, with its redundant/unique/synergistic decomposition and "causality leak" term, is the methodological backbone the show keeps reaching for, though it had no applied-domain demonstration in the notes.

Watch for: whether Ep 73's effect reverses under return-to-office mandates, and whether Ep 82's estimate survives its own proposed direct test — a defined-denominator retrospective series of unexplained fatal encephalitis deaths assayed for rabies.

## Machines that decide, not just compute
Where is the line between automation and autonomy, and does crossing it help?

- Ep 14 draws the definition explicitly (automated = human-decided, autonomous = machine-decided) and admits its decision layer is heuristic, with no quantitative definition of "novelty" to guide exploration.
- Ep 30 closes the loop physically — an LLM re-planning mid-task in changing environments — but the episode material carried no success rates or non-LLM baseline.
- Ep 58 is the constraint: LLMs cannot reliably attribute a false first-person belief, correcting the speaker instead, and the gap narrowed but did not close in newer releases.
- Eps 45 and 49 show the pattern that keeps working — theory-derived features as inductive bias for a gradient-boosted model (45), and learned embedding fields enabling mapping from sparse labels (49) — both prediction, neither decision.

Resolution: Ep 14's own test — a genuinely unanticipated compound or reaction class discovered by the machine and independently characterised — remains unmet.

## Is the dominant framework in a field actually load-bearing?
A recurring meta-thread: when do accumulated anomalies mean a paradigm should be replaced rather than patched?

- Ep 31 argues the somatic mutation theory of cancer has failed, citing driver mutations in histologically normal tissue and cancers with no identifiable drivers — while conceding it offers no falsification criteria for its cell-state alternative.
- Ep 12 complicates both sides: ecDNA species co-segregate non-randomly via intermolecular interactions and transcription, which is genetic but not Mendelian, and shapes targeted-therapy response.
- Ep 34 is the model of how to do this properly — a preregistered adversarial collaboration where neither GNWT nor IIT passed in full, forcing revision rather than confirmation of either. Ep 41 supplies the older version of the same worry: objective reduction works by moving away from the subjective viewpoint, which is precisely what consciousness research must explain.
- Ep 38 offers a candidate reframe — cross-tissue multicellular coordination rewired in cancer — but the supplied material had no cohort sizes or statistics to assess it.
- Ep 70's "world model" claim is the newest instance: layer-wise decoupling of function and structure is argued as evidence of internal organisation, not demonstrated by causal intervention on the model's features.

Watch for: Ep 31's unanswered challenge — why mutation-targeted therapies work at all if mutations are not causal — and whether any successor framework adopts Ep 34's preregistered adversarial format.

## Antibody format, size, and the penetration–residence tradeoff
Does molecular architecture, independent of affinity, determine where an antibody goes and what it does?

- Ep 40's three-paper survey sets the tradeoff: transport into tumour competes with systemic and antigen-mediated clearance, small formats penetrate better but clear faster, and size is a principal determinant of fragment biodistribution.
- Eps 47 and 52 locate function in geometry rather than binding strength — domain rearrangement on dual antigen engagement as the source of activity enhancement (47), and hinge plasticity in intact IgG (52, DOI only; numbers still need backfilling).
- Ep 44 moves the lever outside the CDRs entirely, tuning stability and function via rational framework mutations, with the unresolved risk that non-germline framework residues raise immunogenicity.
- Ep 63's pH switch is the same principle in a different guise: the causative mutations (T89LD, Q90LE) do not contact antigen, acting through loop rigidification and a ~2° VH/VL tilt — both inferred from constant-pH simulation, not structures at both pH values.
- Ep 81 supplies the discipline check — developability was scored across five assays, and a composite threshold let a 2.9 pM design pass despite an outright HIC failure.

Resolution: matched-format, matched-affinity head-to-heads in a single tumour model, plus experimental structures at both states for the rearrangement and pH-switch claims.

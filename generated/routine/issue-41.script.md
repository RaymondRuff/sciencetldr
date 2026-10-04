# Issue #41 — script (routine writer)

**Length:** 10,792 chars (~10.2 min)  
**Episodes cited:** [3, 70]

## Corrections made by the fact-check pass

- Nadia described episode 3 as having no causal handle on its neutrophil states; the card reports leucine metabolism driving the antigen-presenting state, so the clause now says one state had a metabolic driver and the rest did not.
- Nadia attributed to the authors that 'most' predicted regulators are not individually sufficient to polarise a cell; the paper says 'not all ... are individually sufficient to induce a fully polarized state' — restored their wording.
- The Th1/Th2 validation was given as 12 of 13 without saying the 13 were pre-filtered from 18 on robustness in the screen itself; both the result turn and Theo's third takeaway now name the filter.
- Nadia listed Jurkat cells as a third clean negative in the lymphocyte-count analysis; the authors state the Jurkat gap could be explained by the smaller number of perturbations measured, so that caveat is now spoken.
- Theo had the authors 'warn' that 'such models will struggle' in unmeasured states; the paper says context specificity 'may' pose hurdles for models predicting perturbation effects, not for protein language models — softened and re-pointed.
- Nadia said the probe readout 'misses most non-coding RNAs'; the paper claims it limits certain coding and non-coding RNAs, allelic variants and isoform- or UTR-level dynamics, with no fraction given.
- 575 cells per perturbed gene per condition was stated flatly; it is a mean, and the paper notes essential genes fall well below it, so that is now said.
- The power analysis was quoted as costing '30 percent of replication' at 10 percent read depth; the paper reports a ~30 percent reduction in Pearson R, and the analysis covers 12 genes in the rested condition only — both corrected.
- Nadia said prior primary-cell perturb-seq used libraries of 'a few hundred genes'; the paper gives no library size, so the number was removed.
- '12,779 genes, two guides each, 26,504 guides' implied all guides were targeting; the library includes five percent non-targeting controls, now stated.
- Nadia invented 'an eighty-year-old'; the paper says 'T cells profiled from aged individuals' — changed to aged donors.
- The mTORC1 direction reversal was reported without the authors' own control: individual knockdowns do move gold-standard mTORC1 activation signatures as expected, which is now credited.
- The Th1/Th2 arrayed experiments were called knockouts; the study is CRISPRi throughout, so 'knocked down'.
- The OneK1K split read as 199 of 782 donors; the methods describe disjoint discovery (782) and replication (199) cohorts.
- The 310 distal off-target guides were described as 'flagged'; the paper excluded them, and 'distal' distinguishes them from the 10 percent proximal cases that were annotated.
- One protein-level discordance was reported; the paper describes two, one Th1 and one Th2 regulator.
- 'Nothing tissue-specific survives' overstated the authors' 'tissue-specific regulatory effects ... are likely missed'.
- The rested-condition fit being best was given as the hosts' own inference; the paper attributes it to PBMCs being predominantly unstimulated, so it is now attributed.
- Added Nadia-side thinking sounds and a self-correction, which the fact-check noted were missing from her register, and trimmed setup and framing to hold the length window.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** And today, in Cell: "Genome-scale perturb-seq in primary human CD4 T cells maps context-specific regulators of T cell programs and human immune traits." In one line: they knocked down every expressed gene, one at a time, across 22 million primary human T cells, reading out the whole transcriptome.

**Theo:** Why is that worth ten minutes? Perturb-seq isn't new.

**Nadia:** It isn't. The move is where it was done. Perturb-seq is a pooled CRISPR screen whose readout is the whole transcriptome of each cell, not survival or one marker. Genome-scale versions have been in immortalised lines; primary cells have had targeted libraries, biased toward regulators you already suspect. Here the library is every expressed gene in CD4 T cells plus all annotated transcription factors: 12,779 genes, two guides each, plus five percent non-targeting controls — 26,504 guides.

**Theo:** And in primary cells.

**Nadia:** Four healthy donors, naive CD4 T cells. CRISPRi — a dead Cas9 fused to a repressor domain, so knockdown, not cutting. And what makes it affordable: a probe-based readout that lets you fix cells and overload the lanes, so tens of millions fit in fewer than eighty lanes.

**Theo:** Hmm. And the conditions?

**Nadia:** Three: rested, eight hours after re-stimulation, and forty-eight hours after. Same perturbations, three states.

**Theo:** So what came out?

**Nadia:** Start with quality control — they're unusually open there. After filtering, 33.4 million cells; 21.99 million, 66 percent, had exactly one guide assigned. The rest had none or several, and get dropped. That averages 575 cells per perturbed gene per condition — with essential genes well below it.

**Theo:** And did the knockdown work?

**Nadia:** For 73 percent of tested guides, yes — median log-two fold change minus 2.33. The failures were mostly genes with very low baseline expression. They threw out 869 guides as inefficient, and for 100 genes both guides failed.

**Theo:** Wait — so a hundred genes are just missing from the map.

**Nadia:** Yes. And they say so. They removed 310 guides for likely distal off-target activity, and in 10 percent of perturbed genes the guide also hit a neighbour — those they annotate rather than hide. The map itself: effects for 11,527 genes, of which 7,807 — 67 percent — moved at least three other genes. Just over two million regulator-to-gene effects.

**Theo:** Two million. What does that buy?

**Nadia:** Less than it sounds. The median perturbation with real knockdown moves two genes. Two. The top five percent move more than 427 — a sparse network with a handful of hubs, not a dense web.

**Theo:** Huh. So the headline is the tail, not the average.

**Nadia:** And context dependence is the real result. They clustered 3,341 strong perturbations from 1,860 regulators into 111 clusters — about a third holding together in only one or two conditions.

**Theo:** Meaning they stop co-behaving when the state changes.

**Nadia:** Right. And a subtler version: Mediator and SAGA — big coactivator complexes — stay coherent in all three conditions, consistent with acting as one physical complex throughout. But the downstream genes they control change with state. Same machine, different output.

**Theo:** So "what does this gene regulate" has no answer without a state attached. Did they test the timing split — early versus late?

**Nadia:** Early if they appeared at eight hours only, late at forty-eight only. Early ones included calcium-handling factors; late ones, cell cycle and genome integrity. They then knocked down six predicted early-or-late regulators, and five of six behaved as classified.

**Theo:** Five of six, arrayed, independent RNA-seq. Fine.

**Nadia:** Cytokines are similar. Thirty canonical cytokine genes; 1,556 perturbations with a strong effect — one percent FDR — on at least one cytokine in some condition.

**Theo:** Um — 1,556 regulators of cytokines sounds like everything regulates everything.

**Nadia:** It partly does, and they show why that's not vacuous. For a stimulation-induced cytokine, negative regulators turn up mostly in rested cells, where the gene is near-off and there's room to see it rise; positive regulators, after stimulation. The condition decides which half you can see.

**Theo:** Ah, okay. That's a measurement asymmetry, not biology.

**Nadia:** Both, really — but yes, it's a reason a one-condition screen gives you half a map. They then validated nine regulators of IL-10 and IL-21 arrayed, two guides each, by bulk RNA-seq and intracellular staining. All 12 tested regulatory interactions went the predicted direction; 10 significant at 10 percent FDR.

**Theo:** And the protein?

**Nadia:** Mostly concordant — one exception, where the protein didn't follow the transcript. They flag probable post-transcriptional regulation. I'd read it as the reminder that this is an mRNA assay.

**Theo:** So — third act. From this map to human cohorts. How?

**Nadia:** A regression. Take a cell state observed elsewhere — a differential expression signature — and reconstruct it from perturbation signatures. Whichever regulators carry the weight are the nominated drivers.

**Theo:** Held-out genes, or the ones they fit on?

**Nadia:** Held out. For a Th2-versus-Th1 signature from sorted human cells, mean cross-validated correlation 0.39 in the discovery cohort, 0.27 in an independent replication cohort. It beat the same model built on K562 perturbations.

**Theo:** 0.39 is... fine. That's not a prediction, it's a nomination.

**Nadia:** Agreed. It's a hypothesis generator with a measured hit rate.

**Theo:** Which they measured?

**Nadia:** They did. Eighteen knocked down individually, including under Th1 and Th2 polarising conditions; of the 13 they pre-filtered for robust screen effects, 12 shifted the signature genes as predicted — four previously uncharacterised Th1 regulators, two Th2.

**Theo:** And at the protein level?

**Nadia:** Hmm. Weaker. The master regulators moved T-bet, GATA3 and the cytokines hard. The novel ones were subtler, and two candidates — one Th1, one Th2 — moved marker cytokines opposite to their RNA signatures. Their conclusion: not all of these regulators are individually sufficient to induce a fully polarised state.

**Theo:** Then the aging analysis — the one I'd be most nervous about.

**Nadia:** Fair. CD4 T cells from the OneK1K cohort — 782 discovery donors, another 199 held out — an age-associated signature controlling for subset composition, reconstructed from perturbations. Best fit was the rested condition, correlation 0.366, which they attribute to PBMCs being mostly unstimulated.

**Theo:** And what gets nominated?

**Nadia:** mTORC1 components and SUMOylation enzymes. And here's the part I respect: the direction for mTORC1 is backwards from what the aging literature would predict. Knocking down the mTOR-inhibiting complexes gives the signature of young cells, not old.

**Theo:** Oh — that's a problem for the story.

**Nadia:** It is, and they print it: feedback, compensation, or survivor bias in the T cells you can still profile from aged donors. Unresolved. Though the knockdowns do move mTORC1 activation signatures the expected way, so it isn't an assay failure.

**Theo:** Last piece — human genetics.

**Nadia:** Loss-of-function burden statistics for lymphocyte count from the UK Biobank, 454,787 participants. The logic: if a gene sits close to the trait, the genes regulating it should carry burden signal too. They see that excess in the stimulated conditions, not in rested cells or K562. The Jurkat arm they caveat themselves — could just be fewer perturbations measured.

**Theo:** So the cell state is load-bearing for the genetics too.

**Nadia:** That's their inference. They also tested their regulator clusters for enrichment of autoimmune-associated genes from Open Targets: 33 of 77 testable clusters, concentrated in the stimulated conditions, and weaker for three non-immune control diseases.

**Theo:** The control-disease comparison is what makes that worth anything. Okay — the hard part. What would I want first?

**Nadia:** Well — their own limitations list is most of mine, which doesn't happen often. Two guides per gene, so guide disagreements can't be resolved. CRISPRi is partial repression, so a protein whose activity saturates at low abundance looks like a non-hit. And the probe readout limits certain coding and non-coding RNAs, allelic variants and isoform-level dynamics.

**Theo:** And pseudobulk?

**Nadia:** They aggregate — well, per perturbation per donor. Which buys stability and throws away response heterogeneity, and they show substantial cell-to-cell variation even among controls. A distribution-aware analysis is future work, by their own account.

**Theo:** And the conditions? Three states is more than one, but it's still three.

**Nadia:** And all non-polarising. So the rewiring polarising cytokines drive — the thing CD4 biology is famous for — is unmapped here. These are also blood-derived cells in culture, so tissue-specific effects are likely missed, as they say.

**Theo:** Hmm. And the thing nobody can fix cheaply: it's all transcription.

**Nadia:** Yes. Every phenotype here is an mRNA profile. The authors state plainly that linking perturbation effects to immune cell function still needs doing.

**Theo:** Two connections. Episode 3 gave us ten neutrophil states, with a metabolic driver for one and no systematic causal handle on the rest. That's the pattern: atlases multiply, the causal arm lags. This is the causal arm arriving, and what it yields is a nomination at 0.39.

**Theo:** And episode 70's protein language model argued a "world model" from internal organisation rather than intervention. This is the intervention side — and these authors suggest their context-specificity result may be a hurdle for perturbation-prediction models in contexts nobody measured.

**Theo:** Three takeaways. One: the scale is real, but the number that matters isn't 22 million cells — it's 575 cells per gene per condition across four donors. That's what lets them quote gene-level effects; their power analysis — twelve genes, rested — says estimates stabilise near 200 cells per perturbation, and cutting read depth to 10 percent costs about 30 percent of the Pearson R.

**Nadia:** Right.

**Theo:** Two: context specificity is the finding, supported three ways — a third of clusters cohere in only some conditions, the same complexes retarget across states, and the burden signal appears only in stimulated cells.

**Theo:** Three: the regression is a nomination engine — 12 of 13 the right way transcriptionally, after a screen-based filter on 18, weaker on protein, one top pathway pointing the wrong way in the aging analysis. Useful. Not a causal map of aging.

**Nadia:** Mm.

**Theo:** What I'd believe: regulatory architecture in CD4 T cells is state-dependent, and a one-condition screen gives you a partial answer. What I wouldn't yet: any specific nominated regulator of human aging, from this.

**Nadia:** For me it's the guide number. What would move me is a third and fourth guide on the disputed targets, plus the same perturbations under polarising cytokines — where their argument predicts the map changes most.

**Theo:** And a functional readout. Proliferation, killing — something that isn't a transcript.

**Nadia:** Agreed.

**Nadia:** That's Cell — DOI ten point one-oh-one-six, J dot cell dot twenty twenty-six dot zero-eight dot zero-zero-two. The data's deposited and the model is a Python class.

**Theo:** Thanks for listening.

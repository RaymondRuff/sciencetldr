# Issue #41 — script (routine writer)

**Length:** 10,786 chars (~10.2 min)  
**Episodes cited:** [3, 70]

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** And today, in Cell: "Genome-scale perturb-seq in primary human CD4 T cells maps context-specific regulators of T cell programs and human immune traits." In one line: they knocked down every expressed gene, one at a time, across 22 million primary human T cells, and read out the whole transcriptome each time.

**Theo:** Why is that worth ten minutes? Perturb-seq isn't new.

**Nadia:** It isn't. The move is where it was done. Perturb-seq is a pooled CRISPR screen whose readout isn't survival or one sorted marker — it's the whole transcriptome of each cell. Genome-scale versions have been in immortalised lines; primary cells have had targeted libraries, a few hundred genes you already suspect. Here the library is every gene expressed in CD4 T cells plus all annotated transcription factors: 12,779 genes, two guides each, 26,504 guides.

**Theo:** And in cells from actual donors.

**Nadia:** Four healthy donors, naive CD4 T cells. CRISPRi — a dead Cas9 fused to a repressor domain, so knockdown, not cutting. And what makes it affordable: a probe-based readout that lets you fix cells and overload the lanes, so tens of millions fit in under eighty lanes.

**Theo:** Hmm. And the conditions?

**Nadia:** Three ways: rested, eight hours after re-stimulation, and forty-eight hours after. Same perturbations, three states.

**Theo:** So what came out of it?

**Nadia:** Start with quality control, because they're unusually open about it. After filtering, 33.4 million cells; 21.99 million — 66 percent — had exactly one guide assigned. The rest had none or several, and get dropped. That leaves 575 cells per perturbed gene per condition.

**Theo:** Mm-hm. And did the knockdown work?

**Nadia:** For 73 percent of tested guides, yes — median log-two fold change of minus 2.33. The failures were mostly genes with very low baseline expression. They threw out 869 guides as inefficient, and for 100 genes both guides failed.

**Theo:** Wait — so a hundred genes are just missing from the map.

**Nadia:** Yes. And they say so. They also flagged 310 guides with likely off-target activity, and in 10 percent of perturbed genes the guide also hit a neighbour, which they annotate rather than hide. The map itself: transcriptome-wide effects for 11,527 genes, of which 7,807 — 67 percent — moved at least three other genes. Just over two million significant regulator-to-gene effects.

**Theo:** Two million. What does that buy you?

**Nadia:** Less than it sounds. The median perturbation with real knockdown moves two genes. Two. The top five percent move more than 427. A sparse network with a handful of hubs, not a dense web.

**Theo:** Huh. So the headline is the tail, not the average.

**Nadia:** And context dependence is the real result. They clustered 3,341 strong perturbations from 1,860 regulators into 111 clusters — about a third of which hold together in only one or two of the conditions.

**Theo:** Meaning they stop co-behaving when the cell changes state.

**Nadia:** Right. And a subtler version: Mediator and SAGA — big coactivator complexes — stay coherent in all three conditions, consistent with acting as physical complexes throughout. But the downstream genes they control change with state. Same machine, different output.

**Theo:** So "what does this gene regulate" has no answer without a state attached. Did they test the timing split — early versus late?

**Nadia:** Early if they appeared at eight hours only, late at forty-eight only. Early ones included calcium-handling factors; late ones, cell cycle and genome integrity. They then knocked down six predicted early-or-late regulators one at a time, and five of six behaved as classified.

**Theo:** Five of six, arrayed, independent RNA-seq. I'll take that.

**Nadia:** The cytokine application is similar in shape. Thirty canonical cytokine genes; 1,556 perturbations with a strong effect — one percent FDR — on at least one cytokine in some condition.

**Theo:** Um — 1,556 regulators of cytokines sounds like everything regulates everything.

**Nadia:** It partly does, and they show why that's not vacuous. For a stimulation-induced cytokine, negative regulators turn up mostly in rested cells, where the gene is near-off and there's room to see it rise; positive regulators, after stimulation. The condition decides which half of the regulation you can see.

**Theo:** Ah, okay. That's a measurement asymmetry, not biology.

**Nadia:** Both, really — but yes, it's a reason a one-condition screen gives you half a map. They then validated nine regulators of IL-10 and IL-21 in arrayed format, two guides each, by bulk RNA-seq and intracellular protein staining. All 12 tested regulatory interactions went the predicted direction; 10 significant at 10 percent FDR.

**Theo:** And the protein?

**Nadia:** Mostly concordant — with one exception, where the protein didn't follow the transcript. They flag probable post-transcriptional regulation. I'd read it as the reminder that this is an mRNA assay.

**Theo:** So — third act. They go from this map to human cohorts. How?

**Nadia:** A regression. Take a cell state observed elsewhere — a differential expression signature — and reconstruct it as a weighted combination of perturbation signatures. Whichever regulators carry the weight are the nominated drivers.

**Theo:** Held-out genes, or the ones they fit on?

**Nadia:** Held out. For a Th2-versus-Th1 signature from sorted human cells, mean cross-validated correlation of 0.39 in the discovery cohort, 0.27 in an independent replication cohort. It beat the same model built on K562 perturbations.

**Theo:** 0.39 is... fine. That's not a prediction, it's a nomination.

**Nadia:** Agreed. It's a hypothesis generator with a measured hit rate.

**Theo:** Which they measured?

**Nadia:** They did. Eighteen predicted regulators knocked out individually, including under Th1 and Th2 polarising conditions; of 13 with robust effects, 12 shifted the signature genes as predicted — four previously uncharacterised Th1 regulators, two Th2.

**Theo:** And at the protein level?

**Nadia:** Weaker. The canonical master regulators moved T-bet, GATA3 and the cytokines hard. The novel ones were subtler, and one Th2 candidate moved the marker cytokines opposite to its RNA signature. Their own conclusion: most of these regulators are not individually sufficient to polarise a cell.

**Theo:** Then the aging analysis — the one I'd be most nervous about.

**Nadia:** Fair. CD4 T cells from the OneK1K cohort — 782 donors, 199 held out — an age-associated signature controlling for subset composition, reconstructed from perturbations. Best fit came from the rested condition, correlation 0.366, which tracks with blood being mostly unstimulated cells.

**Theo:** And what gets nominated?

**Nadia:** mTORC1 components and SUMOylation enzymes. And here's the part I respect: the direction for the mTORC1 components is backwards from what the aging literature would predict. Knocking down the mTOR-inhibiting complexes gives the signature of young cells, not old.

**Theo:** Oh — that's a problem for the story.

**Nadia:** It is, and they print it. They offer feedback, compensation, or survivor bias in the cells you can still collect from an eighty-year-old — and don't resolve it.

**Theo:** Last piece — human genetics.

**Nadia:** Loss-of-function burden statistics for lymphocyte count from the UK Biobank, 454,787 participants. The logic: if a gene sits close to the trait, the genes regulating it in T cells should carry burden signal too. They see that excess in the stimulated conditions — not in rested cells, not in K562, not in Jurkats.

**Theo:** So the cell state is load-bearing for the genetics too.

**Nadia:** That's their inference. They also tested their regulator clusters for enrichment of autoimmune-associated genes from Open Targets: 33 of 77 testable clusters, concentrated in the stimulated conditions, and weaker enrichment for three non-immune control diseases.

**Theo:** The control disease comparison is the part that makes that worth anything. Okay. The hard part. What would I want before I lean on this?

**Nadia:** Their own limitations list is most of mine, which doesn't happen often. Two guides per gene, so guide disagreements can't be resolved. CRISPRi is partial repression, so a protein whose activity saturates at low abundance looks like a non-hit. And the probe readout misses most non-coding RNAs, isoforms and UTR-level regulation.

**Theo:** And pseudobulk?

**Nadia:** They aggregate cells per perturbation per donor, which buys stability and throws away response heterogeneity — and they show substantial cell-to-cell variation even among controls. A distribution-aware analysis is future work, by their account.

**Theo:** And the conditions themselves? Three states is more than one, but it's still three.

**Nadia:** And all non-polarising. So the rewiring that polarising cytokines drive — the thing CD4 biology is famous for — is unmapped here, as they say. These are also blood-derived cells in culture, so nothing tissue-specific survives.

**Theo:** Hmm. And the thing nobody can fix cheaply: it's all transcription.

**Nadia:** Yes. Every phenotype here is an mRNA profile. The authors state plainly that linking perturbation effects to actual immune cell function still needs doing.

**Theo:** Two connections. Episode 3 gave us ten neutrophil states from single-cell profiling with no causal handle on what maintains them — and that's the pattern: atlases multiply, the causal arm lags. This is the causal arm arriving, and what it yields is a nomination at 0.39.

**Theo:** And episode 70's protein language model paper argued a "world model" from internal organisation rather than intervention. This is the intervention side — and these authors warn their own context-specificity result means such models will struggle in states nobody measured.

**Theo:** Three takeaways. One: the scale is real, but the number that matters isn't 22 million cells — it's 575 cells per gene per condition across four donors. That's what lets them quote gene-level effects at all; their power analysis says estimates stabilise near 200 cells per perturbation, and cutting read depth to 10 percent costs about 30 percent of replication.

**Nadia:** Right.

**Theo:** Two: context specificity is the finding, supported three ways — a third of clusters cohere in only some conditions, the same complexes retarget across states, and the genetic signal appears only in stimulated cells.

**Theo:** Three: the cell-state regression is a nomination engine with a measured hit rate — 12 of 13 the right way transcriptionally, weaker on protein, one top pathway pointing the wrong way in the aging analysis. Useful. Not a causal map of aging.

**Nadia:** Mm.

**Theo:** What I'd believe: that regulatory architecture in CD4 T cells is state-dependent, and that a one-condition screen gives you a partial answer. What I wouldn't yet: any specific nominated regulator of human aging, from this.

**Nadia:** For me it's the guide number. What would move me is a third and fourth guide on the disputed targets, plus the same perturbations under polarising cytokines — where their own argument predicts the map changes most.

**Theo:** And a functional readout. Proliferation, killing, something that isn't a transcript.

**Nadia:** Agreed.

**Nadia:** That's Cell — DOI ten point one-oh-one-six, J dot cell dot twenty twenty-six dot zero-eight dot zero-zero-two. The data's deposited and the model is released as a Python class.

**Theo:** Thanks for listening.

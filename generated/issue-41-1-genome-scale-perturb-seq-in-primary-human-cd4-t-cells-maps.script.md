# 1. Genome-scale perturb-seq in primary human CD4 T cells maps context-specific regulators of T cell programs and human immune traits

**DOI:** 10.1016/j.cell.2026.08.002  
**Length:** 11061 chars (~10.4 min)

## Corrections made by the verification pass

- Publication status: draft said the paper was "posted as a preprint and now in Cell"; the PDF is an uncertified bioRxiv preprint, so this is now stated as the preprint carrying a Cell DOI.
- Library description: "essentially every expressed gene" corrected to the paper's actual library — the union of all expressed CD4 T cell genes and all transcription factors (12,748 genes).
- Off-target figure: script said 18% of "all tested perturbations"; the paper reports 18% of all tested perturbed genes.
- Theo's gloss "two guides against the same gene agree about half the time" misdescribes a Pearson correlation of ~0.5; rephrased as a correlation statement.
- Th1/Th2 inverted regulators: script named only IL4 as one of the two; the paper names TRAF3 and IL4, so TRAF3 is now named.
- Power analysis: draft said "donor count matters more than cells per perturbation once you're past roughly two hundred cells" and framed "four donors is where they ran out of budget" as following from their analysis; corrected to the paper's actual finding (for fixed cells per perturbation, more donors consistently improved trans-effect estimates; cell-number gains stabilized at ~200 cells) with the budget inference marked as Nadia's read.
- Figure 4H attribution: draft said the authors attribute the subtle single-cell shifts to the non-polarizing culture; the paper attributes them to full polarization requiring coordinated action of multiple regulators plus external signal input.
- FBXO32 "unstudied in immunity" now attributed to the authors rather than stated flatly.
- Claim strength: "cleanest internal demonstration of the whole context-dependence claim" softened to "cleanest internal support".
- Length: trimmed from 13,432 to within the 10,200–10,800 character window, cutting setup and framing rather than numbers or limitations.

---

**Nadia:** Hello and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** And today: genome-scale perturb-seq in primary human C-D-four T cells, out of Gladstone-U-C-S-F and Stanford. We read the bioRxiv preprint; it carries a Cell D-O-I. They knocked down the union of all expressed genes and all transcription factors — twelve thousand seven hundred forty-eight genes — across twenty-two million primary C-D-four T cells from four donors, at rest and after re-stimulation.

**Theo:** Okay. Why ten minutes? Genome-wide perturb-seq isn't new.

**Nadia:** It isn't — it's been done in K562 and other immortalized lines. The move here is primary cells, donor replication, and enough depth to trust per-gene effects rather than coarse signatures. Median transcripts per cell per context around ten thousand, comparable to the cell-line datasets, with roughly double the cell coverage — an average five hundred seventy-five cells per perturbed gene per condition.

**Theo:** Right. CRISPRi — knockdown, not knockout?

**Nadia:** Correct. Catalytically dead Cas9 fused to a repressor domain, parked at the promoter. Partial silencing, cell stays alive. The readout is probe-based single-cell R-N-A-seq — ten-x Flex — where instead of capturing polyadenylated messages you hybridize a defined probe panel. That lets them fix cells and superload lanes: twenty-two million assigned cells across fewer than eighty lanes.

**Theo:** Probe-based means you only see what's on the panel.

**Nadia:** Yes — real constraint. They also spiked in custom probes for the guide R-N-A itself.

**Theo:** Hm. Quality control first — at this scale I'm suspicious. What fraction of cells got a clean guide assignment?

**Nadia:** Thirty-three point four million cells passed transcriptome Q-C. Sixty-five point eight percent got a single guide, fourteen percent had none detected, twenty percent had multiple. They characterize both failure modes: multi-guide cells had higher U-M-I counts, consistent with doublets; no-guide cells had lower puromycin-resistance transcript, so they escaped selection rather than the probe failing.

**Theo:** Nice diagnostic. Did the guides knock down?

**Nadia:** Seventy-three percent of tested guides gave significant target reduction versus non-targeting controls. The failures concentrated in genes with very low baseline expression.

**Theo:** And off-target? Two guides per gene is thin.

**Nadia:** Um — careful here. They ran the proximal check: guides near a non-target transcription start site. Within five kilobases they saw downregulation of that neighbour in sixty percent of the one thousand seven hundred eighty-two genes with a proximal T-S-S — eighteen percent of all tested perturbed genes. They flag those as putative off-targets rather than silently including them.

**Theo:** Eighteen percent is not small.

**Nadia:** No. And they state in their own limitations that fully assessing off-target guide effects would need more guides per target. Cross-guide correlation was moderate — median point four seven to point five two depending on condition.

**Theo:** So a correlation of about a half between two guides against the same gene.

**Nadia:** On genes where both had measurable effects, yes. They attribute most discrepancies to differential knockdown efficiency — an attribution, not a demonstration.

**Theo:** External validation?

**Nadia:** Two comparisons. Against published arrayed knockout R-N-A-seq in C-D-four T cells, twenty-seven of thirty-two matched targets showed significant correlation, higher than randomly paired perturbations. And against F-A-C-S-based CRISPRi screens for four T-cell genes, effects correlated better between matched stimulation conditions than mismatched ones.

**Theo:** Ah — that second one's the better control.

**Nadia:** Agreed. And the headline is context dependence, larger than I'd have guessed. They clustered three thousand three hundred forty-one strong perturbations into one hundred eleven regulator clusters. About a third show coherent regulator effects in only one or two of the three conditions — rest, eight hours post-stimulation, forty-eight hours — and they checked it isn't explained by the regulator not being expressed in the others.

**Theo:** So the gene's there, it's just... not wired in.

**Nadia:** That's their read. There's a second flavour: clusters whose regulators act coherently in all three conditions — consistent with a physical complex — but control different downstream gene sets depending on activation state. Mediator and SAGA are the example.

**Theo:** Huh. Even the housekeeping coactivators, then.

**Theo:** Does any of it transfer to K562, which is what everyone else has been generating?

**Nadia:** Roughly eight percent of trans-effects detected in C-D-four T cells across three thousand eighty-one shared perturbations were also seen in K562, after meta-analysis for power differences. Mean Pearson correlation point three two for the same perturbation across cell types — better than random pairs, lower than between donor replicates. What transferred was enriched for housekeeping processes: transcription, chromatin remodelling, cell cycle.

**Theo:** Eight percent. That's the number I'd put on a slide arguing against training perturbation models on cell lines.

**Nadia:** The authors make roughly that argument, and they're explicit that cross-context prediction is likely to be hard.

**Theo:** Any concrete biology, or is it all atlas?

**Nadia:** They validated two cytokines — I-L-ten and I-L-twenty-one — with arrayed knockdowns of nine regulators, read out by bulk R-N-A-seq and intracellular protein staining. Eleven of twelve tested regulator-target interactions moved in the predicted direction; eight were statistically significant.

**Theo:** At protein level?

**Nadia:** Mostly concordant, with one clean exception: N-F-K-B-two's effect on I-L-ten showed up transcriptionally but not in protein. They report it and suggest post-transcriptional regulation.

**Theo:** And the modelling — they claim they can explain cell states from population atlases?

**Nadia:** They fit a regression reconstructing an observed cell-state signature as a linear combination of perturbation signatures. On a T-h-two versus T-h-one signature from sorted human cells: mean cross-validation correlation point three nine in the discovery cohort, point two seven in an independent replication cohort, on held-out genes. That beat models fit on K562 data, and beat scrambled controls.

**Theo:** Point two seven. Real, but — what's the ceiling?

**Nadia:** They plot it: inter-cohort agreement is the maximum achievable, and point two seven sits meaningfully below it. Signal, clearly. Not reconstruction.

**Theo:** Sanity check on the regulators?

**Nadia:** Known ones rank correctly with the right sign — I-F-N-gamma receptors, JAK2, IRF1 on T-h-one; I-L-four receptor, STAT6, GATA3, RARA on T-h-two. Only two came out inverted, TRAF3 and I-L-four itself, which they attribute to paracrine signalling in pooled culture damping the I-L-four knockdown response.

**Theo:** Mm-hm. Anything not already known?

**Nadia:** F-B-X-O-thirty-two as a top T-h-two regulator — expressed in T cells but, they say, unstudied in immunity. It and STAT6 have similar average effects on the signature while controlling distinct genes: F-B-X-O-thirty-two enriched for chemokines, STAT6 for GATA3 and T-G-F-beta components.

**Theo:** Wait — no functional validation of F-B-X-O-thirty-two?

**Nadia:** None. It's a nomination, and they say so.

**Theo:** There's an aging analysis too.

**Nadia:** Same framework on age-associated C-D-four expression across seven hundred eighty-two donors from the OneK1K cohort. Rest-condition perturbation effects fit best — cross-validation correlation point three six six. Top nominated pathways: m-T-O-R-C-one components and SUMOylation enzymes.

**Theo:** m-T-O-R and aging. Almost too tidy.

**Nadia:** Well — the honest part is that the directions run backwards. Knocking down the m-T-O-R-C-one inhibitors, T-S-C and GATOR genes, induces genes that are down in aged T cells, and RPTOR comes out as a negative regulator of the aging signature. That's opposite to the hyperactive-m-T-O-R story.

**Theo:** Oh. What do they do with that?

**Nadia:** Flag it, show the individual knockdowns move gold-standard m-T-O-R-C-one activation signatures as expected, then hypothesize feedback, compensation, or survivor bias in T cells from aged donors. It's in a supplementary note — they didn't quietly flip a sign.

**Theo:** And the human genetics integration?

**Nadia:** They correlate each regulator's knockdown effect on a gene with that regulator's loss-of-function burden effect on lymphocyte count in U-K Biobank. Excess correlation shows up in stimulated T cells at both timepoints — not in rested cells, not in K562, not in a Jurkat essential-gene screen.

**Theo:** Not in rested cells. Same cells, different state.

**Nadia:** That's the cleanest internal support for the context-dependence claim, because it holds cell type fixed. They do note the Jurkat comparison is confounded by the far larger number of perturbations they measured.

**Theo:** Limitations. Four donors.

**Nadia:** Four. Their power analysis shows that for a fixed number of cells per perturbation, adding donors consistently improved trans-effect estimates, while gains from more cells flattened around two hundred. So donors were the higher-value axis — my read is that four is a budget number.

**Theo:** And donor biology versus batch?

**Nadia:** Confounded, and they say so in limitations. Also pseudobulk aggregation, which masks heterogeneity of response across cells. And non-polarizing culture, so the cytokine-driven rewiring that defines T-helper differentiation is unmapped — which matters, given they're nominating polarization regulators.

**Theo:** So the T-h-one/T-h-two nominations come from cells that were never polarized.

**Nadia:** Correct. The single-cell shifts in Figure four-H are subtle, and they attribute that to full polarization requiring coordinated action of multiple regulators plus external signal input.

**Theo:** Connections — this sits against a thread we keep circling: episode sixty-three's p-H-switchable C-D-three binders, episode seventy-six's C-D-two costimulatory bispecific, episode seventy-one's clinical T-C-E-R. All engineer the molecule and treat the T cell as a fixed reagent.

**Nadia:** And this paper argues the reagent is wired differently depending on activation state. Whether that explains heterogeneous engager responses is a hypothesis — there's no engager anywhere in this paper.

**Theo:** Three takeaways. One: the technical claim holds — twenty-two million primary cells, seventy-three percent of tested guides with significant knockdown, replication against two independent screen types. Two: context dependence is the substantive result, and the sharpest evidence is the lymphocyte-count correlation appearing in stimulated but not rested cells, same cell type. Three: roughly eight percent of trans-effects shared with K562 — the number that should worry anyone training perturbation models on cell lines.

**Nadia:** I'd add: the cell-state modelling is a proof of concept at correlations around point three, under the noise ceiling. They call it a baseline themselves.

**Theo:** What would change my mind — a third guide per target on the eighteen percent flagged for proximal off-target effects, showing the trans-effects hold.

**Nadia:** For me, polarizing conditions. Add T-h-one and T-h-two skewing cytokines, re-run the polarization nominations. If F-B-X-O-thirty-two survives that, I'd believe it.

**Theo:** D-O-I ten point one zero one six, slash, j dot cell dot twenty twenty-six dot zero eight dot zero zero two. The data are publicly released.

**Nadia:** Thanks for listening.

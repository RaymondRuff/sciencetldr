# 1. Discovery and engineering of bispecific TCR-mimic antibodies targeting peptide-HLA complex

**DOI:** 10.1080/19420862.2026.2731282  
**Length:** 11302 chars (~10.7 min)

## Corrections made by the verification pass

- Length: draft ran 13,109 spoken characters against a 10,200–10,800 window; trimmed roughly 2,400 characters of setup, framing and transitional banter (opening premise turn, 'sell me' exchange, duplicated 'comparators fail the same assay' beat, 'honest version of that sentence' aside, repeated takeaway restatement) while leaving every number, control description and stated limitation intact.
- Framing mismatch: Theo's 'Sell me on twelve minutes' no longer matched the shortened runtime; changed to 'Sell me on it.'
- Claim strength: Theo's 'Which more or less explains the clinical history without needing any other hypothesis' overstated what the X-scan data show — the assay gives a mutational-tolerance footprint, not a demonstrated cause of ESK1's clinical performance; rewritten as 'Which is consistent with the clinical history...' with Nadia's hedge preserved.
- Merged the benchmark-comparison turns so the assay-condition caveat (100 nM antibody, 50 µM peptide pulse, non-physiological copy number) stays attached to the statement that the published comparators bound the off-target peptides, rather than following it as a separate softening turn.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** Today: a paper in mAbs from Alloy Therapeutics, with MD Anderson and Immunitrack — "Discovery and engineering of bispecific TCR-mimic antibodies targeting peptide-HLA complex." An end-to-end discovery platform, run on WT1 as a test case.

**Theo:** Okay. Sell me on it. WT1 TCR-mimics are not new.

**Nadia:** They're not. ESK1 has been around for over a decade. What interests me isn't the molecule — it's where they put the specificity screen. A proteome-wide off-target counter-screen during selection, rather than afterwards as a safety report.

**Theo:** So it's a process claim, not a product claim.

**Nadia:** Mostly. And there's one number that justifies the episode, which I'll get to.

**Theo:** Set the stage first. Why does this target class have a body count?

**Nadia:** About thirty percent of the proteome sits on the cell surface. Everything else is intracellular and invisible to a conventional antibody. But cells chew up intracellular proteins and display nine-residue fragments on H-L-A class one. A TCR-mimic reads that peptide-in-groove the way a T-cell receptor would.

**Theo:** And the failure mode is that the groove looks the same regardless of what's in it.

**Nadia:** Exactly. Your paratope is discriminating on four or five residues of a nine-mer in a highly conserved scaffold. The affinity-enhanced MAGE-A3 T-cell receptor programs cross-reacted onto titin and killed patients. That's the history behind every molecule in this class.

**Theo:** So what's the target?

**Nadia:** WT1 residues 126 to 134 — R-M-F-P-N-A-P-Y-L — on H-L-A-A-star-oh-two-oh-one. A leukemia antigen, and as the authors note, prior TCRm antibodies against it did poorly in the clinic on specificity grounds.

**Theo:** Alright, what's the pipeline?

**Nadia:** Four pieces. Refolded peptide-H-L-A monomers as immunogen, from Immunitrack. Twelve transgenic mice expressing human antibody variable regions, so the output arrives already human. Two parallel arms — single B-cell sorting and phage immune libraries from the same spleens. Then counter-screening.

**Theo:** Hang on — how do you sort for peptide specificity rather than H-L-A specificity? Most of that tetramer is H-L-A.

**Nadia:** Right question. They stained with the WT1 tetramer in P-E and a C-M-V-p-p-sixty-five tetramer on the same allele in a different dye, and sorted double — positive for one, negative for the other. Same idea on the phage side: deplete on mixed peptides loaded on A-two, then pan on WT1.

**Theo:** So the deselection is built in from the first step.

**Nadia:** It is. WT1-specific cells were between zero point five and six point five percent of the IgG-positive memory B-cell pool. Ninety-five hits, seventy-eight unique heavy-chain C-D-R-threes, cloned as IgG1. Eleven percent of expressed hits bound WT1 with no detectable binding to the mixed peptide pool — three clonotypes. Phage added fifteen more antibodies, two clonotypes.

**Theo:** Twenty-six total.

**Nadia:** Twenty-six. Affinities by high-throughput S-P-R from ten-to-the-minus-seven to ten-to-the-minus-ten molar. Twenty-five of twenty-six showed no binding to MAGE-A4 on the same allele. Epitope binning against the anti-A-two antibody B-B-seven-point-two split them into two bins.

**Theo:** And at that point you'd call all twenty-six specific.

**Nadia:** On that data, yes. Then they moved to T2 cells — T-A-P-deficient, so it can't load its own peptides and you pulse whatever you want onto its surface A-two. They pulsed WT1, and two known off-target peptides: M13L, R-M-F-P-T-P-P-S-L, and PIGQ, R-M-F-P-G-E-V-A-L. Both share the R-M-F-P start. Thirteen of the twenty-six bound M13L. Fourteen of twenty-six bound PIGQ.

**Theo:** Oh — half the panel that passed clean S-P-R against irrelevant peptide-H-L-A.

**Nadia:** Half. And that's the most useful result in the paper, because it tells you what the earlier screens are worth. A mixed peptide pool tells you nothing about a peptide sharing your N-terminal motif.

**Theo:** What did the benchmarks do?

**Nadia:** 33H9 and ESK1 bound both M13L and PIGQ. 11D06 bound M13L. Eight of the twenty-six bound neither. Though — at a hundred nanomolar antibody, pulsed at fifty micromolar peptide. That's a lot of peptide. T2 pulsing puts far more copies on the surface than a tumor cell presents endogenously, so it's a stringency test, not a physiological one.

**Theo:** Cuts both ways, presumably. Overstates off-target as well as on-target.

**Nadia:** It does, and they don't quantify it. As a rank-ordering tool among antibodies run side by side, though, it's doing real work.

**Theo:** Then the proteome piece — X-scan. Walk me through it.

**Nadia:** They display peptide-H-L-A as a single-chain trimer on phage — peptide, linker, beta-two-microglobulin, linker, heavy chain, with a Y-eighty-four-A mutation to accommodate the linker. Then a library where every position of the nine-mer is substituted with every amino acid. A hundred and seventy-two variants. Pan against bead-immobilised TCRm antibody, two rounds, sequence by N-G-S.

**Theo:** And what falls out is which positions you can't touch.

**Nadia:** An interaction footprint. Four subsets across the nine antibodies tested. Their lead, ATX-TCRm-06, reads positions three, four, six, seven and eight — five residues. A second group reads four, a third reads three. The fourth subset, 11D06 and ESK1, tolerated substitutions broadly at every position.

**Theo:** That's a clean separation. And ESK1 —

**Nadia:** ESK1's binding is driven mainly by the first residue, per the authors. One residue of a nine-mer.

**Theo:** [thoughtful] Which is consistent with the clinical history without needing any other hypothesis.

**Nadia:** It is. Then they take that footprint, run a proteome homology search, and ask which human peptides fit the motif. For their leads, the target peptide came back. For 11D06 and ESK1, four to twelve peptides came back.

**Theo:** Let me push on that. The proteome search is an algorithm over a motif — not an experiment against the real peptidome.

**Nadia:** It isn't, and you're right to separate those. It's a prediction of candidate cross-reactors from a mutational tolerance profile. It doesn't tell you whether those peptides are processed and presented on a real cell. And the algorithm is proprietary and internal, so I can't tell you its thresholds.

**Theo:** So what would close the gap?

**Nadia:** Synthesise the predicted hits, pulse them on T2, test binding. They did that for M13L and PIGQ, which were known from the literature — extending it to their own predictions isn't in the paper.

**Theo:** Alright. Engineering. They turn 06 into an engager.

**Nadia:** Two formats. First, a knob-into-hole heterodimer: anti-C-D-three s-c-F-v derived from the SP34 clone on the knob arm, WT1 Fab on the hole arm, N-two-nine-seven-A to kill Fc gamma receptor function. K-D of fourteen point six nanomolar for C-D-three, thirty-five nanomolar for the peptide-H-L-A.

**Theo:** Wait — the monomer affinity for the lead was sub-nanomolar. Nought point one nanomolar in the discussion.

**Nadia:** Yes. Reformatting bivalent IgG into a monovalent Fab costs you avidity — different measurements of different molecules. But the bispecific is what goes forward, and it binds target at thirty-five nanomolar.

**Theo:** And function?

**Nadia:** Jurkat N-F-A-T reporter against pulsed T2. WT1-pulsed gave roughly fifteen thousand relative light units. M13L-pulsed and no-peptide were both at baseline. That's the cleanest specificity result in the paper, because it's functional rather than a binding readout.

**Theo:** M13L being the peptide thirteen of their own twenty-six bound.

**Nadia:** The same one. Then primary human C-D-eight T cells, one-to-one effector-to-target, antibody at a hundred nanomolar, twenty-four hours, absolute counts by flow. Killing approached a hundred percent at peptide pulsing above fifty nanomolar. No antibody, no killing, even above five hundred nanomolar peptide.

**Theo:** And endogenous antigen? Pulsed T2 is not a tumor.

**Nadia:** Second format — different geometry, C-D-three s-c-F-v from U-C-H-T-one fused to the Fab light chain, anti-H-S-A single domain for half-life. Two molecules, from TCRm-01 and TCRm-06. Targets TF-1 and SET-2, chosen off DepMap for endogenous WT1 and A-two. Dose-dependent killing, sub-nanomolar E-C-fifties, reproduced in two H-L-A-A-two-positive donors.

**Theo:** Controls?

**Nadia:** An isotype control bispecific, same C-D-three binder, identical geometry. It didn't kill. That's the right control — you're isolating the targeting arm.

**Theo:** Reviewer question. Everything in that experiment is WT1-positive and A-two-positive. Where's the WT1-negative, A-two-positive line?

**Nadia:** Not there — and the authors say so explicitly in the discussion. Direct cytotoxicity against a WT1-negative, H-L-A-A-two-positive target in the primary T-cell killing assay was not performed, and is ongoing work. They had T2 with no peptide in the binding and reporter assays, but not in the primary C-D-eight killing format. Which is the format that matters, because an engager can kill at occupancies that don't register as binding.

**Theo:** That's the whole problem with the class. Weak binding plus a potent C-D-three arm equals killing.

**Nadia:** Sub-threshold binding, suprathreshold cytotoxicity. That's why the missing arm isn't a formality.

**Theo:** One more. They call their antibodies superior to the published comparators.

**Nadia:** Um — on the assays they ran, their leads do look better: cleaner on M13L and PIGQ, tighter footprints, fewer predicted proteome hits. But ESK1 didn't plateau at a hundred nanomolar in the T2 binding curve, so no E-C-fifty, and they hypothesise the single-chain trimer linker interfered with benchmark binding in the phage E-L-I-S-A. Those are comparator-disadvantaged conditions. It's a platform paper from a company selling the platform, so I'd read the benchmarking as directional, not head-to-head.

**Theo:** Connection — IMA401, episode seventy-one. T-cell receptor bispecific against MAGE-A4 slash A8, deliberately low-affinity C-D-three arm. Thirty-eight percent C-R-S, all grade one to two, twenty percent response rate at the recommended dose. Same target class solved from the receptor side, and it got through first-in-human. This paper argues an antibody paratope can reach the same footprint. Put it next to episode seventy-four — KRAS G12D TCR-like antibodies, where affinity maturation introduced a SARS-CoV-2 cross-reactivity that had to be sorted out.

**Nadia:** Same lesson from three directions: potency engineering degrades specificity, so the counter-screen has to be inside the loop.

**Theo:** Which is the paper's thesis. Takeaways. One: thirteen of twenty-six, fourteen of twenty-six — half a panel that passed S-P-R against irrelevant peptide-H-L-A bound a homologous off-target peptide on cells. If your specificity data is monomer S-P-R against unrelated peptides, you have not measured specificity. Two: the X-scan footprint is more informative than the proteome list — five contact positions versus one is a mechanistic account of why some binders in this class fail, measurable early. Three: the bispecific data is clean where it's controlled, and silent exactly where the field has been burned.

**Nadia:** That's fair.

**Theo:** So I'd believe the workflow enriches for tighter peptide footprints than the published benchmarks. I would not yet believe a specificity claim about ATX-TCRm-06 as a therapeutic.

**Nadia:** What I'd watch for: predicted proteome off-targets synthesised and tested on cells. Turn the algorithm's output into an experiment.

**Theo:** And mine — the WT1-negative, A-two-positive line in the primary C-D-eight killing assay. They say it's running.

**Nadia:** That's the paper. mAbs, D-O-I ten point one-oh-eight-oh, slash, one-nine-four-two-oh-eight-six-two-point-two-oh-two-six-point-two-seven-three-one-two-eight-two.

**Theo:** Thanks for listening.

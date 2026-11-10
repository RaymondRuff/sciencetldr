# Issue #108 — script (routine writer)

**Length:** 11,595 spoken chars (~10.8 min)  
**Episodes cited:** [83, 86]  
**Paper text from:** Publisher PDF staged in the private papers repository (emailed-pdf provenance), 23 pages, 56,412 characters of extracted text plus six figure images; Molecular Cancer Therapeutics, doi 10.1158/1535-7163.MCT-25-1542

| Run | Started (UTC) | Finished (UTC) | Safeguard stops |
|---|---|---|---|
| writer | 2026-11-10T08:09:59Z | 2026-11-10T08:21:25Z | 0 |

## Show notes

**[Aberrant expression of HERV-K envelope in lymphoma represents an opportunity for novel treatments](https://doi.org/10.1158/1535-7163.MCT-25-1542)**

*Molecular Cancer Therapeutics, 2026*

DOI: [10.1158/1535-7163.MCT-25-1542](https://doi.org/10.1158/1535-7163.MCT-25-1542)

**Question:** Does HERV-K (HML-2) envelope mark clinically relevant DLBCL states, and is it a usable surface target?

**Answer:** HERV expression mirrors the known ABC/GCB split but adds nothing independent of cell of origin, and Env reaches the surface of only 2 of 8 DLBCL lines; a humanized VHH-Fc, FF-01, drives NK killing and internalizes, with no Env-negative control in the 3D assay and no in vivo data.

**Three takeaways**

1. Discarded multi-mapping reads split 342 DLBCLs into 4 survival-distinct clusters mirroring ABC/GCB; not offered as prognostic.
2. Env was detected by qPCR in 8 of 8 lines, by immunoblot in 5, on the surface in 2; every functional result rests on RCK8.
3. FF-01 (Kd 142 nM against peptide 3) gave ~2.5x ADCC signal, NK killing in 2D and 3D, and ~1.5-fold selective internalization.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo. A target paper today, which I enjoy.

**Nadia:** We do. Molecular Cancer Therapeutics, from the Institute of Oncology Research in Bellinzona: aberrant expression of Herv-K envelope in lymphoma. A retrovirus that entered our ancestors' germline millions of years ago is switched back on in some lymphomas, and its envelope protein reaches the cell surface.

**Theo:** Okay. Why does that get ten minutes?

**Nadia:** Because the scarce thing in this kind of engineering isn't the binder, it's the antigen. You can raise an arm against almost anything; what you can't manufacture is a protein that sits on tumour cells and nowhere else. These elements are methylated and quiet in healthy tissue, and in cancer that silencing slips.

**Theo:** So the target would be defined by broken regulation rather than lineage — unlike the antigens we already drug, where hitting C-D-nineteen takes the normal B cells too. How much of this material is in the genome?

**Nadia:** Nearly half of it is transposable elements, and endogenous retroviruses are up to about eight percent. Most of that is invisible in standard analysis: the sequences repeat all over the genome, so the reads multi-map and get discarded. The family here is Herv-K, the subgroup H-M-L-two, which still has intact reading frames.

**Theo:** Huh — a whole layer routine work throws away. Flag before we go on, though: these envelope genes aren't all junk. Some have real jobs.

**Nadia:** Good flag. The syncytins, which let trophoblasts fuse in the placenta, are domesticated retroviral envelope genes. So "it came from a retrovirus" doesn't mean the body treats it as foreign, or that it's absent from normal tissue.

**Theo:** Noted. What's the central claim?

**Nadia:** Three linked ones, and I'd grade them separately. That Herv-K expression marks real states in diffuse large B-cell lymphoma. That the envelope protein is on the surface and the cell needs it. And that an antibody to it can direct killing.

**Theo:** Start with the patient data.

**Nadia:** Two published sequencing cohorts of D-L-B-C-L plus sorted healthy B cells, reprocessed with a tool that assigns those ambiguous reads to specific loci. About three hundred and forty tumours, four clusters, different survival under standard chemo-immunotherapy.

**Theo:** Which sounds like a new prognostic classifier, and I'd normally be suspicious.

**Nadia:** Be suspicious, then give them credit, because they got there first. The clusters track the split everyone already uses, activated B-cell-like versus germinal-centre, and with cell of origin in the model they add nothing independent. They decline to call it a prognostic tool.

**Theo:** And tumour against normal?

**Nadia:** Many Herv-K elements run higher in tumours, one provirus especially, K-one-one-three. The high expressors also light up interferon signalling — viral mimicry, where the cell sees its own derepressed retroviral transcripts and responds as if infected.

**Theo:** That's a pathway signature. Not a measurement of protein.

**Nadia:** Correct, and that's the hinge. Message is where the patient data stops. Everything about protein on the surface happens in cell lines.

**Theo:** Give me the cell lines.

**Nadia:** Eight D-L-B-C-L lines, three assays. By quantitative P-C-R, the envelope message is detectable in all eight. By immunoblot — total protein in the lysate — five of eight. On the surface, by flow cytometry, two of eight.

**Theo:** Oh — that's a brutal funnel. Eight, five, two.

**Nadia:** It's the most informative number here, and they draw it as a panel rather than burying it. The attrition isn't mysterious — premature stop codons, and a heavily glycosylated protein whose trafficking decides whether it reaches the membrane. But the therapeutic argument applies only to the last column.

**Theo:** And of those two, is one doing the heavy lifting?

**Nadia:** Um — yes. Essentially everything functional is one line, which is also the only line carrying the K-one-one-three provirus, on one chromosome.

**Theo:** Wait. That insertion isn't in everyone's genome?

**Nadia:** No, it's polymorphic — something like a quarter of people overall, roughly half in African-ancestry cohorts. Other lines make envelope without it, from other family members, and the targeted peptide is conserved across the family. So it isn't one locus — but envelope-positive isn't a clean genotype.

**Theo:** Second half of that claim — the cell needs it.

**Nadia:** Two small interfering R-N-As against separate parts of the transcript. Each knocks the protein down by about half, and proliferation over three days is roughly halved against scrambled control. Viability barely moves, so it's growth, not killing.

**Theo:** How many replicates behind the knockdown?

**Nadia:** [thoughtful] Two, and for one guide they disagree with each other quite a bit. In one line. So — consistent with envelope contributing to growth, not a demonstrated dependency. It isn't a passenger; how hard the cell leans on it is untested.

**Theo:** Now the part I came for. Where does the antibody come from?

**Nadia:** They modelled the envelope, picked four candidate epitopes on the extracellular portion avoiding glycosylation sites and cysteines, and made them as peptides. Those do double duty. First, serology: a hundred and fifty lymphoma sera screened, and about a third were positive for the best peptide.

**Theo:** A third. Against what baseline?

**Nadia:** That's the problem. There's no healthy-donor comparison in the paper, and given what we said about normal tissue, a frequency with no control group can't say whether this is tumour-associated or background. The assay is validated on a dilution series, so it measures something. It has no denominator.

**Theo:** And the second use of the peptides?

**Nadia:** Selection. A camelid single-domain library — nanobodies — by phage display against those immobilised peptides. Two came out, one held up by surface plasmon resonance. They humanised it onto a human I-g-G-one Fc, so it's heavy-chain-only but still engages Fc receptors. They call it F-F-oh-one.

**Theo:** Affinity?

**Nadia:** A dissociation constant of one hundred and forty-two nanomolar. To the peptide.

**Theo:** To the peptide. Not to envelope on a cell.

**Nadia:** Not to envelope on a cell. There's flow binding to positive lines and none to negative lines — the qualitative version — but no affinity against native protein and no copies-per-cell figure. Mid-nanomolar against a fragment is a starting point, not a candidate, and they say as much.

**Theo:** Is the epitope even reachable on the real thing?

**Nadia:** They checked, and I liked it. Experimental structures appeared only recently, and they went back and computed solvent accessibility on the single subunit and the assembled trimer. It stays exposed in both.

**Theo:** So what does the antibody do?

**Nadia:** Nothing alone — no direct anti-tumour activity, reported plainly. The activity is antibody-dependent cytotoxicity: in the reporter assay the envelope-high line gives roughly two and a half times baseline at six hours, and the negative line nothing.

**Theo:** With actual N-K cells?

**Nadia:** Primary N-K cells from healthy donors. In the high expressor, four replicates, all the same direction, and it separates. In the lower expressor, three replicates, and it doesn't clear significance.

**Theo:** But the text calls that confirmation.

**Nadia:** It does, and that's where the writing gets ahead of the figure. One line killed; one trend in the same direction that didn't reach threshold.

**Theo:** There's a three-dimensional model too.

**Nadia:** The nicest piece of design here. Lymphoma cells in a fibrin gel with primary N-K cells and bone marrow stromal cells from knee-replacement donors, imaged live for three days. Lymphoma area under the antibody falls to about sixty percent of isotype by day three; the stromal cells are unaffected.

**Theo:** And they read the stromal cells as the specificity control.

**Nadia:** They call it a strong on-target effect, yes.

**Theo:** I don't buy it, and it bothers me because the fix is in their own freezer. A stromal cell is a different cell type doing a different thing. The control that settles this is an envelope-negative lymphoma line in the same gel. They have those lines.

**Nadia:** Agreed, that's the missing experiment. And the stromal readout is occupied area with wide spread between donors — blunt, even as the right control.

**Theo:** The drug-conjugate angle — internalisation.

**Nadia:** Taken up by envelope-positive cells, faster and higher than the non-binding nanobody, and in the negative line the ratio goes the other way, below one. Right shape for specificity. But the non-binder internalises substantially too — the separation is about one and a half fold.

**Theo:** Here's the thing nobody can fix. There's no animal work, and I don't think there could be.

**Nadia:** Right. Herv-K is human-specific. No mouse carries this target, so the normal-tissue safety question can't be asked the standard preclinical way. They frame the three-dimensional culture as a replacement-aligned alternative, which is fair, but it answers efficacy, not toxicity.

**Theo:** And toxicity is the question for a target defined by epigenetic leakage.

**Nadia:** Which brings back the syncytins. What decides tumour-restriction is surface staining on primary patient cells and on normal tissue, with this antibody. That doesn't exist yet.

**Theo:** One disclosure first: the institutes have filed a patent on reagents targeting endogenous retroviruses to kill cancer cells, with several authors as inventors. Declared up front — context, not a reason to doubt the data. Now, two connections, pulling opposite ways. In episode eighty-six, the M-R-one nanobodies had lovely ligand discrimination, but every tumour-killing experiment pulsed the targets with synthetic antigen, because no endogenous ligand had been shown at sufficient density. Here nobody loaded anything.

**Nadia:** Which is the harder standard, and they cleared it. The flip side is that density becomes the finding, and the finding is two lines out of eight.

**Theo:** And that's where the other one bites. Episode eighty-three, the W-T-one peptide-H-L-A antibodies: clean on the biosensor, and on cells half the panel bound a peptide it shouldn't have. Specificity failures don't show up in the purified assay. They show up on cells.

**Nadia:** Hmm. And there's no counter-screen of that kind here. Binding to negative lines is the only negative evidence — a handful of lymphoma lines, not a proteome, not normal tissue. So the specificity claim is untested rather than contradicted, but untested where it caught the earlier one out.

**Theo:** Alright. Three takeaways. First: quantifying endogenous retroviruses at individual loci, from reads routine pipelines discard, reconstructs the known subtypes of this lymphoma — real signal, and not sold as a prognostic tool.

**Theo:** Second: envelope is detectable by message in all eight cell lines, by blot in five, on the surface in two — and every functional result rests on one of those two, which is also the only line carrying that polymorphic provirus.

**Theo:** Third: the antibody is a real proof of principle — N-K killing in two and three dimensions, and internalisation — but selected and measured against a peptide at mid-nanomolar affinity, with no envelope-negative lymphoma control in the three-dimensional assay.

**Theo:** So I'd believe the antigen is on some lymphoma cells and does something for them. I wouldn't yet believe it's tumour-restricted.

**Nadia:** Same here.

**Theo:** What would change your mind?

**Nadia:** Surface staining on primary patient tumour cells, with copies per cell, against normal human tissue in the same assay. If it's on patient cells and absent elsewhere, this becomes a programme.

**Theo:** Mine's cheaper. Put an envelope-negative lymphoma line in that fibrin gel, same N-K cells, same antibody. If the negative line dies too, nothing upstream matters.

**Nadia:** That would settle a lot. So: Molecular Cancer Therapeutics, D-O-I ten dot one one five eight slash one five three five dash seven one six three dot M-C-T dash two five dash one five four two. Thanks for listening.

**Theo:** See you next time.

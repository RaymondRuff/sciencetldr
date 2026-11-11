# Issue #113 — script (routine writer)

**Length:** 11,599 spoken chars (~10.8 min)  
**Episodes cited:** [81, 90]  
**Paper text from:** Staged bundle in the private papers repository: RFD4-Proteina white paper PDF, https://rfd4-proteina.org/assets/paper/RFD4-Proteina.pdf (169,995 chars of text plus 104 figure images)

| Run | Started (UTC) | Finished (UTC) | Safeguard stops |
|---|---|---|---|
| writer | 2026-11-11T08:06:32Z | 2026-11-11T08:16:23Z | 1 |
| checker | 2026-11-11T11:16:21Z | 2026-11-11T11:25:00Z | 0 |

## Corrections made by the fact-check pass

- Nadia called the paper the work of the Institute for Protein Design 'together with Nvidia', and Theo spoke of 'the two organisations on the author list'; the author list spans some twenty affiliations (Oxford, Manchester, Southampton, ETH Zurich, Tsinghua and others), so both lines now say IPD and Nvidia led it with academic collaborators, and Nadia's closing question asks for reproduction outside the collaboration.
- Theo's first takeaway said the model 'beats each specialist'; the paper claims only that it performs 'equivalently to or better than' specialist methods, and for ensemble-based filtering it merely matched PLACER. Changed to 'matches or beats', which is also what the show notes say.
- Nadia said the best phosphotriesterase was 'not a fast one next to the natural enzyme family'; the paper never compares the designs with a natural phosphotriesterase, only with uncatalysed hydrolysis and with the authors' earlier designs. Replaced with that stated comparison.
- Nadia called lenacapavir 'the long-acting H-I-V prevention drug'; the paper says only that it is a highly effective HIV-prevention drug whose manufacturing cost is a barrier to access. 'Long-acting' is outside knowledge and was cut.
- Nadia said the catalytic-cysteine knockout 'lost the activity'; the knockout panel (Fig. 6m) is vector art with no values in the text, which states only that the two best designs rely on the designed Cys nucleophile. Softened to that.
- The script gave the ligase enantioselectivity as seventy-nine percent against 'under ten percent of the mirror-image one, with no-enzyme controls near background', which reads as clean selectivity; the (R)-amine conversion was 8.8% against a 4.3% no-enzyme control, about twofold. Theo now says the preference is real but not clean.
- Nadia said the glycan designs shield the sugar so trimming enzymes 'can't process it'; the paper reports designs that retain predominantly Man9 and Glc1Man9, i.e. processing is restricted, not abolished. Softened to 'mostly leave it alone'.
- The clustered pass rate was described as 'distinct passing structures per attempt'; the metric counts distinct passing structural clusters (Foldseek, TM-score 0.5) per attempt.
- Episode ninety callback said a huge fraction of designs 'never expressed'; that episode's card records the dropout as read as failed expression, folding or solubility. Changed to 'never showed up in the pool'.
- Episode eighty-one callback said the non-learned consensus method 'placed third'; kept the card's substance but stated it as beating most of the neural networks, to spend the figure budget on this paper's own numbers.
- Cut roughly a dozen spoken figures to bring the episode inside the fifteen-to-twenty-five budget and the two-per-turn limit: the forty-fold throughput ratio, the low- and high-thinking pass rates, the five-hundred-trajectory count, the one- and two-residue off-target differences, the eighteen-of-sixty cross-campaign denominator left in place but the eighty-four percent restated as 'that hit rate', and the sixteen-hour incubation. The phosphotriesterase turn carried four values and was split across two turns.
- Turn with the phosphotriesterase screen stacked three values (288 tested, 89 active, 25 of 47 scaffold families); the denominator is now spoken as just under three hundred, the scaffold-family spread moved into Theo reaction, and the exact 89 of 288 is in the show notes.

## Show notes

**[Biomolecular design through latent reasoning with RFD4-Proteina](https://rfd4-proteina.org/assets/paper/RFD4-Proteina.pdf)**

*White paper — UW Institute for Protein Design & NVIDIA, 2026*

Source: [https://rfd4-proteina.org/assets/paper/RFD4-Proteina.pdf](https://rfd4-proteina.org/assets/paper/RFD4-Proteina.pdf)

**Question:** Can one generative model span proteins, sugars, DNA and RNA in a shared latent space, and does inference-time compute improve real design success?

**Answer:** On the authors' own AF3-judged benchmarks it leads every baseline (10.6% vs 5.9% clustered pass rate for protein binding), and wet-lab results follow across binders, glycans and enzymes — but no evaluation was blinded or independent.

**Three takeaways**

1. One model matches or beats specialist tools for packing, inverse folding and refinement, with AlphaFold3 as judge throughout.
2. Strongest evidence: 89 of 288 phosphotriesterase designs were active, against 0 of 192 from the same lab's previous model.
3. The 158/188 TrkA hit rate is compared across other groups' campaigns, assays and hit definitions, not a controlled test.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** And today we're taking on a big one: 'Biomolecular design through latent reasoning with R-F-D-four Proteina'. It's self-published — led by the Institute for Protein Design in Seattle and Nvidia, with academic collaborators — and it has not been peer reviewed. Hold onto that for the next ten minutes.

**Theo:** It's a long one, too. So why this paper? Design models come out most months.

**Nadia:** Two reasons, both about method. First, the representation. Most design models are built around protein, and everything else — a sugar, a nucleic acid, a modified residue — is bolted on. Here an autoencoder puts every building block into one shared latent space: amino acids, modified ones, sugars, D-N-A, R-N-A. Each becomes an anchor atom plus a learned vector, and the model samples identity and geometry together in that space.

**Theo:** So identity stops being a label you pick and becomes a coordinate you move through.

**Nadia:** That's the idea, and they check it: nucleotides sit next to their counterparts almost every time, modified amino acids next to their parents less than half the time.

**Theo:** Huh. The second number is much weaker than the first.

**Nadia:** It is, and they report it rather than bury it. They also fine-tune the decoder against a Rosetta energy term, so what comes out is physically plausible.

**Theo:** Okay, and the second reason?

**Nadia:** The word in the title: reasoning. Um — it's doing two jobs. Inside the network they recycle — run the same block over its own output several times — but at every denoising step, rather than once up front. So the model can spend more compute at the stages that matter.

**Theo:** Which they market as low, medium and high thinking.

**Nadia:** They do. And outside the network there's search: generate many trajectories, kill the ones that look bad, on whatever criterion you like.

**Theo:** Right, but a search that kills candidates early only helps if you can tell early. Can you?

**Nadia:** That's the nicest observation in the paper. Across their trajectories they asked when each property becomes predictable from a half-finished design. Interface area settles early, hydrogen bonding in the middle, the folding model's confidence in the interface only at the very end.

**Theo:** Ah — so you prune on area first, then bonding, then confidence.

**Nadia:** Exactly, each criterion when it becomes informative. On their enzyme example, about three times as many passing designs per hour of compute.

**Theo:** Okay. Give me the central claim, then, so we can test it.

**Nadia:** That putting all this chemistry in one latent space, and adding compute at inference, buys two things at once — higher design success and higher throughput — and that it shows up in the wet lab, not just in a scoring function.

**Theo:** Two things at once is the part I'd push on. Those usually trade.

**Nadia:** The in-silico half first. Four benchmarks: protein binding, small-molecule binding, enzyme active-site scaffolding, D-N-A binding. The metric is a clustered pass rate — distinct passing structural clusters per attempt, where passing means an independent fold prediction agrees with the intended design.

**Theo:** Which fold predictor?

**Nadia:** AlphaFold three.

**Theo:** Mm. So the oracle scoring the designs is the same family of model the field now designs against.

**Nadia:** Yes. It's self-consistency, not truth, and that's the biggest caveat on this half of the paper. With that said: on protein binding they report about eleven percent passing clusters against roughly six for the next-best method, and far more designs per hour of compute.

**Theo:** That's a wide margin.

**Nadia:** It is. And the thinking settings do move it — low thinking lands a few points below the high setting on that same benchmark.

**Theo:** And what does the high setting cost?

**Nadia:** Throughput drops by more than half. It's buying success rate with compute, which is the honest way to put it.

**Theo:** My problem with the throughput axis is that designs per hour of G-P-U time is an engineering number — it depends on how hard someone optimised the code, and on the hardware.

**Nadia:** And one of the groups on the author list makes the hardware. They say so, on the first page.

**Theo:** That axis compares engineering effort as much as it compares models. The pass rate is the part that travels.

**Nadia:** Agreed. And every baseline here was run by this group, with their settings and their pass criteria. That's not a question of honesty, it's just what a self-run benchmark is.

**Theo:** Which is what we saw done properly in episode eighty-one — the blinded antibody challenge, where the organisers held the answers and entrants never saw the assay. Nobody has done that for structure-based design at this scale.

**Nadia:** No. And it matters, because when that blinded test did happen, a non-learned consensus method beat most of the neural networks.

**Theo:** Okay. The wet lab — that's where I want to spend our time.

**Nadia:** Mm-hm. So do I, and it is substantial. Binders first: proteins that bind calmodulin only when it has calcium bound. Twelve of eighteen designs tested did exactly that — tight binding with calcium, nothing detectable without it.

**Theo:** That's a conformational state, not just a surface. That's hard.

**Nadia:** It is. The tightest is quoted in the low picomolar range, and — credit where it's due — the authors flag that the estimate sits at the limit of what their instrument resolves. So it's a bound, not a measurement.

**Theo:** Good. That's the sentence I look for and usually don't find.

**Nadia:** Then peptide-M-H-C binders, where the hard part is telling the right peptide from near-identical ones presented the same way. They report over a hundred-fold preference for the intended peptide in every case — and the two hardest off-targets differed from their targets by only a residue or two.

**Theo:** Wait — how were those affinities measured?

**Nadia:** Yeast display with tetramers.

**Theo:** So that's avidity — multiple sites on the reagent, cells covered in binder. The apparent affinity will look better than a one-to-one measurement would.

**Nadia:** Which they label as apparent, correctly. The ranking is the useful part there, not the absolute numbers.

**Theo:** Fine. And the headline binder result?

**Nadia:** Human Trk-A, the kinase receptor, which has become the field's standard target. They ordered a hundred and eighty-eight designs.

**Theo:** And how many bound?

**Nadia:** A hundred and fifty-eight of them, below a micromolar.

**Theo:** Oh. That's most of the plate.

**Nadia:** It is. And they set it beside published campaigns from other groups — the next best of those is eighteen of sixty.

**Theo:** Hmm. That's the figure everyone will quote, and it's the weakest comparison in the paper. Different labs, different years, different numbers ordered, different definitions of a hit. That bar chart is not a controlled experiment.

**Nadia:** No. The within-paper comparisons are the ones that bear weight. On selectivity: binders to human Trk-A that avoid the mouse version, which shares most of its sequence across the modelled region — and, separately, designs hitting both species while avoiding the two human relatives. Eighteen of ninety-four came out with that full pattern.

**Theo:** That I like. Designing for a specificity pattern rather than affinity, and measuring against off-targets nominated in advance.

**Nadia:** They also went after intrinsically disordered peptides — no fixed shape to design against — and got binders to most of them, including a couple nobody had designed against before.

**Theo:** With specificity data?

**Nadia:** An all-by-all panel, five binders against five peptides. Each preferred its own target. One measurement per pair, though.

**Theo:** And the non-protein work?

**Nadia:** Two pieces. Small proteins that shield a sugar so the cell's trimming enzymes mostly leave it alone — that's a vaccine-adjuvant trick — and binders that recognise a peptide only when it carries a phosphate, and can tell one phosphorylation site from the one next door.

**Theo:** Sample sizes?

**Nadia:** Nine glycan designs profiled. It's a plate-scale screen.

**Theo:** Right. Encouraging, not established. Let's do the enzymes — that's where I'd expect a model like this to break.

**Nadia:** Two. So — the first hydrolyses paraoxon, an organophosphate. Their previous model scaffolded six catalytic residues around the bimetallic centre; here they added two more, which demands a more precise active site.

**Theo:** And did that survive contact with a plate?

**Nadia:** They tested just under three hundred designs, and eighty-nine of them were active.

**Theo:** And their previous model, on the same site?

**Nadia:** Nothing. No active designs at all, out of the hundred and ninety-two they tested.

**Theo:** Oh — that's a head-to-head. Same lab, same assay, same people pipetting, and the hits spread over more than half the scaffold families they tried. That's the result I'd build an argument on, not the bar chart.

**Nadia:** And the best one is roughly a thousandfold more efficient than their earlier designs. Though the comparison they reach for is uncatalysed hydrolysis — they never set it beside a natural phosphotriesterase.

**Theo:** And the second enzyme?

**Nadia:** A ligase — it forms an amide bond, and the step they chose is from the synthesis of lenacapavir, an H-I-V prevention drug. The chemistry is awkward: the catalyst has to push an activated ester toward reaction with a bulky amine rather than letting it hydrolyse in water.

**Theo:** And — did it?

**Nadia:** Four designs out of sixty-seven worked, where their previous model gave none. The best converted about eighty percent of the intended amine to product. They also knocked out the catalytic cysteine — both of the best designs depend on it.

**Theo:** The knockout control matters — that tells you the designed chemistry is doing the work, not some accidental surface.

**Nadia:** Yeah. Though with the mirror-image amine it still reached only about twice its own no-enzyme control, so the preference is real but not clean. And what's missing is kinetics: these are endpoint measurements, so we know it turns over, not how fast or for how long.

**Theo:** Which is the whole question for anything industrial. Conversion after a long incubation says the reaction happens, not that it pays.

**Nadia:** Agreed. The authors call it a proof of concept, and that is the right label for it.

**Theo:** One more thread — episode ninety, the competition where twelve thousand designed binders went into a pooled cell assay. Every structure-based confidence score there failed to predict which designs would work, and a huge fraction simply never showed up in the pool.

**Nadia:** Here the denominator is genes ordered, so anything that failed to express counts against them. That's the right denominator.

**Theo:** It is. But these are still one lab's expression pipeline and one lab's filters. Somebody else running these weights will not get that hit rate.

**Nadia:** Almost certainly not. Though the weights and code are out under a permissive licence, so that's a testable prediction, not an argument.

**Theo:** Which is the best thing about this paper, honestly. Let me do takeaways.

**Nadia:** Go ahead.

**Theo:** One: a single model now covers chemistry that used to need a shelf of specialist tools — packing, inverse folding, sugars, nucleic acids — and on the authors' own benchmarks it matches or beats each specialist, with a structure predictor as judge throughout. Two: the strongest evidence is the phosphotriesterase — eighty-nine active designs where their own previous model gave none, same lab, same assay. Three: the eye-catching binder hit rate compares other people's campaigns, and isn't a controlled result.

**Nadia:** What would change your mind?

**Theo:** Kinetics on the designed ligase. If it turns over fast enough to run a process on, this is a different paper. You?

**Nadia:** Someone outside this collaboration reproducing a hit rate with the released weights, on a target the authors didn't pick. Not a benchmark — a campaign.

**Theo:** Agreed. Until then I'd believe the enzyme comparison and the specificity designs, and hold the rankings loosely.

**Nadia:** That's where I am too. No journal and no D-O-I on this one — it's a white paper, posted with the weights and the code. Thanks for listening.

**Theo:** See you next time.

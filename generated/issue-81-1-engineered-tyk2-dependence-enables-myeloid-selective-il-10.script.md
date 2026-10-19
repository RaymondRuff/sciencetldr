# 1. Engineered TYK2 dependence enables myeloid-selective IL-10 receptor agonism

**DOI:** 10.1038/s41586-026-11176-1  
**Length:** 10990 chars (~10.4 min)

## Corrections made by the verification pass

- Cut the episode 54 callback: the memory card describes dual-tumour-antigen co-engagement and affinity tuning, not receptor-copy-number gating, and the draft carried four callbacks (47, 63, 54, 69) against the three-callback limit; kept 47, 63 and 69.
- Nadia called IL-10 'the central anti-inflammatory cytokine'; the paper says 'a central anti-inflammatory cytokine'.
- Nadia said native IL-10 'loses most of its TNF suppression' in R117C/R117H/Y64C cells; the paper reports TNF suppression was 'markedly impaired' — softened to match.
- Nadia said the agonist 'matches IL-10-Fc' in all three in vivo models; the paper states equivalent suppression explicitly only for the LPS challenge, so the DTH and DSS results are now stated as reported (ear swelling, draining-node neutrophils, colon weight-to-length ratio) without claiming measured equivalence.
- Added attribution for the structural claim ('The authors report it is') and for the mechanistic account ('on their interpretation'), which are the authors' interpretation rather than directly demonstrated.
- Monomer limitation restated: the paper lists reduced potency for both TNF and IL-6 suppression, not only IL-6.
- Specified that the partial pSTAT3 retained by non-selective tetravalent agonists in TYK2-knockout cells was measured in the STAT3-luciferase reporter line, not primary macrophages.
- Changed 'those are approved drugs' to 'in clinical use' — the TYK2 inhibitor used in the paper (zasocitinib) is investigational.
- Overexpression result: 'largely comes back' changed to 'substantially', matching the paper's 'substantially restored'.
- T/NK redirection: the paper describes two lead constructs, so 'That bispecific' corrected to 'Those bispecifics'.
- Symmetric-construct arm description corrected: A05-A05/E07-E07 places the two IL-10R-beta binders on one arm and the two IL-10R-alpha binders on the other (draft had the order reversed).
- Trimmed setup, framing and callback text to bring the script from 11,076 characters into the target window, leaving all numbers and limitations intact.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo.

**Nadia:** And today, 'Engineered TYK2 dependence enables myeloid-selective IL-10 receptor agonism', in Nature. Short version: a four-armed nanobody that switches on IL-10 signalling in monocytes and macrophages but not in T cells — and the selectivity comes from the shape of the molecule, not from what it binds.

**Theo:** Okay — why is this worth ten minutes? Selective cytokine agonists aren't new.

**Nadia:** No. What's new is the lever. Most attempts at selective IL-10 have been affinity tuning — mutate the cytokine so it engages one receptor chain more weakly. Here the binders are high affinity, and selectivity falls out of valency and cross-linking geometry. And there's a cryo-EM structure of that geometry, not an inference from activity.

**Theo:** Set up the problem. Why has IL-10 failed as a drug?

**Nadia:** IL-10 is a central anti-inflammatory cytokine — loss-of-function mutations in it or its receptors cause early-onset inflammatory bowel disease. It signals through a pair of chains: IL-10R-alpha, carrying JAK1, and IL-10R-beta, carrying TYK2. That pair sits on myeloid cells and on lymphocytes, and at higher concentrations IL-10 stimulates T cells.

**Theo:** And that's what killed it clinically?

**Nadia:** Mm-hm. Crohn's and psoriasis trials hit a narrow therapeutic window — dose-limiting anaemia and thrombocytopaenia, which the authors attribute to unintended T and B cell activation. Meanwhile that same T cell arm drove pegylated IL-10 as a cancer immunotherapy. Same molecule, opposite programmes.

**Theo:** Right. So what makes the engineering possible?

**Nadia:** The kinase wiring. Native IL-10 is a domain-swapped dimer; it assembles two alphas and two betas, and that lets JAK1 be activated two ways — JAK1 phosphorylating JAK1 across the complex, or TYK2 phosphorylating JAK1.

**Theo:** Two routes to the same output.

**Nadia:** Right. In macrophages, either route will do. Knock out TYK2, or use the TYK2 inhibitor zasocitinib, and pSTAT3 drops partially — but suppression of LPS-induced TNF and IL-6 is unaffected. In CD8 T cells it's the opposite: TYK2 inhibition or CRISPR knockout drops pSTAT3 and completely abolishes the rise in granzyme B and interferon-gamma.

**Theo:** Huh. So the T cells are the fragile ones.

**Nadia:** That's the asymmetry. And they back it with an engineered IL-10 monomer that engages only one alpha-beta pair — about fifty percent of maximal pSTAT3 in blood monocytes, still substantial TNF suppression, and no detectable pSTAT3 in T cells.

**Theo:** So why not just develop the monomer?

**Nadia:** They're straightforward about that. It's thermally unstable, vulnerable to the anti-IL-10 autoantibodies reported in IBD, and less potent on TNF and IL-6 suppression. So they went to nanobodies — single-domain antibodies, twelve to fourteen kilodaltons — raised in alpacas against the receptor ectodomains.

**Theo:** Against the receptor, not the cytokine. How many did they build?

**Nadia:** Eight hundred and eighty-two combinations, formatted as tetravalent Fc fusions — two tandem nanobodies per arm. A hundred and eighty-two gave STAT3 reporter activity. Twenty-one cleared ninety percent TNF and eighty-five percent IL-6 inhibition in LPS-stimulated PBMCs.

**Theo:** And how many of those twenty-one were selective?

**Nadia:** Um — essentially one. Most recapitulated the T cell stimulation of native IL-10. The lead pairs an anti-IL-10R-alpha nanobody, E07, with an anti-IL-10R-beta, A05, in each Fc arm. IC50 of 2.1 picomolar for TNF suppression, 6.9 picomolar for IL-6, with no significant interferon-gamma or granzyme B in T cells and no B cell proliferation.

**Theo:** Wait — one out of nearly nine hundred. So this was found, not designed.

**Nadia:** That's the honest reading. The screen was empirical; the geometry explanation came afterwards, from the structures. It doesn't make the mechanism wrong, but their 'geometry-based strategy' framing is retrospective.

**Theo:** Okay. The structures.

**Nadia:** Two cryo-EM maps. The full complex — both receptor ectodomains plus the tandem nanobody — is only about seventy-eight kilodaltons, small for cryo-EM, so they used an anti-nanobody Fab as a fiducial. That map is 3.14 angstroms; a second, IL-10R-alpha with E07 alone, is 2.40 angstroms.

**Theo:** And the geometry is genuinely different from the cytokine's?

**Nadia:** The authors report it is. A05 binds IL-10R-beta on a surface partly overlapping the cytokine site, but it remodels a loop — asparagine 138 to tryptophan 143 — folding two residues into a cleft between CDR2 and CDR3. E07 binds IL-10R-alpha elsewhere, across the junction between two fibronectin type three domains, on the opposite side from the IL-10 site.

**Theo:** Does that opposite face buy them anything?

**Nadia:** One of the nicer results. A substantial fraction of very-early-onset IBD patients carry IL10RA mutations in the cytokine-binding interface. In cells expressing R117C, R117H or Y64C, native IL-10's TNF suppression is markedly impaired and the detuned muteins fare worse. The agonist retained full activity — it never touches that surface.

**Theo:** Hm. That's a real differentiation argument.

**Nadia:** And the geometry dependence is tested properly. Shorten or lengthen the glycine-serine linker between the two nanobodies and activity drops substantially. Reverse the order — beta-binder first — and there's no detectable signalling in the reporter.

**Theo:** Same binders, same affinities, no signal.

**Nadia:** None. And the variant I'd weight most: a symmetric construct — two beta-binders on one arm, two alpha-binders on the other — is a stronger myeloid agonist, and it brings T cell activation back, about twenty percent of the interferon-gamma response to native IL-10.

**Theo:** So what's the cause? Geometry is a description.

**Nadia:** Two linked things, on their interpretation. The cross-linking the lead imposes doesn't support productive JAK1-JAK1 transphosphorylation, so signalling becomes strictly TYK2-dependent — delete or inhibit TYK2 and the lead does nothing in macrophages, while the non-selective tetravalent agonists keep partial pSTAT3 in TYK2-knockout reporter cells.

**Theo:** And the second?

**Nadia:** Receptor density. Myeloid cells carry two- to eighteen-fold more surface copies of both chains than T, B or NK cells — measured with calibration beads across nine donors. An attenuated signal needs that abundance to cross threshold.

**Theo:** How do they make that causal rather than correlative?

**Nadia:** Overexpression. Push IL-10R-alpha on activated CD8 T cells up to monocyte-like levels and pSTAT3 to the agonist substantially comes back; add IL-10R-beta too and you get granzyme B. Beta alone, TYK2 alone or JAK1 alone doesn't do it.

**Theo:** Yeah. That's the right experiment.

**Nadia:** And then they run it backwards. If density is the lever, pair IL-10R-alpha with something enriched on lymphocytes — IL-2R-gamma, the common gamma chain, about tenfold higher on T and NK cells. Those bispecifics gave STAT3 agonism in T and NK cells with minimal monocyte activity.

**Theo:** That predicts how to invert it, and it inverts. Alright — in vivo.

**Nadia:** So — the molecule has no mouse cross-reactivity, so in vivo work runs in knock-in mice carrying humanised IL-10R-alpha and IL-10R-beta ectodomains on mouse cytoplasmic tails. In LPS challenge, agonist and IL-10-Fc suppressed serum TNF, IL-6 and IL-12 equivalently. In KLH hypersensitivity, less ear swelling and fewer draining-node neutrophils; in DSS colitis, a better colon weight-to-length ratio.

**Theo:** Ah — equivalent to IL-10-Fc, not better.

**Nadia:** On efficacy, yes — the claim is equivalence on efficacy, difference on toxicity. The toxicity work is in cynomolgus monkeys: a humanised version, terminal half-life around eight days, sustained receptor occupancy on monocytes, and ex vivo LPS challenge of whole blood showing suppressed TNF more than three weeks after one dose.

**Theo:** Against native IL-10's half-life of a few hours.

**Nadia:** Two point seven to four point five hours in humans. And the safety readout — IL-10-Fc induced IL-18, a reported biomarker for T cell activation and haematological toxicity in cynos, at 0.25 milligrams per kilogram, plus thrombocytopaenia and anaemia. The agonist showed no significant dose-dependent IL-18 rise and no haematological abnormalities up to a hundred milligrams per kilogram.

**Theo:** Oh — that's a four-hundred-fold gap in dose.

**Nadia:** It is. It's also — I mean, more precisely — a single-dose study in healthy animals, and the comparator is the molecule already known to be toxic.

**Theo:** What else would you want?

**Nadia:** Hmm. Two things. One falls out of their own mechanism: if efficacy is strictly TYK2-dependent, then a patient on a TYK2 inhibitor — and those are in clinical use — would lose the therapy. That interaction is designed in, and it isn't discussed.

**Theo:** Or people carrying TYK2 loss-of-function variants.

**Nadia:** Right. The other is that the cryo-EM is of two ectodomains with a tandem nanobody — not the intact tetravalent molecule, and not on a membrane. The full assembly is a composite model, and the linker itself wasn't resolved.

**Theo:** Do they concede anything themselves?

**Nadia:** Cleanly, yes. They say receptor abundance emerged as the determinant but that other mechanisms may contribute — higher signalling thresholds in T cells, phosphatases damping IL-10R signalling. They don't over-own the copy-number story.

**Theo:** There's a pattern worth naming. Episode 47, domain rearrangement on dual engagement; episode 63, the pH-switch CD3 binders where the causative mutations didn't contact antigen. Geometry rather than affinity as the lever. Difference is, 63's mechanism came from simulation — this one from a map and a topology swap.

**Nadia:** That's the contrast I'd draw. The other one is density gating — episode 69, where killing started around a thousand EGFR per cell but normal epithelium carries forty to a hundred thousand. Two- to eighteen-fold isn't obviously more generous.

**Theo:** Though here, being wrong means T cell stimulation, not cytotoxicity.

**Nadia:** A softer failure mode. Worth saying out loud before anyone ports this to a CD3 arm.

**Theo:** Three takeaways. One: myeloid IL-10 signalling tolerates losing TYK2 and still suppresses TNF and IL-6, while in CD8 T cells TYK2 inhibition or knockout abolishes the granzyme B and interferon-gamma response — shown pharmacologically and genetically.

**Theo:** Two: one molecule out of eight hundred and eighty-two was both low-picomolar on myeloid suppression and silent on T cells, and the linker, topology and symmetry variants show selectivity tracks geometry rather than occupancy.

**Theo:** Three: the selectivity is receptor-density-gated, and they showed it in both directions — restoring T cell signalling by overexpressing IL-10R-alpha, and redirecting agonism to T and NK cells with an IL-2R-gamma arm.

**Nadia:** And what you'd believe?

**Theo:** I'd believe the mechanism, and the preclinical separation of myeloid suppression from T cell stimulation. I would not yet believe the therapeutic window — that rests on a single-dose cyno study against a comparator picked because it's known to be toxic.

**Nadia:** Mine is the TYK2 dependence. I'd want chronic dosing with a TYK2 inhibitor on board — that's the clean test of whether strict TYK2 dependence is a feature or a liability.

**Theo:** Mine is colitis in a mouse where the immune compartment is human too, not just the receptor.

**Nadia:** That's Nature, DOI 10.1038/s41586-026-11176-1. Thanks for listening.

**Theo:** See you next time.

# 1. T cell-mediated antibody-dependent cellular cytotoxicity provides a therapeutic approach for solid cancers

**DOI:** 10.1172/jci.insight.205984  
**Length:** 11428 chars (~10.8 min)

## Corrections made by the verification pass

- Turn 34 called 1.375 mg/mL soluble antibody 'an absurd concentration'; the paper makes no such claim and FcgammaRI binds any IgG1, so the figure was left plain and tied to total circulating antibody rather than to the trastuzumab dose.
- Turn 30 named 'primary human kidney and lung epithelium' for the CAR comparison; Figure 6F reports only 'epithelial cells' (both types appear in Methods, neither is assigned to that experiment), so the tissue names were cut.
- Turn 42 said the ten- and twenty-million-cell doses were given 'in one go'; the paper says only that mice received escalating numbers of cells (Figure 10A), so the unstated detail was cut.
- Turn 53 put Episode 92's density margin at 'only a few fold'; card 092 and memory/threads.md record 2- to 18-fold, so it now reads as narrow and cell-type dependent without a wrong figure.
- Show notes answer said AG2G 'killed only targets above ~50 HER2 molecules/um2', conflating the bilayer signalling threshold with the killing assays; split into signalling threshold and killing/sparing.
- Show notes takeaway 1 claimed a '~5-fold higher bar' against TCR and CAR at 10-20 molecules/um2; against that range it is 2.5- to 5-fold, so the range is now stated.
- Show notes takeaway 2 omitted the matched-CAR/primary-epithelium comparison that the hosts give as their second takeaway; added.

---

**Nadia:** Hi, and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo. It's Monday, so we're riding alongside this week's digest — and this was the paper sitting right at the top of it.

**Nadia:** It was. "T cell-mediated antibody-dependent cellular cytotoxicity provides a therapeutic approach for solid cancers", in J-C-I Insight, from Yaron Carmi's lab in Tel Aviv. They take an antibody receptor that normally lives on myeloid cells, put it into human T cells, and the killing you get depends on how densely the antigen is packed on the target rather than on which antigen it is.

**Theo:** So why is that worth ten minutes? We have done a lot of redirected killing on this show.

**Nadia:** We have, and nearly all of it comes at the problem from the binder end — tune the affinity, change the geometry, add an arm. This one comes at it from the signalling end: what does the receptor have to see before it fires at all? The claim is that the natural Fc receptor has an answer built in, and you keep it only if you don't rebuild the receptor.

**Theo:** Okay. Set the problem up properly for me.

**Nadia:** So. Engineered T cells clear blood cancers and stall in solid tumours mostly because no antigen sits only on the tumour. The good targets are self proteins the tumour has made too much of. Point a C-A-R at one and you get on-target, off-tumour toxicity — the cells working as designed, on the wrong tissue.

**Theo:** Right, and the usual answers are logic gates, detuned affinity or masking.

**Nadia:** All of which we've covered. The alternative everyone gestures at is density — kill the cell with a lot of the antigen, spare the one with a little. Trouble is, a C-A-R is a very good amplifier. It signals off almost nothing.

**Theo:** Hmm. So the lever exists, nobody can reach it.

**Nadia:** That's the setup. And their route to it starts somewhere odd, with T cells that do this naturally.

**Theo:** Naturally? T cells aren't supposed to carry Fc receptors at all.

**Nadia:** That has been the textbook line for fifty years, and it keeps getting challenged. By mass cytometry on mouse melanomas they find a small population of killer T cells inside the tumour carrying F-c gamma R one, the high-affinity receptor for antibody — not in the lymph nodes, not in blood. A couple of percent of the T cells in the hot tumour model, far less in the cold one. In people: all five melanoma patients they resected, none of the pancreatic ones.

**Theo:** Are those cells transcribing the receptor?

**Nadia:** No, and this is the part I liked. In published single-cell data the messenger R-N-A isn't there in T cells, while the protein plainly is. So they co-culture killer T cells with the person's own monocytes, and the receptor turns up on the T cells. They're tearing membrane off the monocytes. Trogocytosis.

**Theo:** Nibbling. And it's functional?

**Nadia:** Functional, and brief — sorted cells lose it within four to six hours. While they have it, T cells from tumour-bearing mice carrying a deliberately irrelevant T-cell receptor killed melanoma cells, but only when the tumour-binding antibody was there.

**Theo:** Nice control — nothing can come through the T-cell receptor.

**Nadia:** Exactly. So that's the natural phenomenon, and the central claim sits on top of it: the Fc receptor's signalling module has an antigen-density threshold, and engineer it into T cells without rebuilding it and that threshold becomes your selectivity filter. Everything after is evidence for or against that sentence.

**Theo:** Then let's test it. Where does the threshold number come from?

**Nadia:** Supported lipid bilayers carrying H-E-R-two at controlled density, trastuzumab as the bridge, and T cells engineered with the receptor plus its signalling chain. Below a certain density, nothing. Above it, the receptor clusters, pushes the T-cell receptor and the phosphatase out of the contact, and fires. They put that transition at about fifty molecules per square micrometre.

**Theo:** And an ordinary T-cell receptor?

**Nadia:** Signals somewhere between ten and twenty. And their donor-matched H-E-R-two C-A-R responded down to ten.

**Theo:** Oh — so the whole claim is that gap. Five times the antigen before the engineered cell will even start.

**Nadia:** That's the claim. And I want to flag something, because it's the first thing I checked. The abstract says phosphorylation happens above thirty molecules per square micrometre. The results say about fifty, twice. Different numbers for the same switch, and the paper never reconciles them.

**Theo:** Huh. Which one does the rest of the argument use?

**Nadia:** The higher one, as far as I can follow it. The lower figure may belong to the natural receptor and the higher one to the engineered version, but they never say so. I'd treat the exact value as unsettled and the gap as the finding.

**Theo:** Fair. What happens when you take it off the bilayer and onto an actual cell?

**Nadia:** This is the experiment I'd keep. One tumour line, three antibodies against three antigens it carries at three densities. The high one, E-G-F-R with cetuximab, gets killed properly. The middle one, H-E-R-two with trastuzumab, a little. The low one, nothing — no detectable cytotoxicity.

**Theo:** Same effector, same target cell, same assay. So the only thing varying is density.

**Nadia:** About as clean a demonstration of the principle as you get in a dish. Then the comparison that matters: donor-matched H-E-R-two C-A-R T cells against theirs, on tumour cells and on primary human epithelium. The C-A-R killed both. Theirs killed the tumour and left the epithelium alone.

**Theo:** Hold on. There's a version of that result that's trivially true — make a worse killer and you also spare normal cells.

**Nadia:** Right, and that's the standing complaint on this show. The answer here is that they aren't worse — they eradicate tumours in mice, and the version with the extra signalling chain kills harder than the bare receptor. What they capped is how little antigen starts the process, which isn't the same as being weak.

**Theo:** What about free antibody? There's a lot of it floating around in a person.

**Nadia:** That's the other half, and the argument for the natural scaffold. A conventional Fc receptor C-A-R — the receptor's outside on standard T-cell signalling tails — fired on soluble, irrelevant antibody. Killing, cytokines, the lot. Theirs did essentially nothing until free antibody passed about a milligram per millilitre. And since the receptor takes any I-g-G, that is the number to hold against everything circulating, not just against the dose of the drug.

**Theo:** Why not? It's the same binding event.

**Nadia:** Because the receptor binds soluble antibody, internalises it and digests it — off the surface in about two hours. Productive signalling needs clustering at a contact, with antibody held against a target. Immobilised antibody gives clusters, phosphorylated Syk and actin at the interface; soluble gives none. And pooled human antibody at high concentration didn't block killing.

**Theo:** Huh. I'd have predicted the receptor just gets saturated and switched off.

**Nadia:** Turnover is fast enough that it doesn't. Now, the mouse work.

**Theo:** Which model?

**Nadia:** Human gastric tumours in severely immunodeficient mice, weekly trastuzumab. One infusion of five million cells controlled the tumours but didn't clear them. Two infusions, twenty-one days apart, cleared them completely.

**Theo:** So it's cumulative dose rather than anything clever.

**Nadia:** Looks that way. Ten million or twenty million cells gave complete regression as well, and a tenth of that barely did anything.

**Theo:** And the cells that stick around?

**Nadia:** Mostly effector memory, in bone marrow and spleen. Rechallenged two months later, the mice clear the second tumour — as long as the antibody is given too.

**Theo:** Mm. I'd put an asterisk on the word memory there.

**Nadia:** You should. That's a mouse with essentially no immune system of its own, carrying transferred human T cells. It tells you those cells persist and stay functional. It tells you nothing about memory as an interaction with a host repertoire, because there isn't one.

**Theo:** And the safety claim lives in the same animal.

**Nadia:** It does, and that's the limitation I'd lead with. The sparing of normal cells is in a dish, on primary epithelium. The in vivo claim is no detectable inflammation in major mouse organs — mouse tissue, mouse antigen densities, in an animal missing most of the compartments that make this toxicity bad in people.

**Theo:** There's also a thing that bothers me about the framing. Antigen density as the filter still requires an antigen that the tumour genuinely overexpresses.

**Nadia:** Yes. This doesn't widen the target space, and the abstract's phrasing — density rather than identity — oversells that a little. What it does is make the targets we already have less dangerous. Still worth having.

**Theo:** Let me put a number from our back catalogue against this. In episode sixty-nine, the E-G-F-R engager, the authors conceded that healthy skin and gut carry something like forty thousand to a hundred thousand copies of E-G-F-R per cell.

**Nadia:** And that's the measurement this paper owes us, in its own units. Per cell is not per square micrometre — a big flat epithelial cell can carry plenty of receptor at low density, so those don't compare directly. But the experiment that settles it is density, measured the same way, on the normal human tissues these antibodies reach.

**Theo:** It also rhymes with episode ninety-two, where the selectivity came from receptor density too, through binding geometry rather than a threshold — and the margin there was narrow too, and varied a lot by cell type.

**Nadia:** Which is the right frame. Density gating is becoming a real design lever across formats, but the reported margins tend to be narrower than the headline suggests.

**Theo:** There's a second half to this paper, on tumour infiltration, that we can't do justice to.

**Nadia:** Briefly: their cells reached the tumour core better than matched C-A-R cells, and they tie it to adhesion — less collagen-binding integrin, weaker grips on basement-membrane-coated beads in a force assay. Plausible mechanism, not a demonstrated one. Nobody put the integrin back to test it.

**Theo:** What do the authors own up to themselves?

**Nadia:** Credit where it's due. They say plainly they didn't investigate the trogocytosis mechanism, and they're open about a liver sink — transferred T cells and injected antibody both end up there, and they compensated by raising the dose rather than solving it. They also report a negative result they didn't owe us: adding more signalling motifs made the receptor fire with no ligand at all.

**Theo:** Anything to declare?

**Nadia:** One author is at a biotech company; the paper declares no conflict, and the funding is foundation and academic. Worth saying once, not worth reading into.

**Theo:** Alright, three takeaways. One: the natural high-affinity Fc receptor has an antigen-density threshold several times above where a T-cell receptor or a C-A-R fires, and keeping the native scaffold keeps that threshold.

**Theo:** Two: on one cell line with three antibodies, killing tracked antigen density rather than identity, and matched C-A-R cells killed primary human epithelium where these did not. Three: the selectivity case is in dishes or in a mouse with no immune system, and the paper's own threshold number differs between its abstract and its results.

**Nadia:** Fair.

**Theo:** What I'd watch for: density, in molecules per square micrometre, on the normal human tissues trastuzumab and cetuximab actually reach. Until I see that, I don't know how wide this window is.

**Nadia:** Mine is the comparator: a matched construct deliberately detuned to the same potency, in the same assay, to show whether the threshold is doing the work or the cells are simply milder.

**Nadia:** That's J-C-I Insight, this year. D-O-I ten dot one one seven two slash j c i dot insight dot two zero five nine eight four. Thanks for listening.

**Theo:** See you Friday.

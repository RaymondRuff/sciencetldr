# Substantial under-detection of human rabies cases in the United States

**DOI:** 10.1038/s44528-026-00031-4  
**Length:** 10635 chars (~10.0 min)

## Corrections made by the verification pass

- Claim strength: Nadia said the authors' estimate 'shows under-detection can also occur' in wildlife-risk countries; the paper says it 'highlights that under-detection ... could also occur' — softened to match.
- Claim strength: the feedback-loop line asserted that under-detection 'produces' an underappreciation of transmission; the paper states it 'may both result from and contribute to' that underappreciation — reworded to the authors' hedged formulation.
- Length: draft ran 11,039 spoken characters against a 10,200–10,800 window; trimmed setup and framing turns (opening banter, restatement of the encephalitis-series proposal, secondary commentary) while leaving all numbers, assumptions and limitations intact. Numbers (2.4/yr, n=3, 239,251 donors, 68,266,224 deaths, 856, 213–2,220, 34.2, 8.5–88.8, 7%, 22%, 36.6, 14-fold, weeks-to-one-year incubation) all check out against the paper, and the episode 32, 73 and 80 references match the memory cards.
- Show framing (hand edit after review): removed two lines presenting Science TLDR as a protein engineering show visiting an unusual field; re-voiced.

---

**Nadia:** Hello and welcome to Science TLDR. I'm Nadia.

**Theo:** And I'm Theo. And today's paper is a bit of a detective story.

**Nadia:** It is. This is a short paper in Communications Health, titled "Substantial under-detection of human rabies cases in the United States." D-O-I 10.1038/s44528-026-00031-4. And the one-sentence version is: the authors use organ donors who turned out to have rabies as a kind of accidental random sample of the dead, and back out how many rabies deaths the US surveillance system is missing.

**Theo:** So why is this one worth ten minutes?

**Nadia:** Because the inferential move is the whole paper. There's essentially no new data here — four numbers and a ratio. Which means the argument is completely exposed. That's rarer than it should be.

**Theo:** Right. Give me the setup.

**Nadia:** In February 2025, the C-D-C diagnosed rabies in a kidney transplant recipient, and then went back and diagnosed it in the donor, who had died in December 2024. That is the fourth time since 1978 that an undiagnosed rabies-infected deceased donor has transmitted rabies through transplantation in the US. The earlier donors died in 1978, 2004, and 2011.

**Theo:** And those caused how many deaths?

**Nadia:** Six, across the three earlier events. One cornea recipient, three kidney recipients, one liver recipient, and one arterial-segment recipient. In every case the transplant went ahead because rabies had not been diagnosed in the donor. Some other recipients from those donors stayed asymptomatic after post-exposure prophylaxis.

**Theo:** Hm. So the donor was never suspected.

**Nadia:** Never suspected. And that's the seed of the argument. Because meanwhile, confirmed human rabies in the US, including Puerto Rico, averages 2.4 cases per year from 2000 to 2024. That's the official number.

**Theo:** Two point four. That's — that's basically nothing.

**Nadia:** It's basically nothing. And the authors' point is: if rabies is that rare, how did three of them end up in the deceased donor pool? Because only a tiny fraction of people who die become organ or tissue donors.

**Theo:** Okay, I see the shape of it. Walk me through the arithmetic.

**Nadia:** It's a proportion. Three donors died of undiagnosed rabies prior to transplantation in the 2000 to 2024 window — that's the 2004, 2011, and 2024 donors. Divide by the total number of deceased donors in that period, 239,251. Multiply by the total number of deaths in the US over those 25 years, 68,266,224.

**Theo:** And that gives you —

**Nadia:** 856 undiagnosed human rabies deaths over 25 years. 95 percent confidence interval, 213 to 2,220. Which is an average of 34.2 per year, interval 8.5 to 88.8.

**Theo:** Oh — so against 2.4 confirmed.

**Nadia:** Against 2.4 confirmed. Their central estimate is that about 7 percent of human rabies cases in the general population were confirmed. 2.4 divided by 36.6, where 36.6 is the confirmed plus the estimated undiagnosed. And even at the optimistic end of the confidence interval — the lower bound on undiagnosed deaths — you only get to about 22 percent detected.

**Theo:** So the best case is that we're missing roughly four out of five.

**Nadia:** That's their claim, yes. And I want to flag the one assumption that carries all of it, because they flag it themselves, plainly, in the text: the assumption is that deceased donors experienced the average national risk of rabies infection.

**Theo:** [interrupting] And that's exactly where I'd push. Donors are not a random sample of the dead.

**Nadia:** They're not. Not remotely. To become a deceased organ donor you generally need to die in a hospital, on a ventilator, with an intact circulation — typically brain death from trauma, stroke, anoxia. A specific population, younger and trauma-skewed.

**Theo:** And rabies kills you with encephalitis, which lands you in exactly that pathway.

**Nadia:** Hmm. Yes — that's the strongest version of the objection, and the authors don't test it. Someone dying of undiagnosed encephalitis in an I-C-U is plausibly over-represented among brain-dead donors relative to, say, someone who dies at home. If that's true, the multiplier is too big.

**Theo:** So how much over-representation would you need to kill the result?

**Nadia:** They give you that number, and I think it's the best sentence in the paper. For the reported case count to be consistent with complete surveillance, deceased donors would need a rabies risk approximately 14 times that of the general population of decedents.

**Theo:** Fourteen-fold. Huh. That's a specific, falsifiable bar.

**Nadia:** It is, and I like that they framed it that way instead of just asserting the estimate. Now — is 14-fold implausible? I genuinely don't know. Encephalitis-to-brain-death is a real enrichment channel. I would not bet on 14, but I wouldn't say it's absurd either.

**Theo:** And there's a second direction of bias, right? Donation isn't randomly distributed either.

**Nadia:** Correct, and they raise it. They note both the risk of rabies infection and the probability of becoming a donor after death might be associated with geographical, occupational, and socioeconomic factors. US rabies exposure is mostly wildlife — bats, raccoons, skunks — which is rural-skewed, and donor registration isn't uniformly distributed. Those could push either way.

**Theo:** Um — and the confidence interval. 213 to 2,220 is a factor of ten. What's driving that?

**Nadia:** Three events. That's it. The numerator of the whole estimate is n equals 3. Everything about the width of that interval comes from Poisson uncertainty on three counts. And I'd note that the interval only captures sampling uncertainty on those three — it does not capture the uncertainty in the donor-risk assumption at all.

**Theo:** Right, which is the bigger uncertainty.

**Nadia:** Almost certainly the bigger uncertainty. So the honest read is: the interval is narrower than your actual belief should be.

**Theo:** Let me ask the reviewer question. Is there a confirmatory dataset that doesn't route through transplant?

**Nadia:** That's the experiment, and they don't have it. What would settle this is a systematic retrospective — unexplained fatal encephalitis cases in the US, tested for rabies by a validated assay, with a defined denominator. That gives you a detection rate directly rather than through a three-event proxy.

**Theo:** And nobody's done that?

**Nadia:** Not that this paper cites. What they do instead is offer mechanism — reasons under-detection is plausible, which is different from evidence that it's occurring at this rate.

**Theo:** Go through those.

**Nadia:** The incubation period ranges from weeks to about a year, which breaks the link between exposure and illness in the clinician's mind. Exposures may go unobserved — non-apparent injuries. Or unrecognised: a superficial scratch, or simply no awareness that your region or your travel carried rabies risk. And then there's the loop they describe, which I think is the interesting claim: under-detection may both result from and contribute to an underappreciation of rabies transmission, thereby sustaining the risk to transplant recipients.

**Theo:** That's a self-reinforcing loop rather than a measured effect, though.

**Nadia:** It's a hypothesis. They present it as one. I'd say it's consistent with the four transplant events, and it is not established by them.

**Theo:** Mm-hm. What do they want done about it?

**Nadia:** Four things: raise public risk awareness, take in-depth exposure histories, consider geographical, occupational and socioeconomic risk factors independently of a stated exposure history, and explicitly include rabies in the differential for patients dying of unexplained clinical signs compatible with rabies, including encephalitis.

**Theo:** That last one is the operational ask. And it's cheap.

**Nadia:** It is. I'd also note they're careful about the international comparison. They say canine rabies is notoriously under-detected in affected countries, and that their estimate highlights that under-detection could also occur where risk is mostly wildlife exposure. But they explicitly say the mechanisms and relative contributions likely differ, given different diagnostic capacity and exposure profiles — wildlife versus free-roaming dogs. They don't pretend it's the same phenomenon.

**Theo:** Good. That's the kind of restraint that makes me trust the rest more. Can I connect this to something?

**Nadia:** Go ahead.

**Theo:** This is a design-not-randomisation paper, and we've done a run of those. Episode 32, the zoster vaccine birthdate cutoff. Episode 73, work from home and disability employment, where the instrument was the pre-pandemic remote-feasibility index. And episode 80, the Norwegian conscription cohorts where the Flynn reversal cancelled out in the national average. In every one of those, the credibility rested on the exposure being as-good-as-random.

**Nadia:** And that's exactly the axis this paper sits on. In 32, the cutoff genuinely was arbitrary — weeks of birthdate. Here, becoming a deceased organ donor is manifestly not arbitrary with respect to cause of death. So the design is the same species, but the as-good-as-random claim is much weaker.

**Theo:** And episode 80 had half a million people. This has three.

**Nadia:** Three. Though I'd say something in its defence: the direction of the finding doesn't depend on the arithmetic being precise. Even at 22 percent detection, the top of their range, the conclusion — that surveillance is missing most cases — holds. The point estimate is fragile. The sign is not.

**Theo:** Hmm. That's a fair distinction. All right — three takeaways, from the numbers rather than the framing.

**Theo:** One. Three of 239,251 deceased donors in 25 years died of undiagnosed rabies, and scaling that to 68 million deaths gives 856 undiagnosed rabies deaths, or 34.2 a year, against 2.4 confirmed. That's the entire paper and it's one line of arithmetic.

**Theo:** Two. The load-bearing assumption is that donors carry average national rabies risk, and the authors quantify what would break it: donors would need a 14-fold elevated risk. I think that assumption is the weakest part of the paper and I also think stating the 14-fold bar is the best part of it.

**Theo:** Three. The confidence interval, 213 to 2,220, reflects Poisson noise on three events and nothing else. It does not price in the donor-selection uncertainty, so the true uncertainty is wider than stated.

**Nadia:** I'd sign all three.

**Theo:** What I'd believe on this evidence: that confirmed US rabies cases undercount true rabies deaths, probably substantially. What I would not yet believe: 34 a year, or 7 percent, as figures to plan around.

**Nadia:** What would change my mind is that retrospective encephalitis series. If it came back at a few percent positive, this estimate is roughly right. If it came back at zero across a few thousand cases, the donor pool is enriched and the 14-fold objection wins.

**Theo:** And for me it's simpler — whether any transplant network starts routinely screening donors with unexplained encephalitic death. That's the decision this paper is arguing for.

**Nadia:** That's the paper. Communications Health, D-O-I 10.1038/s44528-026-00031-4. Thanks for listening.

**Theo:** See you next time.

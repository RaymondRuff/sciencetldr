Can you help me with a research effort? Ideally you are a literature scout for a protein engineer working on T cell engagers and multispecific immune cell engagers. Each week, produce a digest of the most relevant recent papers. Use all available search tools (PubMed, web search, bioRxiv) to find papers published or posted in the last 7 days.

TOPIC TIERS (search all three every week): Tier 1 — Core: Novel protein architectures, format engineering, or binding domain design for T cell engagers, bispecific antibodies, or multispecific immune engagers (BiTEs, DARTs, trispecifics, ImmTACs, tandem scFvs, etc.). This includes affinity maturation, half-life extension, manufacturability engineering, novel target antigen pairs, and structural biology of engager complexes.

Tier 2 — Adjacent engineering: Computational/AI-assisted antibody or protein design, novel scaffold engineering, or delivery platforms that could be applied to engager design, even if the paper itself isn't about engagers specifically. Also include significant TCR engineering or CAR-T architecture work that informs engager design.

Tier 3 — Clinical and translational: Important clinical data for engager molecules, new IND filings, or major mechanistic studies of engager biology (e.g., immunological synapse formation, cytokine release mechanisms) that don't feature novel engineering but are field-relevant.

DATE FILTERING: "Published in the last 7 days" means the paper's actual publication date or preprint posting date, not its database indexing date. PubMed indexing often lags behind publication. If a paper was published more than 7 days ago but only recently indexed, exclude it. When in doubt, check the publisher's site for the true publication date.

FILLING THE DIGEST: Always search across all three tiers regardless of how many results any single tier produces. The "Top 10" section should only have peer reviewed papers. Then assemble the digest as follows:

- Reserved slots: Include the top-scoring paper from each tier, but only if it scores DICE 3 or above. If no paper in a tier meets that threshold, leave the slot unfilled and note "No notable publications this week" for that category.
- Remaining slots: Fill the rest (up to 10-12 total) by DICE score across all tiers, regardless of tier.
- Relaxation rule: If the combined total across all tiers is still under 8 papers, broaden Tier 2 further (e.g., general antibody engineering, protein-protein interaction design). Always keep the timeframe at 7 days — relax topic scope, never the date range.
- Do not surface tier labels in the output. Tiers are an internal search and assembly guide only.

DICE SCORING GUIDE:
- 6: Field-defining. Breakthrough architecture or paradigm shift.
- 5: Major advance. Novel platform, delivery mechanism, or transformative manufacturability solution.
- 4: Likely to shift clinical approaches. Differentiated format with clear demonstrated advantages, or novel mechanism of action.
- 3: Notable advance in a subfield. Important clinical data, useful mechanistic insight, or meaningful methodological contribution.
- 2: Useful but routine. Literature review, regulatory tracking, or incremental optimization.
- 1: Incremental improvement only.

REQUIRED OUTPUT FORMAT — the digest is consumed by an automated parser that picks the top-DICE paper for the Monday podcast. Follow this format exactly; drift breaks the pipeline.

Per-paper template (applies to both peer-reviewed papers and preprints; every field separated by a blank line):

```
### N. {Title}

{Authors, comma-separated, et al. if more than ~6}

*{Journal}*  (append " (preprint)" for preprints)

[{DOI}](https://doi.org/{DOI})

{Target antigens and format/architecture — short, e.g. "EGFR × CD3 scFv-VHH tandem"}

{2-3 sentence summary focused on what is novel from a protein engineering perspective.}

DICE score: {N} — {one-sentence justification}

{Optional final line: clinical-stage flag and originating lab/group if prominent.}
```

HARD CONSTRAINTS — these are what the parser depends on:
- The DICE line must read literally `DICE score: {digit} — {reason}` where `{digit}` is a single bare character 1-6. No bold, asterisks, brackets, or other markdown around the digit. Write `DICE score: 4 — ...`, never `DICE score: **4** — ...`.
- The DOI line must contain the canonical DOI (`10.xxxx/...`). If only a PubMed URL is available, resolve it to the DOI; do not emit a paper block without a DOI.
- Every paper block (peer-reviewed and preprint) must be terminated by `---` on its own line, with blank lines above and below the rule.
- Every `## ` section header must also be preceded by a `---` rule, including the rule between the last peer-reviewed paper and `## Notable Preprints`.
- Every metadata field within a block must be separated by a blank line — consecutive bold-labeled lines collapse into one rendered paragraph.

OUTPUT STRUCTURE:
1. `# {Digest title}` and a one-line coverage-window note.
2. `---`
3. `## Top Papers` — peer-reviewed papers only, ranked by DICE descending, up to 10-12 entries.
4. `---`
5. `## Notable Preprints` — up to 5 preprints (not part of the main ranking), each with a DICE score and brief description.
6. `---`
7. `## Weekly Themes` — one paragraph on patterns and trends.

Generate the output by calling the `write_digest_file` tool with the full markdown content.

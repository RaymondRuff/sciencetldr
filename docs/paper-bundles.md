# Getting a paper into the pipeline

Most papers never reach the show on their own. Publishers refuse scripted
downloads even for open-access articles, so for a large share of Issues the
only way in is a human handing over a PDF. This note describes how that
hand-off works, and what the PDF becomes once it arrives.

## The problem the bundle solves

A supplied PDF used to be read with `pypdf.extract_text()` and nothing else.
That loses two things:

1. **Everything drawn inside a raster figure.** A forest plot's hazard ratios,
   a dot plot's quartiles, a Manhattan plot's peak — all of them are pixels.
   Grepping the extracted text of a real paper for its own figure labels
   returns nothing. A script that cites a figure is citing a number the writer
   could not have read.
2. **The captions' position.** Captions survive extraction but land wherever
   the PDF's content stream put them, which is routinely mid-paragraph:

   > ...a recent analysis of the EPIC study showed a 6% higher
   > Fig 1. Associations for joint effect of ultra-processed food intake...

Reading the PDF natively instead solves both and costs the wrong resource: a
routine on the subscription spends its session budget rendering forty pages,
every run, including the checker's.

So the PDF is normalised **once**, by Actions, into a bundle:

```
papers/issue-86/
  paper.txt          body text, then a FIGURES AND TABLES section holding
                     every caption as printed, each naming its image file
  figures/*.jpg      each real figure, downsampled to 1600px on its long edge
  meta.json          DOI, page count, the original PDF's sha256, one record
                     per figure and per caption
```

Measured on a 17-page PLOS Medicine paper: a 0.9 MB PDF becomes a 0.31 MB
bundle — 74,000 characters of text and two figures at 88 KB and 146 KB. Every
hazard ratio and confidence interval on the forest plot stays legible, and
those values exist nowhere in the text.

Tables benefit by accident and substantially: a table's "caption" runs on into
the table itself, so the collected section ends up holding each table's rows as
one clean labelled block instead of scattered through the prose. Tables get an
8,000-character budget for that reason; figure captions get 2,500.

## Routes in

Both of the everyday routes stop at the same place — 25 MB — so there is no
point preferring one for size:

| Route | Ceiling |
|---|---|
| Reply to the PDF-request email with the PDF attached | 25 MB (Gmail) |
| Upload to the private papers repository in a browser | 25 MiB (GitHub) |
| Attach to a routine's session | 30 MB |
| `git push` from a desktop | warns at 50 MiB, blocked at 100 MiB |

The request email offers the first two, because one suits a phone and the other
a desk. For anything larger, the email points at:

```bash
python scripts/paper_bundle.py shrink --pdf big.pdf --out small.pdf
```

which rewrites the PDF with its images downsampled. Figures stay readable; only
print resolution goes. A paper whose bulk is text rather than figures will
barely shrink — that paper was never the problem.

A PDF uploaded to the papers repository is recognised as `issue-NN.pdf`, or by
a filename containing the DOI suffix, which covers publisher filenames like
`journal.pmed.1005251.pdf` without renaming anything.

## What happens to it

`generate_episode.py` calls `paper_bundle.sync_all()` once per run, before
anything else. That opens the papers repository a single time, bundles every
PDF that has arrived by any route, pushes the bundles in one commit, and caches
them on the runner. The raw PDF is deleted in the same commit: a 40 MB blob
left in git history would be permanent.

From then on the route the paper took stops mattering. `paper_text.resolve()`
tries the cached bundle first and falls back to its old HTTP sources, and
`routine_tools.py context` pulls the bundle into the routine's scratch folder,
figures and all. When the episode publishes, `publish_episode.py` deletes the
bundle: the papers repository stages other people's copyrighted work and is not
an archive.

Nothing here can break the pipeline. Every step is wrapped: no papers
repository, no token, or a PDF that will not parse, and the run falls back to
fetching text over HTTP exactly as it did before bundles existed.

## Setup

- `GH_PAT` needs **Contents: Read and write** on `sciencetldr-papers`. Without
  it the clone fails, the run says so, and bundles are silently skipped.
- The repository variable `PAPERS_REPO` overrides the default
  `RaymondRuff/sciencetldr-papers`.
- `pillow` is a pipeline dependency; the routines install it alongside `pypdf`.

## Limits worth knowing

- A figure drawn as **vector** graphics has no embedded image to extract. Its
  text survives extraction instead, so the two cases are complementary — the
  captions section marks which is which.
- Caption detection keys off a label at the start of a line. An inline
  cross-reference ("the effect held (Fig 1)") is correctly ignored; a sentence
  that happens to wrap onto a new line just before "Fig 1 shows" would be
  caught as a caption. The cost is a labelled paragraph of the paper's own
  text, which is harmless.
- `numbers_not_in_paper()`, the validator's cross-check, compares spoken
  figures against `paper.txt`. A number read off a figure image is not in
  `paper.txt` and will be reported as a lead. That is correct behaviour for a
  lead generator, and the checker's instructions say to open the image.

"""Normalise a supplied paper PDF into a small bundle the routines can read.

A paper arrives as one big PDF — by email, by browser upload to the private
papers repository, or attached to a routine's own session. Whatever the route,
this module turns it into the same three things:

    papers/issue-NN/paper.txt      full text, with the figure and table
                                   captions collected at the end and paired
                                   with the image files
    papers/issue-NN/figures/*.png  each real figure, downsampled
    papers/issue-NN/meta.json      provenance: DOI, page count, the original
                                   PDF's sha256, and one record per figure

Why a bundle rather than the PDF itself:

  * A routine reading a 40-page PDF natively spends its session budget on
    rendering pages. The bundle is a few hundred KB of text and a handful of
    images it can open only when a figure actually matters.
  * Extracted text loses everything drawn inside a raster figure. The axis
    values of a dot plot, the points of a forest plot and the peaks of a
    Manhattan plot are simply not there, so a script that cites them is
    citing nothing. The figure files put them back.
  * Captions survive extraction but land in the wrong place: a publisher's
    PDF drops the caption into the middle of a body paragraph, so the text
    reads "...showed a 6% higher Fig 1. Associations for joint effect of...".
    Collecting them at the end gives each figure an intact caption.
  * The bundle is small enough to travel by any route, which keeps the
    hand-off from being bounded by a 25 MB attachment limit.

Only bundles go to the private repository; nothing here ever writes a paper's
text or PDF into the public one.

Usage:
  python scripts/paper_bundle.py build --issue 86 --pdf paper.pdf --out ./bundle
  python scripts/paper_bundle.py sync --issue 86 --doi 10.1371/journal.pmed.1005251
  python scripts/paper_bundle.py shrink --pdf huge.pdf --out small.pdf
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAPERS_REPO = os.environ.get("PAPERS_REPO", "RaymondRuff/sciencetldr-papers")

# A figure smaller than this is a journal logo, an ORCID icon or a rule.
# The smallest real figure seen so far is 1762x1128; the largest decorative
# image, a journal mark at 233x233.
MIN_FIGURE_PIXELS = 120_000
MIN_FIGURE_DIM = 300
MAX_ASPECT_RATIO = 12.0

# A forest plot stays readable to about 1200px on its long edge; 1600 leaves
# headroom for a dense multi-panel figure without the file growing much.
MAX_FIGURE_DIM = 1600
JPEG_QUALITY = 85
# Line art compresses better and stays crisper as PNG, so prefer it unless
# JPEG is dramatically smaller — which only happens for photographic figures.
PNG_PREFERENCE = 1.6

# Total bundle ceiling. Papers seen so far land at 0.2-2 MB; past this the
# figures are downsampled again rather than dropped.
BUNDLE_BUDGET = 8_000_000

CAPTION_RE = re.compile(
    r"^[ \t]*((?:Fig(?:ure)?|Table|Extended Data Fig(?:ure)?|Supplementary "
    r"(?:Fig(?:ure)?|Table))\.?[ \t]*(\d+)[.:]?)(?=[ \t])",
    re.MULTILINE,
)
# A caption ends at the publisher's per-figure DOI stamp, the next caption, or
# a section heading — whichever comes first.
CAPTION_STOP_RE = re.compile(
    r"(https?://doi\.org/\S+)"
    r"|^[ \t]*(?:Abstract|Introduction|Background|Methods|Materials and Methods"
    r"|Results|Discussion|Conclusions?|References|Acknowledg(?:e)?ments"
    r"|Supporting information|Author contributions)\b",
    re.MULTILINE,
)
# A figure caption is prose and ends; a table's "caption" runs on into the
# table itself, and those rows are exactly where the hosts get their numbers,
# so a table gets far more room than a figure.
MAX_CAPTION_CHARS = 2_500
MAX_TABLE_CHARS = 8_000

def figures_heading() -> str:
    """The heading paper_text keys its trim-protection off. Shared, not copied."""
    import paper_text

    return paper_text.FIGURES_MARKER.strip("\n")


# --------------------------------------------------------------------------- #
# Text and captions
# --------------------------------------------------------------------------- #


def page_texts(pdf_bytes: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [page.extract_text() or "" for page in reader.pages]


def find_captions(pages: Iterable[str]) -> list[dict]:
    """Every figure and table caption, with the page it appeared on.

    A caption is a label at the start of a line followed by prose. An inline
    cross-reference ("as Fig 1 shows") never starts a line in any extraction
    we have seen, which is what keeps the two apart.
    """
    found: list[dict] = []
    for page_number, text in enumerate(pages, start=1):
        for match in CAPTION_RE.finditer(text):
            label = re.sub(r"\s+", " ", match.group(1)).strip().rstrip(".:")
            body_start = match.end()
            stop = len(text)
            for candidate in CAPTION_STOP_RE.finditer(text, body_start):
                # The DOI stamp belongs to the caption it closes; a heading
                # does not.
                stop = candidate.end() if candidate.group(1) else candidate.start()
                break
            next_label = CAPTION_RE.search(text, body_start)
            if next_label and next_label.start() < stop:
                stop = next_label.start()
            kind = "table" if "table" in label.lower() else "figure"
            budget = MAX_TABLE_CHARS if kind == "table" else MAX_CAPTION_CHARS
            cut = min(stop, body_start + budget)
            caption = re.sub(r"[ \t]*\n[ \t]*", " ", text[match.start() : cut]).strip()
            if cut < stop:
                caption = caption.rsplit(" ", 1)[0] + " [...truncated]"
            if len(caption) < len(label) + 20:
                continue  # a bare label with no prose is a cross-reference
            found.append(
                {
                    "label": label,
                    "number": int(match.group(2)),
                    "kind": kind,
                    "page": page_number,
                    "caption": caption,
                }
            )
    return found


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def _is_decorative(width: int, height: int) -> bool:
    if width * height < MIN_FIGURE_PIXELS:
        return True
    if max(width, height) < MIN_FIGURE_DIM:
        return True
    long_edge, short_edge = max(width, height), max(1, min(width, height))
    return long_edge / short_edge > MAX_ASPECT_RATIO


def _resize(image, max_dim: int):
    """A copy in a saveable mode, no larger than `max_dim` on its long edge."""
    from PIL import Image

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if max(image.size) > max_dim:
        image = image.copy()
        image.thumbnail((max_dim, max_dim), Image.LANCZOS)
    return image


def _encode(image, max_dim: int) -> tuple[bytes, str]:
    """Downsample and encode, choosing the format that suits the figure."""
    image = _resize(image, max_dim)
    png = io.BytesIO()
    image.save(png, format="PNG", optimize=True)
    jpeg = io.BytesIO()
    image.save(jpeg, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    if len(png.getvalue()) <= len(jpeg.getvalue()) * PNG_PREFERENCE:
        return png.getvalue(), "png"
    return jpeg.getvalue(), "jpg"


def extract_figures(pdf_bytes: bytes, max_dim: int = MAX_FIGURE_DIM) -> list[dict]:
    """Every non-decorative embedded image, downsampled, in page order.

    A figure drawn as vector graphics has no embedded image at all. Its text
    survives extraction, so the caption pairing below records it as vector and
    the writer reads the numbers from `paper.txt` instead.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    figures: list[dict] = []
    seen: set[str] = set()
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            images = list(page.images)
        except Exception as exc:  # noqa: BLE001 - one unreadable page is a miss
            print(f"  [bundle] page {page_number}: images unreadable ({exc})")
            continue
        index = 0
        for item in images:
            try:
                image = item.image
            except Exception as exc:  # noqa: BLE001
                print(f"  [bundle] page {page_number}: image skipped ({exc})")
                continue
            if image is None:
                continue
            width, height = image.size
            if _is_decorative(width, height):
                continue
            digest = hashlib.sha256(item.data).hexdigest()
            if digest in seen:
                continue  # a repeated graphic is furniture, not a figure
            seen.add(digest)
            data, ext = _encode(image, max_dim)
            index += 1
            figures.append(
                {
                    "file": f"figures/fig-p{page_number:02d}-{index:02d}.{ext}",
                    "page": page_number,
                    "width": width,
                    "height": height,
                    "bytes": len(data),
                    "data": data,
                }
            )
    return figures


def pair_figures(figures: list[dict], captions: list[dict]) -> None:
    """Give each image the caption from its own page, in order.

    Publishers put a figure and its caption on the same page, so the page is
    the whole pairing rule. Captions with no image on their page keep their
    text and are marked vector or table.
    """
    by_page: dict[int, list[dict]] = {}
    for caption in captions:
        if caption["kind"] == "figure":
            by_page.setdefault(caption["page"], []).append(caption)
    for figure in figures:
        queue = by_page.get(figure["page"], [])
        match = queue.pop(0) if queue else None
        figure["label"] = match["label"] if match else ""
        figure["caption"] = match["caption"] if match else ""
        if match:
            match["image"] = figure["file"]


# --------------------------------------------------------------------------- #
# Assembling paper.txt
# --------------------------------------------------------------------------- #


def figures_section(captions: list[dict], figures: list[dict]) -> str:
    """The captions, collected, each pointing at its image file."""
    rule = "=" * 70
    lines = [
        "",
        rule,
        figures_heading(),
        "",
        "Captions as printed, collected here because extraction scatters them",
        "through the body text above. A caption with an image file has its",
        "values drawn inside that image and nowhere in the text: open the file",
        "to read them. A caption with no image file was drawn as vector",
        "graphics or is a table, so its numbers are in the text above.",
        rule,
        "",
    ]
    def order(caption: dict) -> tuple:
        return (caption.get("kind", ""), caption.get("number", 0), caption.get("page", 0))

    unmatched = [f for f in figures if not f.get("caption")]
    for caption in sorted(captions, key=order):
        image = caption.get("image")
        where = f"image: {image}" if image else "no image file (vector or table)"
        lines.append(f"[{caption['label']}] page {caption.get('page', '?')} — {where}")
        lines.append(caption["caption"])
        lines.append("")
    for figure in unmatched:
        size = (
            f" ({figure['width']}x{figure['height']})"
            if figure.get("width") and figure.get("height")
            else ""
        )
        lines.append(
            f"[unlabelled image] page {figure.get('page', '?')} — "
            f"image: {figure['file']}{size}"
        )
        lines.append("")
    return "\n".join(lines)


def assemble_text(pages: list[str], captions: list[dict], figures: list[dict]) -> str:
    """Body text, trimmed as the API pipeline trims it, then the captions.

    The captions go last and after trimming on purpose: `prepare_paper_text`
    cuts everything past a late references heading, which would take the
    figures section with it if it were appended first.
    """
    import paper_text

    body = paper_text.prepare_paper_text(
        paper_text._clean("\n\n".join(pages))  # noqa: SLF001 - same package
    )
    return body.rstrip() + "\n" + figures_section(captions, figures)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #


def build(
    pdf_bytes: bytes,
    issue_number: int,
    out_dir: Path,
    *,
    doi: str = "",
    title: str = "",
    journal: str = "",
    provenance: str = "",
) -> dict:
    """Write a bundle for one paper into `out_dir`. Returns its meta."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)

    pages = page_texts(pdf_bytes)
    captions = find_captions(pages)
    figures = extract_figures(pdf_bytes)
    pair_figures(figures, captions)

    text = assemble_text(pages, captions, figures)
    figures = _fit_budget(pdf_bytes, figures, captions, len(text.encode("utf-8")))

    (out_dir / "paper.txt").write_text(text, encoding="utf-8")
    for figure in figures:
        (out_dir / figure["file"]).write_bytes(figure["data"])

    meta = {
        "issue": issue_number,
        "doi": doi,
        "title": title,
        "journal": journal,
        "provenance": provenance,
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "pdf_bytes": len(pdf_bytes),
        "pages": len(pages),
        "text_chars": len(text),
        "figures": [
            {k: v for k, v in figure.items() if k != "data"} for figure in figures
        ],
        "captions": [
            {k: v for k, v in caption.items() if k != "image"} | (
                {"image": caption["image"]} if caption.get("image") else {}
            )
            for caption in captions
        ],
        "bundle_bytes": len(text.encode("utf-8"))
        + sum(f["bytes"] for f in figures),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"[bundle] issue {issue_number}: {len(pages)} pages, "
        f"{meta['text_chars']:,} chars, {len(figures)} figures, "
        f"{meta['bundle_bytes'] / 1e6:.2f} MB (from {len(pdf_bytes) / 1e6:.1f} MB)"
    )
    return meta


def _fit_budget(
    pdf_bytes: bytes, figures: list[dict], captions: list[dict], text_bytes: int
) -> list[dict]:
    """Re-encode the figures smaller until the bundle fits its ceiling."""
    max_dim = MAX_FIGURE_DIM
    while (
        figures
        and text_bytes + sum(f["bytes"] for f in figures) > BUNDLE_BUDGET
        and max_dim > 600
    ):
        max_dim = int(max_dim * 0.75)
        print(f"[bundle] over budget; re-encoding figures at {max_dim}px")
        figures = extract_figures(pdf_bytes, max_dim=max_dim)
        pair_figures(figures, captions)
    return figures


# --------------------------------------------------------------------------- #
# shrink — for a PDF too large to hand over at all
# --------------------------------------------------------------------------- #


def shrink(pdf_in: Path, pdf_out: Path, max_dim: int = 1600) -> tuple[int, int]:
    """Rewrite a PDF with its images downsampled. Returns (before, after).

    For the rare paper whose supplementary figures put it past every channel's
    attachment limit. The text and the figures stay readable; only the print
    resolution goes.
    """
    from pypdf import PdfReader, PdfWriter

    before = pdf_in.stat().st_size
    reader = PdfReader(str(pdf_in))
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        for image in page.images:
            try:
                source = image.image
                if source is None or max(source.size) <= max_dim:
                    continue
                image.replace(_resize(source, max_dim), quality=JPEG_QUALITY)
            except Exception as exc:  # noqa: BLE001 - leave what cannot be redone
                print(f"  [shrink] image left as-is ({exc})")
    writer.compress_identical_objects()
    with open(pdf_out, "wb") as fh:
        writer.write(fh)
    after = pdf_out.stat().st_size
    print(
        f"[shrink] {pdf_in.name}: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB "
        f"({pdf_out})"
    )
    return before, after


# --------------------------------------------------------------------------- #
# The private papers repository
# --------------------------------------------------------------------------- #


def _token() -> str:
    """A token that can reach the private papers repository.

    The workflow's default GITHUB_TOKEN is scoped to the public repository
    alone, so only the PAT can do this. It is tried last all the same: on a
    runner it is simply absent, and failing to clone is not fatal.
    """
    for name in ("GH_PAT", "GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name)
        if token:
            return token
    return ""


class PapersRepo:
    """A shallow clone of the private papers repository, in a temp directory.

    The token goes into the remote URL because that is the only form `git`
    accepts without a credential helper, so nothing here prints a URL and the
    clone is deleted on exit.
    """

    def __init__(self, repo: str = PAPERS_REPO) -> None:
        self.repo = repo
        self.dir: Optional[Path] = None

    def _url(self) -> str:
        # A PAPERS_REPO that is already a URL or a local path is used as given,
        # which is how this is tested against a throwaway repository.
        if "://" in self.repo or Path(self.repo).exists():
            return self.repo
        token = _token()
        if token:
            return f"https://x-access-token:{token}@github.com/{self.repo}.git"
        return f"https://github.com/{self.repo}.git"

    def __enter__(self) -> "PapersRepo":
        self.dir = Path(tempfile.mkdtemp(prefix="tldr-papers-"))
        print(f"[papers] cloning {self.repo}")
        self._git("clone", "--depth", "1", self._url(), str(self.dir), cwd=None)
        self._git("config", "user.name", "sciencetldr-bot")
        self._git(
            "config",
            "user.email",
            "101901279+RaymondRuff@users.noreply.github.com",
        )
        return self

    def __exit__(self, *exc) -> None:
        if self.dir and self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)

    def _git(self, *args: str, cwd: Optional[str] = "") -> subprocess.CompletedProcess:
        where = str(self.dir) if cwd == "" else cwd
        result = subprocess.run(
            ["git", *args],
            cwd=where,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            # Redact in case git echoed the remote back at us.
            token = _token()
            message = (result.stderr or result.stdout).strip()
            if token:
                message = message.replace(token, "***")
            raise RuntimeError(f"git {args[0]} failed: {message}")
        return result

    @property
    def papers(self) -> Path:
        assert self.dir is not None
        return self.dir / "papers"

    def find_raw_pdf(self, issue_number: int, doi: str = "") -> Optional[Path]:
        """A PDF dropped for this Issue, by whatever name it arrived under."""
        if not self.papers.is_dir():
            return None
        exact = self.papers / f"issue-{issue_number}.pdf"
        if exact.is_file():
            return exact
        suffix = doi.rsplit("/", 1)[-1].lower() if doi else ""
        if suffix:
            for path in sorted(self.papers.glob("*.pdf")):
                if suffix in path.name.lower():
                    return path
        return None

    def commit(self, message: str) -> bool:
        self._git("add", "-A", "papers")
        status = self._git("status", "--porcelain", "papers").stdout.strip()
        if not status:
            print("[papers] nothing to commit")
            return False
        self._git("commit", "-m", message)
        self._git("push", "origin", "HEAD:main")
        print(f"[papers] pushed: {message}")
        return True


def cache_dir() -> Path:
    """Where bundles are kept on the runner for the rest of a run."""
    base = os.environ.get("PAPER_BUNDLE_DIR") or os.path.join(
        os.environ.get("RUNNER_TEMP", tempfile.gettempdir()), "tldr-bundles"
    )
    return Path(base)


def cached(issue_number: int) -> Optional[Path]:
    """A bundle already pulled down this run, if there is one."""
    bundle = cache_dir() / f"issue-{issue_number}"
    return bundle if (bundle / "paper.txt").is_file() else None


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def sync_all(wanted: list[dict]) -> dict[int, dict]:
    """Bundle every waiting PDF, push the bundles, and cache them locally.

    `wanted` is one dict per Issue: {"issue": N, "doi", "title", "journal",
    optional "pdf"}. One clone and one push however many papers are waiting,
    because the alternative is a clone per Issue on every sweep.

    A raw PDF is looked for in three places, in order: an explicit path, the
    emailed-PDF drop directory on the runner, and a browser upload sitting in
    the papers repository. An Issue whose bundle already exists is simply
    pulled into the cache.
    """
    if not wanted:
        return {}
    results: dict[int, dict] = {}
    built: list[int] = []
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    with PapersRepo() as repo:
        for item in wanted:
            number = int(item["issue"])
            doi = item.get("doi") or ""
            bundle_dir = repo.papers / f"issue-{number}"
            source: Optional[Path] = None
            provenance = ""

            explicit = item.get("pdf")
            if explicit and Path(explicit).is_file():
                source, provenance = Path(explicit), "explicit"
            if source is None:
                try:
                    import pdf_mailbox

                    emailed = pdf_mailbox.drop_dir() / f"issue-{number}.pdf"
                    if emailed.is_file():
                        source, provenance = emailed, "emailed-pdf"
                except Exception as exc:  # noqa: BLE001 - mailbox is optional
                    print(f"[bundle] mailbox drop unavailable ({exc})")
            if source is None:
                uploaded = repo.find_raw_pdf(number, doi)
                if uploaded is not None:
                    source, provenance = uploaded, f"upload:{uploaded.name}"

            if source is None:
                if (bundle_dir / "paper.txt").is_file():
                    print(f"[bundle] issue {number}: bundle already published")
                    _copy_tree(bundle_dir, cache / f"issue-{number}")
                    results[number] = json.loads(
                        (bundle_dir / "meta.json").read_text("utf-8")
                    )
                continue

            try:
                meta = build(
                    source.read_bytes(),
                    number,
                    bundle_dir,
                    doi=doi,
                    title=item.get("title") or "",
                    journal=item.get("journal") or "",
                    provenance=provenance,
                )
            except Exception as exc:  # noqa: BLE001 - a bad PDF is not fatal
                print(f"[bundle] issue {number}: could not bundle ({exc})")
                continue
            # The raw PDF has served its purpose, and a 40 MB blob left in git
            # history would be permanent.
            if source.is_relative_to(repo.papers):
                source.unlink()
            _copy_tree(bundle_dir, cache / f"issue-{number}")
            results[number] = meta
            built.append(number)

        if built:
            listed = ", ".join(str(n) for n in built)
            repo.commit(f"Bundle papers for issue(s) {listed}")
    return results


def sync(
    issue_number: int,
    *,
    doi: str = "",
    title: str = "",
    journal: str = "",
    pdf: Optional[Path] = None,
) -> Optional[dict]:
    """Bundle and push one Issue's paper. See `sync_all`."""
    results = sync_all(
        [
            {
                "issue": issue_number,
                "doi": doi,
                "title": title,
                "journal": journal,
                "pdf": pdf,
            }
        ]
    )
    return results.get(issue_number)


def fetch(issue_number: int, out_dir: Path) -> Optional[dict]:
    """Copy a published bundle out of the papers repository. Returns its meta."""
    out_dir = Path(out_dir)
    try:
        with PapersRepo() as repo:
            bundle = repo.papers / f"issue-{issue_number}"
            if not (bundle / "paper.txt").is_file():
                return None
            out_dir.mkdir(parents=True, exist_ok=True)
            for item in bundle.iterdir():
                target = out_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
            meta_path = out_dir / "meta.json"
            meta = json.loads(meta_path.read_text("utf-8")) if meta_path.is_file() else {}
            print(
                f"[bundle] issue {issue_number}: bundle fetched "
                f"({meta.get('text_chars', 0):,} chars, "
                f"{len(meta.get('figures', []))} figures) -> {out_dir}"
            )
            return meta
    except Exception as exc:  # noqa: BLE001 - no bundle is a normal outcome
        print(f"[bundle] papers repository unreachable ({exc})")
        return None


def discard(issue_number: int) -> bool:
    """Delete a bundle after its episode is published."""
    with PapersRepo() as repo:
        bundle = repo.papers / f"issue-{issue_number}"
        if not bundle.exists():
            return False
        shutil.rmtree(bundle)
        return repo.commit(f"Discard paper bundle for issue {issue_number}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="bundle a local PDF into a directory")
    p_build.add_argument("--issue", type=int, required=True)
    p_build.add_argument("--pdf", type=Path, required=True)
    p_build.add_argument("--out", type=Path, required=True)
    p_build.add_argument("--doi", default="")
    p_build.add_argument("--title", default="")
    p_build.add_argument("--journal", default="")

    p_sync = sub.add_parser("sync", help="bundle a dropped PDF and push it")
    p_sync.add_argument("--issue", type=int, required=True)
    p_sync.add_argument("--doi", default="")
    p_sync.add_argument("--title", default="")
    p_sync.add_argument("--journal", default="")
    p_sync.add_argument("--pdf", type=Path, default=None)

    p_fetch = sub.add_parser("fetch", help="copy a published bundle locally")
    p_fetch.add_argument("--issue", type=int, required=True)
    p_fetch.add_argument("--out", type=Path, required=True)

    p_discard = sub.add_parser("discard", help="delete a published bundle")
    p_discard.add_argument("--issue", type=int, required=True)

    p_shrink = sub.add_parser("shrink", help="downsample a PDF's images")
    p_shrink.add_argument("--pdf", type=Path, required=True)
    p_shrink.add_argument("--out", type=Path, required=True)
    p_shrink.add_argument("--max-dim", type=int, default=1600)

    args = parser.parse_args()
    if args.command == "build":
        build(
            args.pdf.read_bytes(),
            args.issue,
            args.out,
            doi=args.doi,
            title=args.title,
            journal=args.journal,
            provenance=f"local:{args.pdf.name}",
        )
    elif args.command == "sync":
        meta = sync(
            args.issue,
            doi=args.doi,
            title=args.title,
            journal=args.journal,
            pdf=args.pdf,
        )
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as fh:
                fh.write(f"bundled={'true' if meta else 'false'}\n")
        sys.exit(0 if meta else 2)
    elif args.command == "fetch":
        sys.exit(0 if fetch(args.issue, args.out) else 2)
    elif args.command == "discard":
        discard(args.issue)
    elif args.command == "shrink":
        shrink(args.pdf, args.out, args.max_dim)


if __name__ == "__main__":
    main()

"""Get the full text of a paper for script generation.

Abstracts are not enough: the skeptical content of an episode lives in the
results, the methods and the authors' own limitations paragraph. This module
tries, in order:

  1. A bundle built from a supplied PDF by paper_bundle.py — body text with
     the figure and table captions collected at the end, beside the figure
     images. Best quality: extraction alone scatters captions through the
     prose and loses everything drawn inside a raster figure.
  2. A PDF supplied by hand (issue-NN.pdf, or any PDF whose name contains the
     DOI suffix): first one emailed in and saved to the runner's temp
     directory by pdf_mailbox.py, then one committed to `inbox/pdfs/`.
  3. Europe PMC full text XML, for anything in the PMC open-access subset.
  4. The open-access PDF URL recorded on the Issue.
  5. The publisher's HTML landing page.

Publishers routinely answer scripted requests with 403 even for open-access
articles, so (3) and (4) fail often; that is expected, and the caller should
fall back to asking for a manual PDF drop rather than treating it as an error.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
PDF_INBOX = ROOT / "inbox" / "pdfs"

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
TIMEOUT = 30

# A browser UA gets through some publisher edge rules; many still refuse.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
MIN_USEFUL_CHARS = 4000


def _clean(text: str) -> str:
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class TransientFetchError(RuntimeError):
    """No full text was found, but at least one source failed only temporarily.

    A rate limit or server error says nothing about whether the paper is open,
    so the caller should retry on a later run rather than ask for a PDF.
    """


_transient: list[str] = []


def _record(exc: Exception) -> None:
    """Remember failures that might succeed on a later run."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if (
        isinstance(exc, (requests.Timeout, requests.ConnectionError))
        or status == 429
        or (status is not None and status >= 500)
    ):
        _transient.append(f"{type(exc).__name__}: {exc}")


def pdf_dirs() -> list[tuple[Path, str]]:
    """Where a manually supplied PDF may be: (directory, provenance label).

    The emailed-PDF drop directory comes first — it lives only on the runner,
    which is where paywalled PDFs belong. `inbox/pdfs/` in the repo is public
    and suits only openly licensed papers.
    """
    import pdf_mailbox  # stdlib-only; imported here to keep this module's deps light

    dirs = [(pdf_mailbox.drop_dir(), "emailed-pdf"), (PDF_INBOX, "repo-pdf")]
    return [(d, label) for d, label in dirs if d.is_dir()]


def from_bundle(issue_number: int | None) -> Optional[tuple[str, str]]:
    """Text from a bundle already pulled down this run, if there is one.

    Deliberately local-only: `paper_bundle.sync_all` does the one clone that
    fills the cache, so resolving a dozen Issues costs no extra network.
    """
    if issue_number is None:
        return None
    try:
        import paper_bundle
    except ImportError:
        return None
    bundle = paper_bundle.cached(issue_number)
    if bundle is None:
        return None
    text = (bundle / "paper.txt").read_text(encoding="utf-8")
    if len(text) < MIN_USEFUL_CHARS:
        return None
    return text, f"bundle:issue-{issue_number}"


def from_local_pdf(doi: str, issue_number: int | None) -> Optional[tuple[str, str]]:
    """Text from a supplied PDF matching this paper, if there is one."""
    suffix = doi.rsplit("/", 1)[-1].lower() if doi else ""
    for directory, label in pdf_dirs():
        candidates: list[Path] = []
        if issue_number is not None:
            candidates += list(directory.glob(f"issue-{issue_number}.pdf"))
            candidates += list(directory.glob(f"issue-{issue_number:03d}.pdf"))
        if suffix:
            candidates += [
                p for p in directory.glob("*.pdf") if suffix in p.name.lower()
            ]
        for path in candidates:
            text = pdf_bytes_to_text(path.read_bytes())
            if text and len(text) >= MIN_USEFUL_CHARS:
                return text, f"{label}:{path.name}"
    return None


def pdf_bytes_to_text(data: bytes) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  [paper] pypdf not installed; cannot read PDFs")
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return _clean("\n\n".join(pages)) or None
    except Exception as exc:  # noqa: BLE001 - any malformed PDF is just a miss
        print(f"  [paper] PDF parse failed: {exc}")
        return None


def europe_pmc_record(doi: str) -> Optional[dict]:
    """Europe PMC's record for a DOI, or None. Raises on a failed request."""
    if not doi:
        return None
    search = requests.get(
        f"{EUROPEPMC}/search",
        params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
        timeout=TIMEOUT,
    )
    search.raise_for_status()
    results = search.json().get("resultList", {}).get("result", [])
    return results[0] if results else None


def from_europe_pmc(doi: str) -> Optional[tuple[str, str]]:
    """Full text XML from Europe PMC, for papers in the PMC OA subset."""
    if not doi:
        return None
    try:
        record = europe_pmc_record(doi)
        if not record:
            return None
        pmcid = record.get("pmcid")
        if not pmcid or record.get("inPMC") != "Y":
            print("  [paper] Europe PMC: metadata only, no full text")
            return None
        full = requests.get(f"{EUROPEPMC}/{pmcid}/fullTextXML", timeout=TIMEOUT)
        full.raise_for_status()
        root = ET.fromstring(full.content)
        body = root.find(".//body")
        if body is None:
            return None
        text = _clean("\n\n".join(t.strip() for t in body.itertext() if t.strip()))
        if len(text) < MIN_USEFUL_CHARS:
            return None
        return text, f"europepmc:{pmcid}"
    except Exception as exc:  # noqa: BLE001
        _record(exc)
        print(f"  [paper] Europe PMC lookup failed: {exc}")
        return None


def from_pdf_url(pdf_url: str) -> Optional[tuple[str, str]]:
    if not pdf_url:
        return None
    try:
        resp = requests.get(
            pdf_url, headers={"User-Agent": BROWSER_UA}, timeout=TIMEOUT
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - 403 from publishers is routine
        _record(exc)
        print(f"  [paper] PDF download failed: {exc}")
        return None
    text = pdf_bytes_to_text(resp.content)
    if text and len(text) >= MIN_USEFUL_CHARS:
        return text, "pdf-url"
    return None


def from_publisher_html(doi: str) -> Optional[tuple[str, str]]:
    """Last resort: the article landing page, following the DOI."""
    if not doi:
        return None
    try:
        resp = requests.get(
            f"https://doi.org/{doi}",
            headers={"User-Agent": BROWSER_UA},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        _record(exc)
        print(f"  [paper] publisher HTML fetch failed: {exc}")
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body
    if main is None:
        return None
    text = _clean(main.get_text("\n"))
    if len(text) < MIN_USEFUL_CHARS:
        print(f"  [paper] publisher HTML too short ({len(text)} chars)")
        return None
    return text, "publisher-html"


def resolve(
    *, doi: str = "", pdf_url: str = "", issue_number: int | None = None
) -> Optional[tuple[str, str]]:
    """Return (full_text, provenance), or None if no full text is reachable.

    Raises TransientFetchError if nothing was found but a source failed with a
    rate limit, server error or timeout — worth retrying, not a missing PDF.
    """
    _transient.clear()
    for attempt in (
        lambda: from_bundle(issue_number),
        lambda: from_local_pdf(doi, issue_number),
        lambda: from_europe_pmc(doi),
        lambda: from_pdf_url(pdf_url),
        lambda: from_publisher_html(doi),
    ):
        result = attempt()
        if result:
            text, source = result
            print(f"  [paper] full text via {source} ({len(text)} chars)")
            return text, source
    if _transient:
        raise TransientFetchError("; ".join(_transient))
    return None


# --------------------------------------------------------------------------- #
# Fetching to stage
#
# The routines that write the scripts run in a sandbox that cannot reach any
# paper source: doi.org, Europe PMC, Unpaywall and the publishers are all
# refused there. GitHub Actions can reach them. So Actions fetches whatever is
# open, once, and stages it as a bundle in the private papers repository,
# which the routines can read. This is the fetch half of that.
# --------------------------------------------------------------------------- #

EUROPEPMC_PDF = "https://europepmc.org/backend/ptpmcrender.fcgi"

# A paywalled landing page is an abstract followed by a long reference list,
# which clears MIN_USEFUL_CHARS easily. Staging it would have a routine write
# an episode from the abstract, so a staged paper must carry this much body
# text *before* its last references heading: well above a structured abstract
# (two to three thousand characters), well below a research article's body.
MIN_STAGED_BODY_CHARS = 12_000


@dataclass
class Fetched:
    """Full text from an open source, with the PDF itself when that's what came."""

    text: str
    provenance: str
    pdf: Optional[bytes] = None


def body_chars(text: str) -> int:
    """Characters before the last references heading — the paper, not its citations."""
    matches = list(REFERENCES_RE.finditer(text))
    return matches[-1].start() if matches else len(text)


def looks_like_full_text(text: str) -> bool:
    return bool(text) and body_chars(text) >= MIN_STAGED_BODY_CHARS


def _download_pdf(url: str) -> Optional[bytes]:
    """The bytes at `url` if they are a PDF. Publishers often answer with HTML."""
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - a 403 from a publisher is routine
        _record(exc)
        print(f"  [paper] PDF download failed ({url[:60]}): {exc}")
        return None
    if not resp.content.lstrip()[:5].startswith(b"%PDF"):
        print(f"  [paper] {url[:60]} answered with something other than a PDF")
        return None
    return resp.content


def _pdf_fetched(data: Optional[bytes], provenance: str) -> Optional[Fetched]:
    if not data:
        return None
    text = pdf_bytes_to_text(data)
    if not text or not looks_like_full_text(text):
        print(f"  [paper] {provenance}: PDF is not the full paper")
        return None
    return Fetched(text, provenance, data)


def fetch_open_text(*, doi: str = "", pdf_url: str = "") -> Optional[Fetched]:
    """The paper's full text from open sources only, or None.

    Prefers a PDF, because a bundle built from one keeps the figure images —
    and the values drawn in a figure exist nowhere in any extraction. Falls
    back to Europe PMC's XML and then the publisher's page as text.

    Stricter than resolve(): what this returns gets staged for an unattended
    writer, so text that looks like an abstract plus references is refused.
    Raises TransientFetchError when nothing was found but a source failed
    only temporarily, so the caller can try again rather than ask for a PDF.
    """
    _transient.clear()

    found = _pdf_fetched(_download_pdf(pdf_url), "pdf-url") if pdf_url else None
    if found:
        return found

    record = None
    if doi:
        try:
            record = europe_pmc_record(doi)
        except Exception as exc:  # noqa: BLE001
            _record(exc)
            print(f"  [paper] Europe PMC lookup failed: {exc}")
    pmcid = (record or {}).get("pmcid")
    if pmcid and record.get("inPMC") == "Y":
        if record.get("isOpenAccess") == "Y":
            found = _pdf_fetched(
                _download_pdf(f"{EUROPEPMC_PDF}?accid={pmcid}&blobtype=pdf"),
                f"europepmc-pdf:{pmcid}",
            )
            if found:
                return found
        xml = from_europe_pmc(doi)
        if xml and looks_like_full_text(xml[0]):
            return Fetched(*xml)

    html = from_publisher_html(doi)
    if html and looks_like_full_text(html[0]):
        return Fetched(*html)
    if html:
        print("  [paper] publisher page is an abstract and references, not the paper")

    if _transient:
        raise TransientFetchError("; ".join(_transient))
    return None


# Papers arrive with reference lists, supplementary tables and publisher
# boilerplate; past this length the extra text costs money without improving
# the script. 120k chars is ~30k tokens — room for any main text we've seen.
MAX_PAPER_CHARS = 120_000
REFERENCES_RE = re.compile(
    r"\n\s*(References|REFERENCES|Bibliography|Literature Cited)\s*\n"
)

# The heading paper_bundle.py puts above the collected figure and table
# captions. Everything from here on is the most valuable part of the text and
# must survive trimming, even though it sits past the references heading.
FIGURES_MARKER = "\nFIGURES AND TABLES\n"


def prepare_paper_text(text: str) -> str:
    """Drop the reference list and cap the length, logging what was cut.

    Safe to run twice: a bundle's collected captions are held back, trimmed
    around, and reattached, so preparing an already-prepared bundle is a
    no-op rather than the loss of its best section.
    """
    original = len(text)
    body, marker, captions = text.partition(FIGURES_MARKER)
    # Only treat a References heading as the tail if it's in the back half —
    # an early match is more likely a table of contents or a figure label.
    matches = [m for m in REFERENCES_RE.finditer(body) if m.start() > len(body) * 0.5]
    if matches:
        body = body[: matches[-1].start()]
    if len(body) > MAX_PAPER_CHARS:
        body = body[:MAX_PAPER_CHARS]
    text = body + marker + captions
    if len(text) < original:
        print(f"  [paper] text trimmed {original:,} -> {len(text):,} chars")
    return text

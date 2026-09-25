"""Get the full text of a paper for script generation.

Abstracts are not enough: the skeptical content of an episode lives in the
results, the methods and the authors' own limitations paragraph. This module
tries, in order:

  1. A PDF supplied by hand (issue-NN.pdf, or any PDF whose name contains the
     DOI suffix): first one emailed in and saved to the runner's temp
     directory by pdf_mailbox.py, then one committed to `inbox/pdfs/`.
  2. Europe PMC full text XML, for anything in the PMC open-access subset.
  3. The open-access PDF URL recorded on the Issue.
  4. The publisher's HTML landing page.

Publishers routinely answer scripted requests with 403 even for open-access
articles, so (3) and (4) fail often; that is expected, and the caller should
fall back to asking for a manual PDF drop rather than treating it as an error.
"""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
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


def pdf_dirs() -> list[tuple[Path, str]]:
    """Where a manually supplied PDF may be: (directory, provenance label).

    The emailed-PDF drop directory comes first — it lives only on the runner,
    which is where paywalled PDFs belong. `inbox/pdfs/` in the repo is public
    and suits only openly licensed papers.
    """
    import pdf_mailbox  # stdlib-only; imported here to keep this module's deps light

    dirs = [(pdf_mailbox.drop_dir(), "emailed-pdf"), (PDF_INBOX, "repo-pdf")]
    return [(d, label) for d, label in dirs if d.is_dir()]


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


def from_europe_pmc(doi: str) -> Optional[tuple[str, str]]:
    """Full text XML from Europe PMC, for papers in the PMC OA subset."""
    if not doi:
        return None
    try:
        search = requests.get(
            f"{EUROPEPMC}/search",
            params={"query": f"DOI:{doi}", "format": "json", "resultType": "core"},
            timeout=TIMEOUT,
        )
        search.raise_for_status()
        results = search.json().get("resultList", {}).get("result", [])
        if not results:
            return None
        record = results[0]
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
    """Return (full_text, provenance) or None if no full text is reachable."""
    for attempt in (
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
    return None

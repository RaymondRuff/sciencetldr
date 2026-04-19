"""Pick the top trending PubMed paper, open a podcast Issue.

Scrapes https://pubmed.ncbi.nlm.nih.gov/trending/ — there is no native
trending endpoint in E-utilities. The page is a stable user-facing list;
we assert >=10 entries and fail loudly if the markup changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import paper_resolver
import github_issue
import select_monday_paper

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

TRENDING_URL = "https://pubmed.ncbi.nlm.nih.gov/trending/"
USER_AGENT = "ScienceTLDR-bot/1.0 (https://github.com/RaymondRuff/sciencetldr)"

MIN_TRENDING_ENTRIES = 10


def fetch_trending() -> list[dict]:
    resp = requests.get(TRENDING_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    articles = soup.select("article.full-docsum")
    entries = []
    for art in articles:
        title_el = art.select_one("a.docsum-title")
        if not title_el:
            continue
        pmid = (title_el.get("data-article-id") or "").strip()
        title = " ".join(title_el.get_text().split())
        journal_el = art.select_one(".docsum-journal-citation")
        journal = " ".join(journal_el.get_text().split()) if journal_el else ""
        entries.append({"pmid": pmid, "title": title, "journal_citation": journal})
    return entries


def fetch_doi_for_pmid(pmid: str) -> str:
    resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        params={"db": "pubmed", "id": pmid, "retmode": "json"},
        timeout=20,
    )
    resp.raise_for_status()
    s = resp.json().get("result", {}).get(pmid, {})
    for aid in s.get("articleids", []):
        if aid.get("idtype") == "doi":
            return aid.get("value", "")
    return ""


def main() -> None:
    print("[select-friday] fetching PubMed trending")
    entries = fetch_trending()
    print(f"[select-friday] parsed {len(entries)} trending entries")
    if len(entries) < MIN_TRENDING_ENTRIES:
        sys.exit(
            f"Only parsed {len(entries)} trending entries — expected >= {MIN_TRENDING_ENTRIES}. "
            "PubMed trending page markup may have changed; aborting before publishing the wrong paper."
        )

    top = entries[0]
    print(f"[select-friday] top trending: {top['title'][:80]}")

    doi = fetch_doi_for_pmid(top["pmid"]) if top["pmid"] else ""
    pdf_url = paper_resolver.resolve_pdf(doi=doi, pmid=top["pmid"])
    print(f"[select-friday] PDF: {pdf_url or 'none (closed-access fallback)'}")

    paper = {
        "title": top["title"],
        "doi": doi,
        "dice": None,
        "raw": (
            f"PubMed Trending #1\n"
            f"PMID: {top['pmid']}\n"
            f"Citation: {top['journal_citation']}"
        ),
    }
    body = select_monday_paper.render_issue_body(paper, pdf_url, "friday-trending")
    title = f"🔥 {top['title'][:160]}"
    issue_number = github_issue.open_issue(
        title=title,
        body=body,
        labels=[github_issue.PENDING_LABEL, "friday-trending"],
    )
    print(f"[select-friday] opened issue #{issue_number}")


if __name__ == "__main__":
    main()

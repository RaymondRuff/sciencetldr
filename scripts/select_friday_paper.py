"""Pick the top trending PubMed paper, open a podcast Issue.

Scrapes https://pubmed.ncbi.nlm.nih.gov/trending/ — there is no native
trending endpoint in E-utilities. The page is a stable user-facing list;
we assert >=10 entries and fail loudly if the markup changes.

Walks the top entries in order and skips any paper whose DOI is already
in episodes/ or in an open podcast-pending issue, so we do not republish
last week's pick when the trending list is sticky.
"""
from __future__ import annotations

import json
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
EPISODES_DIR = ROOT / "episodes"

TRENDING_URL = "https://pubmed.ncbi.nlm.nih.gov/trending/"
USER_AGENT = "ScienceTLDR-bot/1.0 (https://github.com/RaymondRuff/sciencetldr)"

MIN_TRENDING_ENTRIES = 10
MAX_CANDIDATES_TO_CHECK = 10


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


def already_seen_dois() -> set[str]:
    """DOIs of episodes already published or queued in an open issue."""
    seen: set[str] = set()
    for path in EPISODES_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        doi = ((data.get("source_metadata") or {}).get("doi") or "").strip()
        if doi:
            seen.add(doi.lower())
    try:
        pending = github_issue.list_pending_issues()
    except Exception as exc:
        print(f"[select-friday] warning: could not list pending issues: {exc}")
        pending = []
    for issue in pending:
        meta = github_issue.parse_metadata(issue.get("body") or "") or {}
        doi = (meta.get("doi") or "").strip()
        if doi:
            seen.add(doi.lower())
    return seen


def main() -> None:
    print("[select-friday] fetching PubMed trending")
    entries = fetch_trending()
    print(f"[select-friday] parsed {len(entries)} trending entries")
    if len(entries) < MIN_TRENDING_ENTRIES:
        sys.exit(
            f"Only parsed {len(entries)} trending entries — expected >= {MIN_TRENDING_ENTRIES}. "
            "PubMed trending page markup may have changed; aborting before publishing the wrong paper."
        )

    seen = already_seen_dois()
    print(f"[select-friday] {len(seen)} DOIs already published or pending")

    chosen = None
    for rank, entry in enumerate(entries[:MAX_CANDIDATES_TO_CHECK], start=1):
        doi = fetch_doi_for_pmid(entry["pmid"]) if entry["pmid"] else ""
        if doi and doi.lower() in seen:
            print(f"[select-friday]  #{rank} skip (already seen): {entry['title'][:70]} [{doi}]")
            continue
        chosen = {**entry, "rank": rank, "doi": doi}
        break

    if chosen is None:
        print(
            f"[select-friday] all top {MAX_CANDIDATES_TO_CHECK} trending papers already "
            "published or pending — nothing new to publish this week."
        )
        return

    print(f"[select-friday] picking #{chosen['rank']}: {chosen['title'][:80]}")

    pdf_url = paper_resolver.resolve_pdf(doi=chosen["doi"], pmid=chosen["pmid"])
    print(f"[select-friday] PDF: {pdf_url or 'none (closed-access fallback)'}")

    paper = {
        "title": chosen["title"],
        "doi": chosen["doi"],
        "dice": None,
        "raw": (
            f"PubMed Trending #{chosen['rank']}\n"
            f"PMID: {chosen['pmid']}\n"
            f"Citation: {chosen['journal_citation']}"
        ),
    }
    body = select_monday_paper.render_issue_body(paper, pdf_url, "friday-trending")
    title = f"🔥 {chosen['title'][:160]}"
    issue_number = github_issue.open_issue(
        title=title,
        body=body,
        labels=[github_issue.PENDING_LABEL, "friday-trending"],
    )
    print(f"[select-friday] opened issue #{issue_number}")


if __name__ == "__main__":
    main()

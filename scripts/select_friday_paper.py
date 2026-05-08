"""Pick the Friday trending paper, open a podcast Issue.

Source order:
  1. r/science top/week — the first peer-reviewed paper we can resolve to
     a DOI, skipping anything already published or pending.
  2. PubMed trending — automatic fallback when Reddit yields nothing
     usable (network, schema drift, all candidates were preprints, etc.).

Reddit picks are enriched via Crossref so the issue title and metadata
come from the journal record, not the redditor's editorialised headline.
"""
from __future__ import annotations

import argparse
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
import reddit_source
import crossref_lookup

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "episodes"

# PubMed-trending fallback knobs (preserved from the original script).
PUBMED_TRENDING_URL = "https://pubmed.ncbi.nlm.nih.gov/trending/"
PUBMED_UA = "ScienceTLDR-bot/1.0 (https://github.com/RaymondRuff/sciencetldr)"
MIN_PUBMED_TRENDING_ENTRIES = 10
MAX_PUBMED_CANDIDATES = 10

# Reddit knobs.
REDDIT_FETCH_LIMIT = 50
MIN_REDDIT_POSTS = 5  # below this, treat the fetch as broken — fall through.


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


def pick_from_reddit(seen: set[str]) -> dict | None:
    try:
        posts = reddit_source.fetch_top_week(limit=REDDIT_FETCH_LIMIT)
    except Exception as exc:
        print(f"[select-friday] reddit fetch failed: {exc}")
        return None

    print(f"[select-friday] reddit: {len(posts)} candidate posts after pre-filter")
    if len(posts) < MIN_REDDIT_POSTS:
        print(f"[select-friday] reddit: too few posts (<{MIN_REDDIT_POSTS}); falling back")
        return None

    for rank, post in enumerate(posts, start=1):
        doi, reason = reddit_source.extract_doi_with_reason(post.url)
        if not doi:
            print(f"[select-friday]  r#{rank} skip ({reason}): {post.title[:70]}")
            continue
        print(f"[select-friday]  r#{rank} doi via {reason}: [{doi}]")
        if doi.lower() in seen:
            print(f"[select-friday]  r#{rank} skip (already seen): {post.title[:70]} [{doi}]")
            continue
        meta = crossref_lookup.crossref_metadata(doi)
        if not meta or not meta.get("title"):
            print(f"[select-friday]  r#{rank} skip (no crossref record): [{doi}]")
            continue
        if meta.get("is_preprint"):
            print(f"[select-friday]  r#{rank} skip (preprint): {meta['title'][:70]} [{doi}]")
            continue
        pmid = crossref_lookup.pmid_for_doi(doi) or ""
        return {
            "rank": rank,
            "doi": doi,
            "pmid": pmid,
            "title": meta["title"],
            "journal_citation": meta.get("journal", ""),
            "raw": (
                f"r/science top/week #{rank} (score {post.score}, "
                f"{post.num_comments} comments)\n"
                f"Flair: {post.flair or '(none)'}\n"
                f"Reddit: {post.reddit_url}\n"
                f"Linked URL: {post.url}\n"
                f"Journal: {meta.get('journal', '')}\n"
                f"Published: {meta.get('published', '')}"
            ),
        }
    print("[select-friday] reddit: no candidate survived filtering")
    return None


def fetch_pubmed_trending() -> list[dict]:
    resp = requests.get(PUBMED_TRENDING_URL, headers={"User-Agent": PUBMED_UA}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    entries = []
    for art in soup.select("article.full-docsum"):
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


def pick_from_pubmed(seen: set[str]) -> dict | None:
    entries = fetch_pubmed_trending()
    print(f"[select-friday] pubmed: {len(entries)} trending entries")
    if len(entries) < MIN_PUBMED_TRENDING_ENTRIES:
        sys.exit(
            f"Only parsed {len(entries)} PubMed trending entries — expected "
            f">= {MIN_PUBMED_TRENDING_ENTRIES}. Markup may have changed; aborting."
        )
    for rank, entry in enumerate(entries[:MAX_PUBMED_CANDIDATES], start=1):
        doi = fetch_doi_for_pmid(entry["pmid"]) if entry["pmid"] else ""
        if doi and doi.lower() in seen:
            print(f"[select-friday]  p#{rank} skip (already seen): {entry['title'][:70]} [{doi}]")
            continue
        meta = crossref_lookup.crossref_metadata(doi) if doi else None
        if (meta and meta.get("is_preprint")) or doi.lower().startswith("10.1101/"):
            print(f"[select-friday]  p#{rank} skip (preprint): {entry['title'][:70]} [{doi}]")
            continue
        return {
            "rank": rank,
            "doi": doi,
            "pmid": entry["pmid"],
            "title": (meta or {}).get("title") or entry["title"],
            "journal_citation": entry["journal_citation"],
            "raw": (
                f"PubMed Trending #{rank}\n"
                f"PMID: {entry['pmid']}\n"
                f"Citation: {entry['journal_citation']}"
            ),
        }
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Pick a Friday trending paper.")
    parser.add_argument("--dry-run", action="store_true", help="print pick, do not open issue")
    parser.add_argument(
        "--source",
        choices=["auto", "reddit", "pubmed"],
        default="auto",
        help="auto = reddit then pubmed fallback (default); reddit/pubmed = single source",
    )
    args = parser.parse_args()

    seen = already_seen_dois()
    print(f"[select-friday] {len(seen)} DOIs already published or pending")

    chosen: dict | None = None
    primary_label = ""
    fell_back = False

    if args.source in ("auto", "reddit"):
        print("[select-friday] trying r/science top/week")
        chosen = pick_from_reddit(seen)
        if chosen:
            primary_label = "friday-reddit"

    if chosen is None and args.source in ("auto", "pubmed"):
        if args.source == "auto":
            print("[select-friday] reddit yielded nothing — falling back to PubMed trending")
            fell_back = True
        else:
            print("[select-friday] using PubMed trending")
        chosen = pick_from_pubmed(seen)
        if chosen:
            primary_label = "friday-trending"

    if chosen is None:
        print("[select-friday] no candidates — nothing new to publish this week.")
        return

    print(f"[select-friday] picking {primary_label} #{chosen['rank']}: {chosen['title'][:80]}")

    pdf_url = paper_resolver.resolve_pdf(doi=chosen["doi"], pmid=chosen.get("pmid", ""))
    print(f"[select-friday] PDF: {pdf_url or 'none (closed-access fallback)'}")

    paper = {
        "title": chosen["title"],
        "doi": chosen["doi"],
        "dice": None,
        "raw": chosen["raw"],
    }
    body = select_monday_paper.render_issue_body(paper, pdf_url, primary_label)
    title_emoji = "🔥" if primary_label == "friday-reddit" else "📈"
    issue_title = f"{title_emoji} {chosen['title'][:160]}"

    labels = [github_issue.PENDING_LABEL, primary_label]
    if fell_back:
        labels.append("friday-reddit-failed")

    if args.dry_run:
        print("[select-friday] DRY RUN — would open issue:")
        print(f"  title: {issue_title}")
        print(f"  labels: {', '.join(labels)}")
        print("  body:")
        print("  " + body.replace("\n", "\n  "))
        return

    issue_number = github_issue.open_issue(title=issue_title, body=body, labels=labels)
    print(f"[select-friday] opened issue #{issue_number}")


if __name__ == "__main__":
    main()

"""Fetch top peer-reviewed papers from r/science, extract DOIs.

r/science requires direct links to peer-reviewed papers, but submitters
sometimes link to news write-ups instead. We fetch top/week, drop
removed/stickied/self/young posts, and try to extract a DOI from each
link — first by regex on the URL, then by fetching the page and reading
its citation_doi meta tag. News-aggregator domains are skipped early.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REDDIT_TOP_URL = "https://www.reddit.com/r/science/top.json"
REDDIT_UA = "ScienceTLDR-bot/1.0 (by /u/sciencetldr; +https://github.com/RaymondRuff/sciencetldr)"
JOURNAL_UA = "Mozilla/5.0 (compatible; ScienceTLDR-bot/1.0; +https://github.com/RaymondRuff/sciencetldr)"

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)

# Posts younger than this haven't been vetted by mods — skip them so we
# don't pick up rule-violating links that get removed minutes later.
MIN_POST_AGE_SECONDS = 12 * 3600

# News / aggregator / video domains: even if r/science rules say "link to
# the paper," some posts slip through. Skip these without HTTP-fetching.
NEWS_DOMAINS = {
    "nytimes.com", "theguardian.com", "washingtonpost.com", "bbc.com", "bbc.co.uk",
    "cnn.com", "reuters.com", "apnews.com", "bloomberg.com", "ft.com",
    "phys.org", "sciencealert.com", "livescience.com", "newscientist.com",
    "scientificamerican.com", "nationalgeographic.com", "smithsonianmag.com",
    "popularmechanics.com", "popsci.com", "iflscience.com", "newatlas.com",
    "techcrunch.com", "theverge.com", "wired.com", "vice.com", "arstechnica.com",
    "medium.com", "substack.com", "youtube.com", "youtu.be", "twitter.com",
    "x.com", "reddit.com",
}


@dataclass
class RedditPost:
    title: str
    url: str
    permalink: str
    score: int
    num_comments: int
    created_utc: float
    flair: str

    @property
    def reddit_url(self) -> str:
        return f"https://www.reddit.com{self.permalink}"


def fetch_top_week(limit: int = 50) -> list[RedditPost]:
    """Fetch top/week posts from r/science. Raises on transport / format errors."""
    resp = requests.get(
        REDDIT_TOP_URL,
        params={"t": "week", "limit": limit},
        headers={"User-Agent": REDDIT_UA, "Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    ctype = resp.headers.get("Content-Type", "").lower()
    if "json" not in ctype:
        raise RuntimeError(f"Reddit returned non-JSON content-type: {ctype!r}")

    data = resp.json()
    children = data.get("data", {}).get("children", [])
    now = time.time()
    posts: list[RedditPost] = []
    for child in children:
        d = child.get("data") or {}
        if d.get("stickied"):
            continue
        if d.get("is_self"):
            continue
        if d.get("removed_by_category"):
            continue
        if (d.get("author") or "[deleted]") in ("[deleted]", "AutoModerator"):
            continue
        if (now - float(d.get("created_utc") or 0)) < MIN_POST_AGE_SECONDS:
            continue
        url = (d.get("url") or "").strip()
        if not url:
            continue
        posts.append(RedditPost(
            title=(d.get("title") or "").strip(),
            url=url,
            permalink=(d.get("permalink") or "").strip(),
            score=int(d.get("score") or 0),
            num_comments=int(d.get("num_comments") or 0),
            created_utc=float(d.get("created_utc") or 0),
            flair=(d.get("link_flair_text") or "").strip(),
        ))
    return posts


def _hostname(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def is_news_domain(url: str) -> bool:
    host = _hostname(url)
    if not host:
        return True
    return any(host == d or host.endswith("." + d) for d in NEWS_DOMAINS)


def _clean_doi(doi: str) -> str:
    return doi.rstrip(".,;:)]'\"")


def _doi_from_url(url: str) -> Optional[str]:
    m = DOI_RE.search(url)
    if not m:
        return None
    return _clean_doi(m.group(0))


META_NAMES = ("citation_doi", "DC.Identifier", "dc.identifier", "DC.identifier", "prism.doi")


def _doi_from_html(url: str) -> Optional[str]:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": JOURNAL_UA, "Accept": "text/html"},
            timeout=20,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return None
    # Some publishers redirect to a DOI URL — check the final URL too.
    doi = _doi_from_url(resp.url)
    if doi:
        return doi
    soup = BeautifulSoup(resp.text, "html.parser")
    for name in META_NAMES:
        tag = soup.find("meta", attrs={"name": name})
        if not tag:
            continue
        content = (tag.get("content") or "").strip()
        if content.lower().startswith("doi:"):
            content = content[4:].strip()
        m = DOI_RE.search(content)
        if m:
            return _clean_doi(m.group(0))
    return None


def extract_doi_with_reason(url: str) -> tuple[Optional[str], str]:
    """Returns (doi, reason). Reason is a short tag describing the path taken
    or why no DOI was found — useful for logs / debugging."""
    if is_news_domain(url):
        return None, "news-domain"
    doi = _doi_from_url(url)
    if doi:
        return doi, "url-regex"
    doi = _doi_from_html(url)
    if doi:
        return doi, "meta-tag"
    return None, "no-doi-found"


def extract_doi(url: str) -> Optional[str]:
    """URL-embedded DOI first, then journal-page meta tags. None on miss."""
    return extract_doi_with_reason(url)[0]

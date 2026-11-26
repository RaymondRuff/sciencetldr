"""Fetch top peer-reviewed papers from r/science, extract DOIs.

r/science requires direct links to peer-reviewed papers, but submitters
sometimes link to news write-ups instead. We fetch top/week, drop
removed/stickied/self/young posts, and try to extract a DOI from each
link — first by regex on the URL, then by fetching the page and reading
its citation_doi meta tag. News-aggregator domains are skipped early.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REDDIT_TOP_URL = "https://www.reddit.com/r/science/top.json"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_OAUTH_TOP_URL = "https://oauth.reddit.com/r/science/top"
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


def _app_only_token() -> str:
    """An application-only bearer token, from the app's id and secret.

    Reddit 403s datacenter IPs — which every GitHub runner is — on the public
    JSON endpoint whatever User-Agent you send, and on 2026-11-19 that cost
    the Friday episode its strand. OAuth is the supported way in from a
    server, and it is not rate-limited to death: a hundred requests a minute
    per client against the one request a week this makes.
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not client_id or not secret:
        raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are not set")
    resp = requests.post(
        REDDIT_TOKEN_URL,
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": REDDIT_UA},
        timeout=30,
    )
    resp.raise_for_status()
    token = (resp.json() or {}).get("access_token", "")
    if not token:
        raise RuntimeError("Reddit returned no access_token")
    return token


def have_credentials() -> bool:
    """Whether an app id and secret are configured for the OAuth route."""
    return bool(
        os.environ.get("REDDIT_CLIENT_ID", "").strip()
        and os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    )


def fetch_top_week(limit: int = 50) -> list[RedditPost]:
    """Fetch top/week posts, by OAuth where it is configured.

    There is no fallback any more, and that is deliberate. The old one asked
    for `/r/science/top.rss`, which Reddit answers "Not Found" for every
    client including a browser — sorted RSS listings no longer exist — so it
    had never once worked, while logging "trying RSS" as though it might.
    A failure that announces itself is worth more than a fallback that cannot
    succeed: select_friday_paper then says so and takes the PubMed strand,
    which is what the hosts tell the listener.
    """
    if have_credentials():
        return _fetch_top_week_oauth(limit)
    print("[reddit] no app credentials; using the public endpoint (403s from a runner)")
    return _fetch_top_week_json(limit)


def _fetch_top_week_oauth(limit: int) -> list[RedditPost]:
    resp = requests.get(
        REDDIT_OAUTH_TOP_URL,
        params={"t": "week", "limit": limit},
        headers={
            "Authorization": f"bearer {_app_only_token()}",
            "User-Agent": REDDIT_UA,
            "Accept": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _posts_from_listing(resp.json())


def _fetch_top_week_json(limit: int) -> list[RedditPost]:
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

    return _posts_from_listing(resp.json())


def _posts_from_listing(data: dict) -> list[RedditPost]:
    """The usable posts in a Reddit listing, whichever route fetched it.

    oauth.reddit.com returns the same shape as the public .json endpoint, so
    the filtering lives here rather than twice.
    """
    children = (data or {}).get("data", {}).get("children", [])
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

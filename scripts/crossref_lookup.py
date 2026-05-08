"""Crossref + NCBI metadata enrichment for a DOI.

Crossref gives us a canonical title/journal/authors plus the type field
that lets us reject preprints (`type == "posted-content"` or
`subtype == "preprint"`). NCBI's idconv resolves DOI→PMID so the existing
PMC PDF lookup in paper_resolver still works for Reddit-sourced papers.
"""
from __future__ import annotations

import os
from typing import Optional

import requests

CROSSREF_URL = "https://api.crossref.org/works/"
NCBI_IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
CONTACT_EMAIL = (
    os.environ.get("CROSSREF_EMAIL")
    or os.environ.get("UNPAYWALL_EMAIL")
    or "sciencetldrpod@gmail.com"
)


def crossref_metadata(doi: str) -> Optional[dict]:
    """Fetch canonical metadata for a DOI. Returns None on miss / failure."""
    if not doi:
        return None
    try:
        resp = requests.get(
            CROSSREF_URL + doi,
            params={"mailto": CONTACT_EMAIL},
            headers={"User-Agent": f"ScienceTLDR-bot/1.0 (mailto:{CONTACT_EMAIL})"},
            timeout=20,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except Exception:
        return None

    msg = (resp.json() or {}).get("message") or {}
    titles = msg.get("title") or []
    title = titles[0].strip() if titles else ""

    container = msg.get("container-title") or []
    journal = container[0] if container else ""

    authors = msg.get("author") or []
    author_names = [
        " ".join(filter(None, [a.get("given"), a.get("family")])).strip()
        for a in authors
    ]

    item_type = (msg.get("type") or "").strip()
    subtype = (msg.get("subtype") or "").strip()
    is_preprint = (
        item_type == "posted-content"
        or subtype == "preprint"
        or doi.lower().startswith("10.1101/")
    )

    issued = msg.get("issued", {}).get("date-parts") or []
    pub_date = "-".join(str(p) for p in issued[0]) if issued and issued[0] else ""

    return {
        "title": title,
        "journal": journal,
        "authors": author_names,
        "type": item_type,
        "subtype": subtype,
        "is_preprint": is_preprint,
        "published": pub_date,
    }


def pmid_for_doi(doi: str) -> Optional[str]:
    """Resolve DOI → PMID via NCBI idconv. Returns None when not indexed in PubMed."""
    if not doi:
        return None
    try:
        resp = requests.get(
            NCBI_IDCONV_URL,
            params={
                "ids": doi,
                "format": "json",
                "tool": "sciencetldr",
                "email": CONTACT_EMAIL,
            },
            timeout=20,
        )
        resp.raise_for_status()
    except Exception:
        return None
    records = (resp.json() or {}).get("records") or []
    if not records:
        return None
    pmid = records[0].get("pmid")
    return str(pmid) if pmid else None

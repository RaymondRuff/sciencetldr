"""Resolve a paper to an open-access PDF URL when possible.

Tries, in order: PMC (if PMID has PMCID) → Unpaywall (DOI). Returns None if no
open-access version is available; in that case the calling script should ask
the user to drop the PDF into inbox/pdfs/ as a fallback.
"""
from __future__ import annotations

import os
from typing import Optional

import requests

UNPAYWALL_EMAIL = os.environ.get("UNPAYWALL_EMAIL", "sciencetldrpod@gmail.com")
NCBI_KEY = os.environ.get("NCBI_API_KEY")


def pmid_to_pmcid(pmid: str) -> Optional[str]:
    params = {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "json"}
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY
    resp = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi",
        params=params, timeout=20,
    )
    resp.raise_for_status()
    linksets = resp.json().get("linksets", [])
    if not linksets:
        return None
    for db in linksets[0].get("linksetdbs", []):
        if db.get("dbto") == "pmc" and db.get("links"):
            return f"PMC{db['links'][0]}"
    return None


def pmc_pdf_url(pmcid: str) -> str:
    pmcid = pmcid.upper()
    if not pmcid.startswith("PMC"):
        pmcid = f"PMC{pmcid}"
    return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"


def unpaywall_pdf(doi: str) -> Optional[str]:
    if not doi:
        return None
    try:
        resp = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": UNPAYWALL_EMAIL},
            timeout=20,
        )
        resp.raise_for_status()
    except requests.HTTPError:
        return None
    data = resp.json()
    best = data.get("best_oa_location")
    if best and best.get("url_for_pdf"):
        return best["url_for_pdf"]
    for loc in data.get("oa_locations", []) or []:
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"]
    return None


def resolve_pdf(*, doi: str = "", pmid: str = "") -> Optional[str]:
    if pmid:
        try:
            pmcid = pmid_to_pmcid(pmid)
            if pmcid:
                return pmc_pdf_url(pmcid)
        except Exception:
            pass
    if doi:
        return unpaywall_pdf(doi)
    return None

"""Weekly literature digest agent.

Runs the user's tier/DICE prompt as the system message, gives Claude tools to
search PubMed, bioRxiv (via Europe PMC), and the web, then writes the digest
markdown and emails it to the recipient list.

Uses Opus 4.7 with extended thinking — explicit user requirement.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import anthropic
import markdown as md
import requests

import send_email

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
DIGEST_DIR = ROOT / "digest"

DIGEST_MODEL = "claude-opus-4-7"
THINKING_EFFORT = "xhigh"  # low | medium | high | xhigh | max — Opus 4.7 adaptive thinking
MAX_OUTPUT_TOKENS = 16000
MAX_AGENT_ITERATIONS = 30

NCBI_KEY = os.environ.get("NCBI_API_KEY")  # optional, raises rate limit

PUBMED_SEARCH_TOOL = {
    "name": "pubmed_search",
    "description": (
        "Search PubMed (peer-reviewed biomedical literature) for papers matching a query. "
        "Returns recent papers with title, authors, journal, DOI, and PMID. "
        "Use PubMed query syntax (e.g., field tags like [tiab], boolean AND/OR/NOT)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "PubMed query"},
            "days": {"type": "integer", "description": "Days back from today", "default": 7},
            "max_results": {"type": "integer", "description": "Max results to return (1-50)", "default": 20},
        },
        "required": ["query"],
    },
}

BIORXIV_SEARCH_TOOL = {
    "name": "biorxiv_search",
    "description": (
        "Search bioRxiv and medRxiv preprints (via Europe PMC) for papers matching a keyword query. "
        "Returns recent preprints with title, authors, DOI, and abstract."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "days": {"type": "integer", "default": 7},
            "max_results": {"type": "integer", "default": 20},
        },
        "required": ["query"],
    },
}

WRITE_DIGEST_TOOL = {
    "name": "write_digest_file",
    "description": (
        "Write the final assembled digest as a Markdown file. Call this exactly once when "
        "the digest is complete. The file is timestamped automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "markdown": {"type": "string", "description": "Full markdown content"},
        },
        "required": ["markdown"],
    },
}

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 15,
}


def pubmed_search(query: str, days: int = 7, max_results: int = 20) -> dict:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    es_params = {
        "db": "pubmed",
        "term": query,
        "datetype": "pdat",
        "reldate": days,
        "retmode": "json",
        "retmax": min(max(max_results, 1), 50),
    }
    if NCBI_KEY:
        es_params["api_key"] = NCBI_KEY
    es = requests.get(base + "esearch.fcgi", params=es_params, timeout=30)
    es.raise_for_status()
    pmids = es.json().get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return {"query": query, "count": 0, "papers": []}
    sm_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
    if NCBI_KEY:
        sm_params["api_key"] = NCBI_KEY
    sm = requests.get(base + "esummary.fcgi", params=sm_params, timeout=30)
    sm.raise_for_status()
    summaries = sm.json().get("result", {})
    papers = []
    for pmid in pmids:
        s = summaries.get(pmid)
        if not s:
            continue
        doi = ""
        for aid in s.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        papers.append({
            "pmid": pmid,
            "title": s.get("title", ""),
            "authors": [a.get("name") for a in s.get("authors", [])][:8],
            "journal": s.get("fulljournalname") or s.get("source", ""),
            "pub_date": s.get("pubdate", ""),
            "doi": doi,
        })
    return {"query": query, "count": len(papers), "papers": papers}


def biorxiv_search(query: str, days: int = 7, max_results: int = 20) -> dict:
    today = datetime.now(tz=timezone.utc).date()
    start = today - timedelta(days=days)
    pmc_query = f"SRC:PPR AND ({query}) AND FIRST_PDATE:[{start} TO {today}]"
    resp = requests.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={
            "query": pmc_query,
            "format": "json",
            "resultType": "core",
            "pageSize": min(max(max_results, 1), 25),
        },
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("resultList", {}).get("result", [])
    papers = []
    for r in results:
        papers.append({
            "title": r.get("title", ""),
            "authors": (r.get("authorString") or "")[:300],
            "preprint_server": r.get("source", ""),
            "doi": r.get("doi", ""),
            "pub_date": r.get("firstPublicationDate", ""),
            "abstract": (r.get("abstractText") or "")[:1500],
        })
    return {"query": query, "count": len(papers), "papers": papers}


def write_digest_file(markdown: str) -> dict:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=timezone.utc).date().isoformat()
    path = DIGEST_DIR / f"{today}.md"
    path.write_text(markdown, encoding="utf-8")
    return {"path": str(path), "bytes_written": len(markdown.encode("utf-8"))}


TOOL_HANDLERS = {
    "pubmed_search": pubmed_search,
    "biorxiv_search": biorxiv_search,
    "write_digest_file": write_digest_file,
}


def run_agent(system_prompt: str, user_message: str) -> tuple[bool, Path | None]:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]
    tools = [PUBMED_SEARCH_TOOL, BIORXIV_SEARCH_TOOL, WRITE_DIGEST_TOOL, WEB_SEARCH_TOOL]

    digest_path: Path | None = None

    for iteration in range(MAX_AGENT_ITERATIONS):
        print(f"[digest] iteration {iteration + 1}")
        response = client.messages.create(
            model=DIGEST_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": THINKING_EFFORT},
            system=system_prompt,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            return digest_path is not None, digest_path

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            handler = TOOL_HANDLERS.get(name)
            if handler is None:
                continue
            args = dict(block.input or {})
            arg_keys = list(args.keys())
            print(f"  → {name}({', '.join(arg_keys)})")
            try:
                result = handler(**args)
                content = json.dumps(result)[:50_000]
                if name == "write_digest_file":
                    digest_path = Path(result["path"])
            except Exception as exc:
                content = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
                print(f"    ! tool error: {exc}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        if not tool_results:
            return digest_path is not None, digest_path
        messages.append({"role": "user", "content": tool_results})

    print(f"[digest] hit max iterations ({MAX_AGENT_ITERATIONS})")
    return digest_path is not None, digest_path


def email_digest(digest_path: Path) -> None:
    body_md = digest_path.read_text(encoding="utf-8")
    body_html = md.markdown(body_md, extensions=["extra", "sane_lists"])
    today = datetime.now(tz=timezone.utc).date().isoformat()
    recipients = send_email.recipients_from_env()
    print(f"[email] sending to {len(recipients)} recipient(s)")
    send_email.send(
        subject=f"Science TLDR Weekly Digest — {today}",
        body_text=body_md,
        recipients=recipients,
        body_html=f"<html><body style='font-family:system-ui,sans-serif;max-width:42rem'>{body_html}</body></html>",
    )


def main() -> None:
    system_prompt = (PROMPTS_DIR / "digest.md").read_text(encoding="utf-8")
    today_iso = datetime.now(tz=timezone.utc).date().isoformat()
    user_message = (
        f"Today is {today_iso}. Produce this week's literature digest following the "
        f"system prompt. Use the available tools to search PubMed, bioRxiv, and the web. "
        f"When the digest is complete, call write_digest_file with the full markdown. "
        f"After write_digest_file returns, end your turn."
    )

    success, digest_path = run_agent(system_prompt, user_message)
    if not success or digest_path is None:
        sys.exit("Agent did not produce a digest file")

    print(f"[digest] wrote {digest_path}")

    if os.environ.get("DIGEST_RECIPIENTS"):
        email_digest(digest_path)
    else:
        print("[email] DIGEST_RECIPIENTS not set, skipping email")


if __name__ == "__main__":
    main()

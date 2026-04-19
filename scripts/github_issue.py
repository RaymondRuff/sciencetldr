"""Thin wrapper around the `gh` CLI for issue operations.

The `gh` CLI is preinstalled on GitHub Actions runners and authenticates
automatically when GH_TOKEN or GITHUB_TOKEN is in the environment.
"""
from __future__ import annotations

import json
import re
import subprocess

PENDING_LABEL = "podcast-pending"

METADATA_RE = re.compile(
    r"<!-- METADATA -->\s*```json\s*(.*?)```\s*<!-- /METADATA -->",
    re.DOTALL,
)


def _run(args: list[str]) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout


def open_issue(title: str, body: str, labels: list[str]) -> int:
    out = _run([
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
        "--label", ",".join(labels),
    ])
    url = out.strip().splitlines()[-1]
    return int(url.rsplit("/", 1)[-1])


def list_pending_issues() -> list[dict]:
    out = _run([
        "gh", "issue", "list",
        "--state", "open",
        "--label", PENDING_LABEL,
        "--json", "number,title,body,createdAt",
        "--limit", "50",
    ])
    issues = json.loads(out)
    issues.sort(key=lambda i: i["createdAt"])
    return issues


def parse_metadata(body: str) -> dict | None:
    match = METADATA_RE.search(body)
    if not match:
        return None
    return json.loads(match.group(1))


def comment(issue_number: int, body: str) -> None:
    _run(["gh", "issue", "comment", str(issue_number), "--body", body])


def close(issue_number: int) -> None:
    _run(["gh", "issue", "close", str(issue_number)])


def render_metadata_block(metadata: dict) -> str:
    return (
        "<!-- METADATA -->\n"
        "```json\n"
        + json.dumps(metadata, indent=2, ensure_ascii=False)
        + "\n```\n"
        "<!-- /METADATA -->"
    )

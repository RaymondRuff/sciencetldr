"""Thin wrapper around the `gh` CLI for issue operations.

The `gh` CLI is preinstalled on GitHub Actions runners and authenticates
automatically when GH_TOKEN or GITHUB_TOKEN is in the environment.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

PENDING_LABEL = "podcast-pending"

METADATA_RE = re.compile(
    r"<!-- METADATA -->\s*```json\s*(.*?)```\s*<!-- /METADATA -->",
    re.DOTALL,
)


_AUTH_FAILURE_HINTS = (
    "http 401",
    "bad credentials",
    "requires authentication",
    "authentication failed",
    "gh auth login",
    "token has expired",
    "expired",
)


def _looks_like_auth_failure(text: str) -> bool:
    low = text.lower()
    return any(hint in low for hint in _AUTH_FAILURE_HINTS)


class GhError(subprocess.CalledProcessError):
    """A failed `gh` invocation that surfaces gh's own stderr.

    Subclasses CalledProcessError so existing `except subprocess.CalledProcessError`
    handlers keep catching it, but its message includes the stderr gh wrote — the
    default CalledProcessError string drops it, which is what made an expired token
    show up as an opaque "exit status 1" — plus a hint when the failure looks like
    an authentication problem.
    """

    def __str__(self) -> str:
        detail = (self.stderr or "").strip()
        base = super().__str__()
        if not detail:
            return base
        message = f"{base}\n  gh stderr: {detail}"
        if _looks_like_auth_failure(detail):
            message += (
                "\n  hint: this looks like an auth failure — check that the GH_PAT "
                "secret holds a valid, unexpired token with Contents + Issues write "
                "access to this repo."
            )
        return message


def _run(args: list[str]) -> str:
    # gh emits UTF-8 (issue titles carry emoji); don't let a Windows locale
    # codepage decide how to read it.
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise GhError(result.returncode, args, output=result.stdout, stderr=result.stderr)
    return result.stdout


def ensure_auth() -> None:
    """Fail fast with an actionable message if `gh` has no working credentials.

    Call this before doing real work so a missing or expired GH_PAT surfaces
    immediately, instead of after minutes of parsing and PDF resolution only to die
    on the final `gh issue create`.
    """
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    if result.returncode != 0:
        raise GhError(
            result.returncode,
            ["gh", "auth", "status"],
            output=result.stdout,
            stderr=(result.stderr or result.stdout or "").strip()
            or "gh reported no authenticated account",
        )


def ensure_label(name: str, color: str = "ededed", description: str = "") -> None:
    """Create (or update) the label with --force; a no-op if it already exists.

    A non-zero exit is non-fatal — open_issue still runs and raises a clear error
    if the label is genuinely missing — but we no longer swallow the reason.
    """
    result = subprocess.run(
        ["gh", "label", "create", name, "--color", color, "--description", description, "--force"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"[github_issue] warning: could not ensure label {name!r}: "
            f"{(result.stderr or '').strip()}",
            file=sys.stderr,
        )


def open_issue(title: str, body: str, labels: list[str]) -> int:
    for label in labels:
        ensure_label(label)
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
        "--json", "number,title,body,createdAt,labels",
        "--limit", "50",
    ])
    issues = json.loads(out)
    issues.sort(key=lambda i: i["createdAt"])
    return issues


def get_issue(number: int) -> dict | None:
    """One Issue, fetched directly, in the shape list_pending_issues() returns.

    The list endpoint is eventually consistent: an Issue created seconds ago
    is routinely missing from it. A direct GET is not, so this is how the
    sweep learns about an Issue it has only just opened.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    try:
        found = json.loads(_run(["gh", "api", f"repos/{repo}/issues/{number}"]))
    except Exception as exc:  # noqa: BLE001 - a missing Issue is not fatal here
        print(f"[issue] could not read #{number}: {exc}")
        return None
    if "pull_request" in found:
        return None
    return {
        "number": found["number"],
        "title": found.get("title", ""),
        "body": found.get("body") or "",
        "createdAt": found.get("created_at", ""),
        "labels": [{"name": l["name"]} for l in found.get("labels", [])],
    }


def ensure_listed(issues: list[dict], numbers) -> list[dict]:
    """`issues`, plus any of `numbers` the list endpoint has not caught up with.

    On 2026-11-18 a one-off arrived with its PDF attached. The sweep opened
    Issue #138 and, in the very next call, listed the pending Issues without
    it — so the PDF was never staged, the reply was consumed as belonging to
    an Issue that "isn't waiting", and a request was then emailed for the PDF
    that had just been thrown away. Two fetches in one run, two different
    answers.
    """
    known = {i["number"] for i in issues}
    added = []
    for number in sorted(set(numbers) - known):
        found = get_issue(number)
        if found is None:
            continue
        print(f"[issue] #{number} was missing from the Issue list; fetched it directly")
        added.append(found)
    if not added:
        return issues
    return sorted(issues + added, key=lambda i: i.get("createdAt") or "")


def open_issues_with_label(label: str) -> list[int]:
    """Numbers of the open Issues carrying this label. REST, so a routine can call it."""
    repo = os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    out = _run([
        "gh", "api",
        f"repos/{repo}/issues?labels={label}&state=open&per_page=100",
    ])
    return [i["number"] for i in json.loads(out) if "pull_request" not in i]


def parse_metadata(body: str) -> dict | None:
    match = METADATA_RE.search(body)
    if not match:
        return None
    return json.loads(match.group(1))


def add_labels(issue_number: int, labels: list[str]) -> None:
    for label in labels:
        ensure_label(label)
    _run(["gh", "issue", "edit", str(issue_number), "--add-label", ",".join(labels)])


def remove_label(issue_number: int, label: str) -> None:
    """Remove a label; a label that is not there is not an error."""
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number), "--remove-label", label],
        capture_output=True,
        text=True,
    )


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

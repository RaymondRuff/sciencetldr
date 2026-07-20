"""Thin wrapper around the `gh` CLI for issue operations.

The `gh` CLI is preinstalled on GitHub Actions runners and authenticates
automatically when GH_TOKEN or GITHUB_TOKEN is in the environment.
"""
from __future__ import annotations

import json
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
    result = subprocess.run(args, capture_output=True, text=True)
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

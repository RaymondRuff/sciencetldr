"""Tell the owner when a pipeline workflow fails — once per breakage.

Run by .github/workflows/alert-on-failure.yml after every completed run of the
pipeline's workflows. A failure opens one Issue, assigned to the repository
owner so GitHub notifies them. Further failures of the same workflow only edit
that Issue's body, and an edit notifies nobody. The next success closes it
with a one-line comment. So a workflow that breaks and stays broken costs one
notification, and its recovery one more.

Standard library and the `gh` CLI only, so the job needs no dependency install.

Environment (set by the workflow):
  WORKFLOW, CONCLUSION, RUN_URL, RUN_ID, EVENT, OWNER, GH_TOKEN, GH_REPO
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ALERT_LABEL = "pipeline-alert"
FAILED = {"failure", "timed_out", "startup_failure"}
LOG_LINES = 40

OPEN, UPDATE, CLOSE, NOTHING = "open", "update", "close", "nothing"


def title_for(workflow: str) -> str:
    return f"Pipeline failing: {workflow}"


def decide(conclusion: str, existing: dict | None) -> str:
    """What to do about one completed run, given the open alert for its workflow."""
    if conclusion in FAILED:
        return UPDATE if existing else OPEN
    if conclusion == "success" and existing:
        return CLOSE
    return NOTHING  # cancelled, skipped, or a success with nothing to close


def count_from(body: str) -> int:
    for line in body.splitlines():
        if line.startswith("**Failed runs:**"):
            digits = "".join(ch for ch in line if ch.isdigit())
            return int(digits) if digits else 1
    return 1


def render_body(*, workflow: str, run_url: str, event: str, count: int, first: str, log: str) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tail = f"\n\n<details><summary>End of the failed log</summary>\n\n```\n{log}\n```\n</details>" if log else ""
    return (
        f"The **{workflow}** workflow is failing. Nothing downstream of it will run "
        "until it is fixed.\n\n"
        f"**First failed:** {first}\n"
        f"**Latest failure:** {now}, [{event} run]({run_url})\n"
        f"**Failed runs:** {count}\n\n"
        "Later failures only update this Issue, so it notifies once. It closes by "
        "itself on the workflow's next successful run."
        f"{tail}\n"
    )


def gh(*args: str) -> str:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout


def open_alert(workflow: str) -> dict | None:
    found = json.loads(
        gh("issue", "list", "--label", ALERT_LABEL, "--state", "open",
           "--json", "number,title,body", "--limit", "50")
    )
    title = title_for(workflow)
    return next((i for i in found if i["title"] == title), None)


def failed_log(run_id: str) -> str:
    try:
        log = gh("run", "view", run_id, "--log-failed")
    except RuntimeError as exc:
        return f"(log unavailable: {exc})"
    # Each line is "job<TAB>step<TAB>timestamp text"; keep the text.
    lines = [line.split("\t")[-1] for line in log.splitlines() if line.strip()]
    return "\n".join(lines[-LOG_LINES:])


def first_failed(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("**First failed:**"):
            return line.split("**First failed:**", 1)[1].strip()
    return ""


def main() -> None:
    workflow = os.environ["WORKFLOW"]
    conclusion = os.environ.get("CONCLUSION", "")
    run_url = os.environ.get("RUN_URL", "")
    run_id = os.environ.get("RUN_ID", "")
    event = os.environ.get("EVENT", "")
    owner = os.environ.get("OWNER", "")

    existing = open_alert(workflow)
    action = decide(conclusion, existing)
    print(f"[alert] {workflow}: {conclusion} -> {action}")
    if action == NOTHING:
        return
    if action == CLOSE:
        gh("issue", "comment", str(existing["number"]),
           "--body", f"Recovered: [this run]({run_url}) succeeded.")
        gh("issue", "close", str(existing["number"]))
        return

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log = failed_log(run_id) if run_id else ""
    if action == UPDATE:
        body = render_body(
            workflow=workflow, run_url=run_url, event=event,
            count=count_from(existing["body"]) + 1,
            first=first_failed(existing["body"]) or now, log=log,
        )
        gh("issue", "edit", str(existing["number"]), "--body", body)
        return

    subprocess.run(
        ["gh", "label", "create", ALERT_LABEL, "--color", "b60205",
         "--description", "A pipeline workflow is failing", "--force"],
        capture_output=True,
    )
    body = render_body(workflow=workflow, run_url=run_url, event=event, count=1, first=now, log=log)
    args = ["issue", "create", "--title", title_for(workflow), "--body", body,
            "--label", ALERT_LABEL]
    if owner:
        args += ["--assignee", owner]
    print(gh(*args).strip())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - say why, and fail the alert job visibly
        sys.exit(f"[alert] could not record the failure: {exc}")

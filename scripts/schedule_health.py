"""How many of GitHub's scheduled runs actually happen.

On 2026-11-14 somebody emailed the podcast address and waited forty minutes
for an answer that a half-hourly poll should have given in fifteen. The code
was fine; the schedule was not. This measures that, because the pipeline's
latency promises are only as good as the scheduler underneath them.

What it does: counts the `schedule`-event runs GitHub actually started, over a
window, against the number the workflow's crons asked for, and reports the gaps
between consecutive runs — which is the number that matters, since a mail waits
for the next run, not for the next cron.

**It reports per workflow, not per cron, on purpose.** A run does not say which
cron started it, and the first attempt to infer it from the clock was wrong:
with runs arriving ten to sixty minutes late, a daily 14:00 sweep and a 13:30
poll tick are indistinguishable. Per-workflow delivery is the honest unit.

Read-only: one `gh api` GET per page. Needs no secrets beyond the `gh` auth
already present in Actions.

Usage:
  uv run python scripts/schedule_health.py              # last 14 days
  uv run python scripts/schedule_health.py --days 30
  uv run python scripts/schedule_health.py --markdown   # for a step summary
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CRON_RE = re.compile(r"^\s*-\s*cron:\s*['\"](?P<cron>[^'\"]+)['\"]", re.MULTILINE)
PAGE_SIZE = 100
MAX_PAGES = 5


def crons_in(path: Path) -> list[str]:
    """The cron expressions a workflow file declares."""
    return CRON_RE.findall(path.read_text(encoding="utf-8"))


def _field(field: str, low: int, high: int) -> set[int]:
    """One cron field expanded to the values it matches."""
    found: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = int(raw_step)
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part.lstrip("-"):
            start_s, _, end_s = part.partition("-")
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)
            if step > 1:  # "5/10" is unusual but means from 5 onwards
                end = high
        found |= {v for v in range(start, end + 1, step) if low <= v <= high}
    return found


def expected(cron: str, start: datetime, end: datetime) -> int:
    """How many times this cron should fire between two instants (UTC)."""
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"not a 5-field cron: {cron!r}")
    minutes, hours, doms, months, dows = (
        _field(parts[0], 0, 59),
        _field(parts[1], 0, 23),
        _field(parts[2], 1, 31),
        _field(parts[3], 1, 12),
        _field(parts[4], 0, 7),
    )
    if 7 in dows:
        dows.add(0)  # cron allows both for Sunday
    dom_restricted = parts[2] != "*"
    dow_restricted = parts[4] != "*"
    count = 0
    # Half-open [start, end): a 24-hour window holds 48 ticks of `*/30`, not
    # 49, which is what anyone checking the arithmetic by hand expects.
    moment = start.replace(second=0, microsecond=0)
    while moment < end:
        if moment.month in months and moment.hour in hours and moment.minute in minutes:
            dom_ok = moment.day in doms
            dow_ok = (moment.weekday() + 1) % 7 in dows
            # Cron ORs day-of-month and day-of-week when both are restricted.
            if dom_restricted and dow_restricted:
                hit = dom_ok or dow_ok
            elif dom_restricted:
                hit = dom_ok
            elif dow_restricted:
                hit = dow_ok
            else:
                hit = True
            count += hit
        moment += timedelta(minutes=1)
    return count


def gh_runs(repo: str, workflow: str, pages: int = MAX_PAGES) -> list[datetime]:
    """Start times of this workflow's schedule-event runs, newest first.

    Paged by hand: `gh --paginate` follows GitHub's numeric-id `next` links,
    which the sandbox's API proxy refuses.
    """
    found: list[datetime] = []
    for page in range(1, pages + 1):
        url = (
            f"repos/{repo}/actions/workflows/{workflow}/runs"
            f"?event=schedule&per_page={PAGE_SIZE}&page={page}"
        )
        result = subprocess.run(
            ["gh", "api", url], capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            error = (result.stderr or result.stdout).strip()
            # A workflow added on a branch but not yet on the default branch
            # has no runs and no API entry. That is "nothing to count", not a
            # failure — otherwise this script breaks itself on first commit.
            if "404" in error or "Not Found" in error:
                print(f"[schedule] {workflow}: not known to GitHub yet; counting zero")
                return []
            raise RuntimeError(f"gh api failed for {workflow}: {error[:200]}")
        runs = json.loads(result.stdout).get("workflow_runs", [])
        for run in runs:
            found.append(
                datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            )
        if len(runs) < PAGE_SIZE:
            break
    return found


def gaps_hours(stamps: list[datetime]) -> list[float]:
    ordered = sorted(stamps)
    return [(b - a).total_seconds() / 3600 for a, b in zip(ordered, ordered[1:])]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def report(repo: str, days: int, fetch=gh_runs) -> dict:
    """Delivery rates and gaps per workflow, for the last `days` days."""
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    workflows = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        crons = crons_in(path)
        if not crons:
            continue
        wanted = sum(expected(cron, start, end) for cron in crons)
        stamps = [s for s in fetch(repo, path.name) if start <= s <= end]
        gaps = gaps_hours(stamps)
        workflows.append(
            {
                "workflow": path.name,
                "crons": crons,
                "stamps": sorted(stamps),
                "expected": wanted,
                "delivered": len(stamps),
                "rate": (len(stamps) / wanted) if wanted else 0.0,
                "per_day": len(stamps) / days,
                "median_gap": percentile(gaps, 0.5),
                "p90_gap": percentile(gaps, 0.9),
                "max_gap": max(gaps) if gaps else 0.0,
            }
        )
    return {"repo": repo, "days": days, "from": start, "to": end, "workflows": workflows}


def as_text(data: dict) -> str:
    lines = [
        f"Scheduled-run delivery for {data['repo']}, "
        f"last {data['days']} days (to {data['to']:%Y-%m-%d %H:%M} UTC)",
        "",
    ]
    for row in data["workflows"]:
        lines.append(f"{row['workflow']}  crons: {', '.join(row['crons'])}")
        lines.append(
            f"  delivered {row['delivered']} of {row['expected']} asked for "
            f"= {row['rate']:.1%}   ({row['per_day']:.1f} runs/day)"
        )
        if row["rate"] > 1 or (row["expected"] == 0 and row["delivered"]):
            # The crons are read from the working tree, the runs from history.
            lines.append(
                "  (more runs than ticks asked for: the crons changed inside this "
                "window, so the rate is meaningless here — read the times instead)"
            )
        lines.append(
            f"  gap between runs: median {row['median_gap']:.1f} h, "
            f"90th pct {row['p90_gap']:.1f} h, worst {row['max_gap']:.1f} h"
        )
        lines.append("")
    lines.append(
        "A mail or a PDF waits for the next delivered run, so the gap is the "
        "latency the pipeline actually offers — not the cron interval."
    )
    return "\n".join(lines)


def daily_slot(cron: str) -> tuple[int, int] | None:
    """(hour, minute) if this cron fires once a day, else None.

    Only then can a run be attributed to a cron at all: with three sweeps a
    day, well separated, a start time says which one it was. With a cron every
    half hour it says nothing, which is why this returns None for those.
    """
    parts = cron.split()
    if len(parts) != 5:
        return None
    minutes, hours = _field(parts[0], 0, 59), _field(parts[1], 0, 23)
    if len(minutes) != 1 or len(hours) != 1 or parts[2] != "*" or parts[4] != "*":
        return None
    return next(iter(hours)), next(iter(minutes))


def as_times(data: dict, window_minutes: float = 90) -> str:
    """Every run, by day, with how late it was — the view that judges a change.

    A run counts as a cron's only if it started within `window_minutes` after
    it. Ninety is deliberate: observed lateness for runs that plausibly belong
    to a cron is ten to sixty minutes, and a window of a few hours attributes
    everything to something. At six hours this called a 10:39 run a late 07:28
    sweep and reported "all fired" on a day when nothing fired on time — the
    confident wrong attribution this whole exercise started with. A run no cron
    can claim is listed bare.
    """
    lines = []
    for row in data["workflows"]:
        slots = {cron: daily_slot(cron) for cron in row["crons"]}
        daily = {c: s for c, s in slots.items() if s}
        lines.append(f"{row['workflow']}  crons: {', '.join(row['crons'])}")
        if not row["stamps"]:
            lines += ["  (no scheduled runs in the window)", ""]
            continue
        by_day = defaultdict(list)
        for stamp in row["stamps"]:
            by_day[stamp.date()].append(stamp)
        for day, stamps in sorted(by_day.items()):
            marks = []
            for stamp in stamps:
                best, late = None, None
                for cron, (hour, minute) in daily.items():
                    due = stamp.replace(hour=hour, minute=minute)
                    delta = (stamp - due).total_seconds() / 60
                    if 0 <= delta <= window_minutes and (late is None or delta < late):
                        best, late = cron, delta
                marks.append(
                    f"{stamp:%H:%M}" + (f"(+{late:.0f}m)" if best else "")
                )
            missing = ""
            if daily:
                fired = {
                    cron
                    for stamp in stamps
                    for cron, (hour, minute) in daily.items()
                    if 0 <= (stamp - stamp.replace(hour=hour, minute=minute)).total_seconds() / 60
                    <= window_minutes
                }
                missed = sorted(set(daily) - fired)
                missing = f"   missed: {', '.join(missed)}" if missed else "   all fired"
            lines.append(f"  {day}  {'  '.join(marks)}{missing}")
        lines.append("")
    return "\n".join(lines)


def as_markdown(data: dict) -> str:
    lines = [
        f"### Scheduled-run delivery — last {data['days']} days",
        "",
        "| workflow | crons | asked | delivered | rate | runs/day | median gap | worst gap |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["workflows"]:
        lines.append(
            f"| `{row['workflow']}` | `{'`, `'.join(row['crons'])}` | {row['expected']} | "
            f"{row['delivered']} | **{row['rate']:.1%}** | {row['per_day']:.1f} | "
            f"{row['median_gap']:.1f} h | {row['max_gap']:.1f} h |"
        )
    lines += [
        "",
        "The gap is what a waiting email actually experiences. Counted per "
        "workflow, not per cron: a run does not record which cron started it, "
        "and with runs arriving ten to sixty minutes late the clock cannot tell "
        "a daily sweep from a poll tick.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument(
        "--times", action="store_true", help="every run by day, with how late it was"
    )
    parser.add_argument(
        "--repo", default=os.environ.get("GITHUB_REPOSITORY", "RaymondRuff/sciencetldr")
    )
    args = parser.parse_args()
    data = report(args.repo, args.days)
    text = as_markdown(data) if args.markdown else as_text(data)
    print(text)
    if args.times:
        print()
        print(as_times(data))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(as_markdown(data) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - a measurement failing is not a pipeline failure
        sys.exit(f"[schedule] could not measure: {exc}")

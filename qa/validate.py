#!/usr/bin/env python3
"""Validate only artifacts that are committed to this repository."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "17"
JSON_PATH = RESULTS / "fault_injection_results.json"
CSV_PATH = RESULTS / "fault_injection_requests.csv"


def main() -> int:
    for path in (JSON_PATH, CSV_PATH, ROOT / "experiments" / "fault_injection_lab.py"):
        if not path.is_file():
            raise SystemExit(f"required public artifact is missing: {path.relative_to(ROOT)}")

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    summaries = data.get("summaries")
    if data.get("all_assertions_passed") is not True:
        raise SystemExit("stored experiment does not declare all assertions passed")
    if not isinstance(summaries, list) or len(summaries) != 6:
        raise SystemExit("expected six archived experiment summaries")

    by_run_mode = {}
    for row in summaries:
        run_id, mode = row.get("run"), row.get("mode")
        if mode not in {"no_retry", "retry_failover"} or run_id not in {0, 1, 2}:
            raise SystemExit(f"unexpected run/mode pair: {run_id!r}/{mode!r}")
        if row.get("requests") != 120:
            raise SystemExit("each archived run must contain 120 requests")
        if row.get("success", -1) < 0 or row.get("success", 121) > 120:
            raise SystemExit("success count outside valid range")
        by_run_mode[(run_id, mode)] = row
    if len(by_run_mode) != 6:
        raise SystemExit("duplicate or missing run/mode summary")
    for run_id in range(3):
        baseline = by_run_mode[(run_id, "no_retry")]
        retry = by_run_mode[(run_id, "retry_failover")]
        if not (0 < baseline["success"] < baseline["requests"]):
            raise SystemExit(f"run {run_id}: baseline should expose injected failures")
        if retry["success"] != retry["requests"] or retry["failed"] != 0:
            raise SystemExit(f"run {run_id}: retry/failover did not recover all requests")

    counts = Counter()
    with CSV_PATH.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["run"]), row["mode"])
            if key not in by_run_mode:
                raise SystemExit(f"CSV contains unknown run/mode: {key}")
            counts[key] += 1
    if any(counts[(run_id, mode)] != 120 for run_id in range(3) for mode in ("no_retry", "retry_failover")):
        raise SystemExit("CSV row counts do not match the six archived summaries")

    print("FAULT-INJECTION ARCHIVE VALIDATION: PASS")
    print("summaries:", len(summaries), "request rows:", sum(counts.values()))
    print("scope: committed local two-replica experiment artifacts only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

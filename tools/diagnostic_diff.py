#!/usr/bin/env python3
"""
Diagnostic metadata diff tool.

Compares two build diagnostic JSON files and reports differences in
module status, pass/fail counts, build metadata, and per-module output.

Usage:
    python3 tools/diagnostic_diff.py <baseline.json> <current.json>
    python3 tools/diagnostic_diff.py <baseline.json> <current.json> --json
    python3 tools/diagnostic_diff.py <baseline.json> <current.json> --summary
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_diagnostic(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Diagnostic file not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _modules_to_dict(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    modules = data.get("modules", [])
    return {m["name"]: m for m in modules if "name" in m}


def diff_diagnostics(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []

    for field in ("commit", "total_modules", "passed", "failed", "chunked"):
        old_val = baseline.get(field)
        new_val = current.get(field)
        if old_val != new_val:
            changes.append({
                "field": field,
                "baseline": old_val,
                "current": new_val,
                "change": "modified",
            })

    old_mods = _modules_to_dict(baseline)
    new_mods = _modules_to_dict(current)

    for name in set(old_mods.keys()) | set(new_mods.keys()):
        old_mod = old_mods.get(name)
        new_mod = new_mods.get(name)
        if old_mod and not new_mod:
            changes.append({
                "field": f"module.{name}",
                "baseline": old_mod.get("status"),
                "current": None,
                "change": "removed",
            })
        elif new_mod and not old_mod:
            changes.append({
                "field": f"module.{name}",
                "baseline": None,
                "current": new_mod.get("status"),
                "change": "added",
            })
        elif old_mod and new_mod:
            for sub in ("status", "elapsed_seconds", "artifact", "output"):
                ov = old_mod.get(sub)
                nv = new_mod.get(sub)
                if ov != nv:
                    changes.append({
                        "field": f"module.{name}.{sub}",
                        "baseline": ov,
                        "current": nv,
                        "change": "modified",
                    })

    summary = {
        "total_changes": len(changes),
        "modules_added": sum(1 for c in changes if c["change"] == "added" and c["field"].startswith("module.")),
        "modules_removed": sum(1 for c in changes if c["change"] == "removed" and c["field"].startswith("module.")),
        "modules_modified": sum(1 for c in changes if c["change"] == "modified" and c["field"].startswith("module.")),
        "metadata_changed": sum(1 for c in changes if not c["field"].startswith("module.")),
        "passed_changed": baseline.get("passed") != current.get("passed"),
        "failed_changed": baseline.get("failed") != current.get("failed"),
        "baseline_commit": baseline.get("commit"),
        "current_commit": current.get("commit"),
        "baseline_passed": baseline.get("passed", 0),
        "current_passed": current.get("passed", 0),
        "baseline_failed": baseline.get("failed", 0),
        "current_failed": current.get("failed", 0),
    }

    return {
        "summary": summary,
        "changes": changes,
    }


def render_text(result: dict[str, Any]) -> str:
    s = result["summary"]
    lines = [
        "# Diagnostic Diff Report",
        "",
        f"Baseline commit: {s['baseline_commit']}",
        f"Current commit:  {s['current_commit']}",
        "",
        f"Pass count: {s['baseline_passed']} -> {s['current_passed']}{' (changed)' if s['passed_changed'] else ''}",
        f"Fail count: {s['baseline_failed']} -> {s['current_failed']}{' (changed)' if s['failed_changed'] else ''}",
        "",
        f"Total changes: {s['total_changes']}",
        f"  Modules added: {s['modules_added']}",
        f"  Modules removed: {s['modules_removed']}",
        f"  Modules modified: {s['modules_modified']}",
        f"  Metadata changed: {s['metadata_changed']}",
        "",
    ]
    if not result["changes"]:
        lines.append("No differences detected. Diagnostics are identical.")
    else:
        lines.append("## Changes")
        lines.append("")
        lines.append("| Field | Baseline | Current | Change |")
        lines.append("| --- | --- | --- | --- |")
        for c in result["changes"]:
            lines.append(f"| {c['field']} | {c['baseline']} | {c['current']} | {c['change']} |")
    return "\n".join(lines) + "\n"


def detect_regressions(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect regressions from pass to fail/error/missing in module statuses."""
    regressions: list[dict[str, Any]] = []
    for c in result.get("changes", []):
        field = c.get("field", "")
        if not field.startswith("module."):
            continue
        if ".status" not in field:
            continue
        baseline_val = str(c.get("baseline", "")).upper()
        current_val = str(c.get("current", "")).upper()
        pass_states = {"PASS", "OK"}
        fail_states = {"FAIL", "ERROR", "MISSING", "NONE"}
        if baseline_val in pass_states and current_val in fail_states:
            module_name = field.replace("module.", "").replace(".status", "")
            regressions.append({
                "module": module_name,
                "baseline_status": c.get("baseline"),
                "current_status": c.get("current"),
                "field": field,
            })
    return regressions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff two build diagnostic JSON files.")
    parser.add_argument("baseline", help="Baseline diagnostic JSON file path")
    parser.add_argument("current", help="Current diagnostic JSON file path")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of Markdown")
    parser.add_argument("--summary", action="store_true", help="Output only the summary section")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit non-zero when module status changes from pass to fail/error/missing")
    args = parser.parse_args(argv)

    try:
        baseline = load_diagnostic(args.baseline)
        current = load_diagnostic(args.current)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = diff_diagnostics(baseline, current)

    if args.fail_on_regression:
        regressions = detect_regressions(result)
        result["regressions"] = regressions
        result["summary"]["regression_count"] = len(regressions)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    elif args.summary:
        print(json.dumps(result["summary"], indent=2, default=str))
    else:
        print(render_text(result), end="")
        if args.fail_on_regression and result.get("regressions"):
            print("\n## Regressions Detected\n")
            for r in result["regressions"]:
                print(f"- {r['module']}: {r['baseline_status']} -> {r['current_status']}")

    if args.fail_on_regression:
        regressions = result.get("regressions", [])
        if regressions:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

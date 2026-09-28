"""Record a declared attempt matrix and retain missing/error rows in reports."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import statistics


def fingerprint(tasks):
    return hashlib.sha256(repr([asdict(t) for t in tasks]).encode()).hexdigest()


def execute_matrix(output, tasks, conditions, repeats, runner, metadata, workers=2):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    attempts = [{"id": f"{task.id}--{condition}--{repeat}", "task": task.id,
                 "condition": condition, "repeat": repeat}
                for repeat in range(1, repeats + 1) for task in tasks for condition in conditions]
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "task_sha256": fingerprint(tasks),
                "agent_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))},
                "conditions": list(conditions), "attempts": attempts, **metadata}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    lookup = {task.id: task for task in tasks}
    def run(attempt):
        try:
            result = runner(lookup[attempt["task"]], attempt["condition"], attempt["repeat"])
        except Exception as error:
            # Preserve the attempt, but don't publish arbitrary exception strings containing paths/keys.
            result = {"passed": False, "status": "runner_error", "error_type": type(error).__name__}
        result.update(attempt)
        (output / f"{attempt['id']}.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, attempt) for attempt in attempts]
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            print(f"{index}/{len(attempts)} {result['id']}: {result['status']}", flush=True)
    return summarize_matrix(output)


def summarize_matrix(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text())
    rows = []
    for attempt in manifest["attempts"]:
        path = output / f"{attempt['id']}.json"
        result = json.loads(path.read_text()) if path.exists() else {**attempt, "passed": False, "status": "missing_attempt"}
        rows.append(result)
    fields = ["id", "task", "condition", "repeat", "passed", "status", "actions", "model_calls",
              "prompt_tokens", "completion_tokens", "reported_cost_usd", "fault_exposed", "failed_actions", "repeated_actions"]
    with (output / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    lines = ["# Experiment results", "", "| Condition | Passed / attempts | Rate | Mean actions | Fault exposed |", "| --- | ---: | ---: | ---: | ---: |"]
    for condition in manifest["conditions"]:
        group = [r for r in rows if r["condition"] == condition]
        passed = sum(bool(r["passed"]) for r in group)
        exposed = sum(bool(r.get("fault_exposed")) for r in group)
        action_rows = [r["actions"] for r in group if "actions" in r]
        summary[condition] = {"passed": passed, "attempts": len(group), "pass_rate": passed / len(group),
                              "mean_actions": statistics.mean(action_rows) if action_rows else None,
                              "actions_observed": len(action_rows), "fault_exposed": exposed,
                              "passed_when_exposed": sum(bool(r["passed"]) for r in group if r.get("fault_exposed")),
                              "failed_actions": sum(r.get("failed_actions", 0) for r in group),
                              "repeated_actions": sum(r.get("repeated_actions", 0) for r in group)}
        mean = summary[condition]["mean_actions"]
        lines.append(f"| {condition} | {passed}/{len(group)} | {100*passed/len(group):.1f}% | {mean if mean is not None else 'N/A'} | {exposed} |")
    lines += ["", "Missing attempts and runner/API errors count as failures. Mean actions uses recorded attempts only.",
              "Repeated runs on the same tasks are not independent task samples; these are descriptive results.",
              "", "## Per-task results", "", "| Task | " + " | ".join(manifest["conditions"]) + " |",
              "| --- | " + " | ".join("---:" for _ in manifest["conditions"]) + " |"]
    for task in dict.fromkeys(a["task"] for a in manifest["attempts"]):
        cells = []
        for condition in manifest["conditions"]:
            group = [r for r in rows if r["task"] == task and r["condition"] == condition]
            cells.append(f"{sum(bool(r['passed']) for r in group)}/{len(group)}")
        lines.append(f"| {task} | " + " | ".join(cells) + " |")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    text = "\n".join(lines) + "\n"
    (output / "summary.md").write_text(text)
    return text

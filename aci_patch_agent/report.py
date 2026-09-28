"""Build tables from saved attempt files, without another model call."""

import csv
import json
from pathlib import Path


def report(directory):
    directory = Path(directory)
    config = json.loads((directory / "run.json").read_text())
    rows = []
    for task in config["tasks"]:
        path = directory / f"{task}.json"
        if path.exists():
            row = json.loads(path.read_text())
        else:
            row = {"task": task, "status": "missing_attempt", "passed": False}
        rows.append(row)
    fields = ["task", "status", "passed", "actions", "model_calls", "prompt_tokens", "completion_tokens", "reported_cost_usd", "seconds"]
    with (directory / "results.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    solved = sum(bool(r["passed"]) for r in rows)
    text = [f"# Results: {solved}/{len(rows)} ({100 * solved / len(rows):.1f}%)", "",
            "One attempt per task. Missing attempts and all error/limit statuses count as failures.", "",
            "| Task | Outcome | Actions | Model calls | Tokens (input + output) |",
            "| --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        tokens = row.get("prompt_tokens", 0) + row.get("completion_tokens", 0)
        text.append(f"| {row['task']} | {row['status']} | {row.get('actions', 0)} | {row.get('model_calls', 0)} | {tokens} |")
    markdown = "\n".join(text) + "\n"
    (directory / "summary.md").write_text(markdown)
    return markdown

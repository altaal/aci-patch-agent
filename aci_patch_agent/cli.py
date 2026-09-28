import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from .agent import SYSTEM_PROMPT, run_task
from .client import DEFAULT_MODEL, ModelError, OpenRouterClient
from .report import report
from .sandbox import DEFAULT_IMAGE, DockerSandbox
from .tasks import TASKS
from .tools import TOOLS


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main():
    parser = argparse.ArgumentParser(description="Run a small coding agent and publish inspectable results.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run live model calls; OPENROUTER_API_KEY is required.")
    run.add_argument("--task", choices=["all"] + [t.id for t in TASKS], default="all")
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--max-actions", type=positive_int, default=15)
    run.add_argument("--max-tokens", type=positive_int, default=1200, help="Completion token limit per request.")
    run.add_argument("--max-total-tokens", type=positive_int, default=32_000, help="Stop before next request after this reported token total.")
    run.add_argument("--image", default=DEFAULT_IMAGE)
    run.add_argument("--output", type=Path, required=True, help="A new directory; existing runs are never overwritten.")
    summarize = commands.add_parser("report", help="Rebuild the result table from saved traces; no API key needed.")
    summarize.add_argument("directory", type=Path)
    commands.add_parser("tasks", help="List the development tasks.")
    args = parser.parse_args()
    if args.command == "tasks":
        for task in TASKS:
            print(f"{task.id}: {task.issue}")
        return
    if args.command == "report":
        print(report(args.directory))
        return
    try:
        client = OpenRouterClient(args.model, args.max_tokens)
        sandbox = DockerSandbox(args.image)
        image = sandbox.preflight()
    except (ModelError, RuntimeError) as error:
        parser.exit(2, f"{error}\n")
    if args.output.exists():
        parser.exit(2, "Output directory already exists. Choose a new directory to preserve previous attempts.\n")
    tasks = [t for t in TASKS if args.task == "all" or t.id == args.task]
    args.output.mkdir(parents=True)
    source_root = Path(__file__).resolve().parent
    repository = source_root.parent
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, capture_output=True, text=True) if (repository / ".git").exists() else None
    config = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "tasks": [t.id for t in tasks], "model": args.model, "temperature": 0,
              "max_actions": args.max_actions, "max_tokens": args.max_tokens,
              "max_total_tokens": args.max_total_tokens, "image": image,
              "git_revision": revision.stdout.strip() if revision and revision.returncode == 0 else None,
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_root.glob("*.py"))},
              "task_sha256": hashlib.sha256(repr([asdict(t) for t in tasks]).encode()).hexdigest(),
              "system_prompt": SYSTEM_PROMPT, "tools": TOOLS}
    (args.output / "run.json").write_text(json.dumps(config, indent=2) + "\n")
    for task in tasks:
        print(f"Running {task.id} ...", flush=True)
        result = run_task(task, client, sandbox, max_actions=args.max_actions, max_total_tokens=args.max_total_tokens)
        (args.output / f"{task.id}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"  {result['status']}, {result['actions']} actions", flush=True)
    print(report(args.output))


if __name__ == "__main__":
    main()

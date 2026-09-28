"""Change only the edit syntax check and its truthful tool description."""

import argparse
from functools import partial

from .agent import SYSTEM_PROMPT, run_task
from .client import DEFAULT_MODEL, OpenRouterClient
from .eval_tasks import EVAL_TASKS
from .experiment import execute_matrix, summarize_matrix
from .sandbox import DockerSandbox
from .tools import Workspace, tool_schemas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        print(summarize_matrix(args.output))
        return
    sandbox = DockerSandbox()
    image = sandbox.preflight()
    OpenRouterClient()  # Fail before creating the matrix if the credential is missing.
    def runner(task, condition, repeat):
        checked = condition == "checked"
        client = OpenRouterClient(tools=tool_schemas(checked))
        return run_task(task, client, sandbox, workspace_factory=partial(Workspace, checked=checked))
    metadata = {"experiment": "edit-syntax-check", "model": DEFAULT_MODEL, "temperature": 0,
                "max_actions": 15, "max_tokens": 1200, "max_total_tokens": 32000, "image": image,
                "system_prompt": SYSTEM_PROMPT, "tool_schemas": {c: tool_schemas(c == "checked") for c in ["checked", "unchecked"]}}
    print(execute_matrix(args.output, EVAL_TASKS, ["checked", "unchecked"], 3, runner, metadata))


if __name__ == "__main__":
    main()

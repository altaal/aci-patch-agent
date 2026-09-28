"""The model can view and change one source string, never evaluation code."""

from .tasks import Task


def tool(name, description, properties=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties or {},
                           "required": required or [], "additionalProperties": False}}}


TOOLS = [
    tool("view", "Show numbered lines of solution.py.",
         {"start": {"type": "integer"}, "end": {"type": "integer"}}),
    tool("edit", "Replace an inclusive line range. Invalid Python syntax is rejected without changing the source.",
         {"start": {"type": "integer"}, "end": {"type": "integer"}, "replacement": {"type": "string"}},
         ["start", "end", "replacement"]),
    tool("test", "Run example checks in an isolated container. Passing examples is not final success."),
    tool("submit", "Finish and submit the current source for separate evaluation."),
]


class Workspace:
    def __init__(self, task: Task, sandbox):
        self.task, self.sandbox = task, sandbox
        self.source = task.source

    def execute(self, name, args):
        if not isinstance(args, dict):
            return {"error": "Arguments must be a JSON object."}
        allowed = {"view": {"start", "end"}, "edit": {"start", "end", "replacement"}, "test": set(), "submit": set()}
        if name not in allowed or args.keys() - allowed[name]:
            return {"error": "Unknown tool or argument. Use view, edit, test, or submit."}
        if name in {"view", "edit"}:
            lines = self.source.splitlines()
            start, end = args.get("start", 1), args.get("end", len(lines))
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                return {"error": f"Invalid inclusive line range; source has {len(lines)} lines. Source unchanged."}
            if name == "view":
                end = min(end, start + 99)
                return {"source": "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1)), "total_lines": len(lines)}
            if not {"start", "end", "replacement"} <= args.keys() or not isinstance(args["replacement"], str):
                return {"error": "edit needs start, end, and string replacement. Source unchanged."}
            candidate = "\n".join(lines[:start-1] + args["replacement"].splitlines() + lines[end:]) + "\n"
            if len(candidate.encode()) > 16_384:
                return {"error": "Source exceeds 16 KiB. Source unchanged."}
            try:
                compile(candidate, "solution.py", "exec")
            except (SyntaxError, ValueError) as error:
                return {"accepted": False, "error": f"{type(error).__name__}: {error}. Source unchanged."}
            if not candidate.strip():
                return {"error": "Empty source is not accepted. Source unchanged."}
            self.source = candidate
            return {"accepted": True, **self.execute("view", {})}
        if name == "test":
            return self.sandbox.check(self.task, self.source)
        return {"submitted": True}

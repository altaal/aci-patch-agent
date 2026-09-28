"""Five authored development tasks, not a held-out benchmark."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    args: tuple
    expected: object = None
    raises: str | None = None


@dataclass(frozen=True)
class Task:
    id: str
    function: str
    issue: str
    source: str
    examples: tuple[Case, ...]
    evaluation: tuple[Case, ...]


TASKS = (
    Task(
        "normalize-method", "normalize_method",
        "Return an HTTP method as text. Decode bytes using ASCII; preserve strings exactly. "
        "Reject other types with TypeError. Non-ASCII bytes must raise UnicodeDecodeError.",
        "def normalize_method(method):\n    return str(method)\n",
        (Case((b"GET",), "GET"), Case(("POST",), "POST")),
        (Case((b"DELETE",), "DELETE"), Case(("get",), "get"), Case((b"",), ""),
         Case((42,), raises="TypeError"), Case((None,), raises="TypeError"),
         Case((b"\xff",), raises="UnicodeDecodeError")),
    ),
    Task(
        "chunked", "chunked",
        "Split a list into consecutive lists of size n, including a shorter final chunk. "
        "Empty input returns []. n must be a positive integer; bool is not accepted. "
        "Raise TypeError for other n types and ValueError for non-positive n.",
        "def chunked(items, n):\n    return [items[i:i+n] for i in range(0, len(items)-n+1, n)]\n",
        (Case(([1, 2, 3], 2), [[1, 2], [3]]), Case(([], 2), [])),
        (Case(([1, 2], 5), [[1, 2]]), Case(([1, 2, 3, 4], 2), [[1, 2], [3, 4]]),
         Case(([1], 0), raises="ValueError"), Case(([], -1), raises="ValueError"),
         Case(([1], True), raises="TypeError"), Case(([1], 1.5), raises="TypeError")),
    ),
    Task(
        "merge-intervals", "merge_intervals",
        "Merge overlapping or touching closed integer intervals [start, end]. "
        "Input can be unsorted; return sorted lists, preserving every endpoint. "
        "Return [] for empty input. Raise ValueError if any start exceeds its end.",
        "def merge_intervals(intervals):\n    result = []\n    for start, end in sorted(intervals):\n        if result and start < result[-1][1]:\n            result[-1][1] = end\n        else:\n            result.append([start, end])\n    return result\n",
        (Case(([[1, 4], [2, 3]],), [[1, 4]]), Case(([],), [])),
        (Case(([[5, 7], [1, 3], [3, 5]],), [[1, 7]]), Case(([[0, 0], [2, 2]],), [[0, 0], [2, 2]]),
         Case(([[-3, -1], [-2, 2]],), [[-3, 2]]), Case(([[3, 2]],), raises="ValueError"),
         Case(([[1, 9], [2, 3], [4, 5]],), [[1, 9]])),
    ),
    Task(
        "parse-bool", "parse_bool",
        "Parse a string after stripping whitespace and ignoring case. "
        "True tokens: true, yes, 1. False tokens: false, no, 0. "
        "Reject any other string with ValueError and any non-string with TypeError.",
        "def parse_bool(text):\n    return bool(text)\n",
        (Case(("false",), False), Case((" YES ",), True)),
        (Case(("0",), False), Case((" No\n",), False), Case(("TRUE",), True),
         Case(("1",), True), Case(("",), raises="ValueError"), Case(("maybe",), raises="ValueError"),
         Case((0,), raises="TypeError"), Case((True,), raises="TypeError")),
    ),
    Task(
        "unique-stable", "unique_stable",
        "Remove duplicate items from a list while keeping the first occurrence order. "
        "Determine duplicates using Python equality, including unhashable lists and dicts. "
        "Return a list; empty input returns [].",
        "def unique_stable(items):\n    return list(set(items))\n",
        (Case(([3, 1, 3, 2, 1],), [3, 1, 2]), Case(([[1], [1], [2]],), [[1], [2]])),
        (Case(([],), []), Case(([{"x": 1}, {"x": 1}, {"x": 2}],), [{"x": 1}, {"x": 2}]),
         Case(([True, 1, False, 0],), [True, False]), Case(([None, "a", None],), [None, "a"]),
         Case((["z", "a", "z", "b"],), ["z", "a", "b"])),
    ),
)


def get_task(task_id):
    return next(task for task in TASKS if task.id == task_id)

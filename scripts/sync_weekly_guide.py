"""Generate the public guide from the shared plan in the sibling-project workspace."""

import argparse
from pathlib import Path, PurePosixPath
import re


REPOSITORY = Path(__file__).resolve().parents[1]
PROJECTS = {"aci-patch-agent", "agent-recovery-lab", "agent-edit-dpo"}
LINK = re.compile(r"(\[[^\]\n]+\]\()([^\s)]+)(\))")
NOTICE = (
    "> Publication copy of the shared six-week plan. In the sibling-project workspace,\n"
    "> edit `../WEEK_BY_WEEK.md`, then run `python3 scripts/sync_weekly_guide.py`\n"
    "> from `aci-patch-agent` to refresh this copy.\n\n"
)


def publication_link(match):
    target = match[2]
    project, separator, relative = target.partition("/")
    if separator and project in PROJECTS:
        if project == "aci-patch-agent":
            target = relative or "./"
        else:
            base = f"https://github.com/altaal/{project}"
            kind = "blob" if PurePosixPath(relative).suffix else "tree"
            target = f"{base}/{kind}/main/{relative}" if relative else base
    return match[1] + target + match[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REPOSITORY.parent / "WEEK_BY_WEEK.md")
    parser.add_argument("--check", action="store_true", help="Check the publication copy without changing it.")
    args = parser.parse_args()
    if not args.source.is_file():
        parser.error(f"Shared guide not found: {args.source}. Run from the sibling-project workspace or supply --source.")
    content = LINK.sub(publication_link, args.source.read_text())
    title, separator, body = content.partition("\n\n")
    if not separator or not title.startswith("# "):
        parser.error("The shared guide must start with a Markdown title and a blank line.")
    expected = title + separator + NOTICE + body
    destination = REPOSITORY / "WEEK_BY_WEEK.md"
    if args.check:
        if not destination.is_file() or destination.read_text() != expected:
            parser.exit(1, "Publication copy is stale. Run python3 scripts/sync_weekly_guide.py.\n")
        print("Publication copy matches the shared guide.")
    else:
        destination.write_text(expected)
        print(f"Updated {destination}")


if __name__ == "__main__":
    main()

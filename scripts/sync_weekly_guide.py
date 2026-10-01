# Copyright 2026 Ali Taalimi. Licensed under the MIT License.
"""Generate the public guide after checking an external blocked-term policy.

The default policy is publication_blocked_terms.txt beside the canonical guide.
Use --blocked-terms for another external policy. Missing or empty policies fail
without changing the public copy. Keep real policy terms out of this repository.
"""

import argparse
import pathlib
import re


REPOSITORY = pathlib.Path(__file__).resolve().parents[1]
PROJECTS = {"aci-patch-agent", "agent-recovery-lab", "agent-edit-dpo"}
LINK = re.compile(r"(\[[^\]\n]+\]\()([^\s)]+)(\))")
NOTICE = (
    "> Publication copy of the shared six-week plan. In the sibling-project "
    "workspace,\n"
    "> edit `../WEEK_BY_WEEK.md`, then run "
    "`python3 scripts/sync_weekly_guide.py`\n"
    "> from `aci-patch-agent` to refresh this copy.\n\n"
)


def _publication_link(match: re.Match[str]) -> str:
    """Convert a sibling-project link to its publication target."""
    target = match[2]
    project, separator, relative = target.partition("/")
    if separator and project in PROJECTS:
        if project == "aci-patch-agent":
            target = relative or "./"
        else:
            base = f"https://github.com/altaal/{project}"
            kind = "blob" if pathlib.PurePosixPath(relative).suffix else "tree"
            target = f"{base}/{kind}/main/{relative}" if relative else base
    return f"{match[1]}{target}{match[3]}"


def _load_blocked_terms(path: pathlib.Path) -> list[str]:
    """Read a nonempty policy stored outside the publication repository.

    Args:
        path: External UTF-8 file with one literal substring per line.

    Returns:
        Case-folded terms, excluding blank lines and comments.

    Raises:
        OSError: The policy cannot be read.
        ValueError: The policy is internal, empty, or not valid UTF-8.
    """
    if path.resolve().is_relative_to(REPOSITORY):
        raise ValueError("Keep the blocked-term policy outside the public repo")
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term.casefold())
    if not terms:
        raise ValueError("The blocked-term policy needs at least one rule")
    return terms


def _validate_content(content: str, terms: list[str]) -> None:
    """Reject blocked content without echoing private terms in diagnostics.

    Args:
        content: Text to inspect before publication.
        terms: Case-folded literal substrings from the external policy.

    Raises:
        ValueError: A line contains a blocked substring.
    """
    for number, line in enumerate(content.splitlines(), start=1):
        folded = line.casefold()
        if any(term in folded for term in terms):
            raise ValueError(
                f"Blocked content on line {number}; copy unchanged"
            )


def _render_publication(source: str) -> str:
    """Convert guide links and add a notice below the Markdown title.

    Args:
        source: The canonical guide's text.

    Returns:
        The complete publication copy.

    Raises:
        ValueError: The guide lacks a title followed by a blank line.
    """
    content = LINK.sub(_publication_link, source)
    title, separator, body = content.partition("\n\n")
    if not separator or not title.startswith("# "):
        raise ValueError("The guide needs a Markdown title and a blank line.")
    return f"{title}{separator}{NOTICE}{body}"


def _parser() -> argparse.ArgumentParser:
    """Build a parser with external source and policy defaults."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=pathlib.Path,
        default=REPOSITORY.parent / "WEEK_BY_WEEK.md",
    )
    parser.add_argument(
        "--blocked-terms",
        type=pathlib.Path,
        default=REPOSITORY.parent / "publication_blocked_terms.txt",
        help="Required external policy; missing or empty rules prevent sync.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the publication copy without changing it.",
    )
    return parser


def main() -> None:
    """Validate the guide and policy before checking or writing the public copy.

    Raises:
        SystemExit: Inputs are invalid or the publication copy is stale.
        OSError: The destination cannot be read or written.
    """
    parser = _parser()
    args = parser.parse_args()
    try:
        terms = _load_blocked_terms(args.blocked_terms)
        source = args.source.read_text(encoding="utf-8")
        _validate_content(source, terms)
        expected = _render_publication(source)
        _validate_content(expected, terms)
    except OSError:
        parser.error("Cannot read the guide or external blocked-term policy.")
    except ValueError as error:
        parser.error(str(error))
    destination = REPOSITORY / "WEEK_BY_WEEK.md"
    if args.check:
        if (
            not destination.is_file()
            or destination.read_text(encoding="utf-8") != expected
        ):
            parser.exit(
                1,
                "Publication copy is stale. "
                "Run python3 scripts/sync_weekly_guide.py.\n",
            )
        print("Publication copy matches the shared guide.")
    else:
        destination.write_text(expected, encoding="utf-8")
        print("Updated WEEK_BY_WEEK.md.")


if __name__ == "__main__":
    main()

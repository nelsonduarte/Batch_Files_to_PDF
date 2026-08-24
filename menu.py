"""Interactive menu shown when the tool is started with no arguments.

The menu does not convert anything itself: it builds the command-line arguments
the user would have typed and hands them back, so there is a single code path
for both ways of driving the tool.
"""

from __future__ import annotations

import sys
from pathlib import Path

import engines

BANNER = """
+----------------------------------------------------+
|  files_to_pdf - convert many kinds of file to PDF  |
+----------------------------------------------------+"""

OPTIONS = """
  1) Convert a folder
  2) Convert a folder and its subfolders
  3) Convert a single file
  4) Show detected engines
  5) Quit
"""


def interactive() -> bool:
    """True when there is a terminal we can prompt on."""
    return bool(sys.stdin) and sys.stdin.isatty()


def _ask(prompt: str) -> str | None:
    """Read one line. None means the user aborted (Ctrl+C / Ctrl+D)."""
    try:
        answer = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    # Explorer's "Copy as path" wraps the path in quotes.
    return answer.strip().strip('"').strip("'")


def _ask_path(prompt: str, want_dir: bool) -> str | None:
    """Ask until an existing path of the right kind is given, or the user quits."""
    while True:
        answer = _ask(prompt)
        if answer is None or answer.lower() in ("q", "quit", "exit"):
            return None
        if not answer:
            if not want_dir:
                print("  please type a file path", file=sys.stderr)
                continue
            answer = "."

        path = Path(answer).expanduser()
        if want_dir and path.is_dir():
            return str(path)
        if not want_dir and path.is_file():
            return str(path)
        kind = "folder" if want_dir else "file"
        print(f"  not an existing {kind}: {path}", file=sys.stderr)


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = _ask(prompt + suffix)
    if not answer:
        return default
    return answer[0].lower() in ("y", "s")


def run_menu() -> list[str] | None:
    """Show the menu and return extra CLI arguments, or None to quit."""
    print(BANNER)
    while True:
        print(OPTIONS)
        choice = _ask("Choose [1-5]: ")
        if choice is None or choice in ("5", "q", "quit", "exit"):
            return None

        if choice == "4":
            print("\nDetected engines:")
            print(engines.describe())
            continue

        if choice not in ("1", "2", "3"):
            print("  invalid choice", file=sys.stderr)
            continue

        want_dir = choice in ("1", "2")
        label = "Folder" if want_dir else "File"
        source = _ask_path(f"{label} to convert (Q to go back): ", want_dir)
        if source is None:
            continue

        args = [source]
        if choice == "2":
            args.append("--recursive")

        destination = _ask("Destination folder (Enter = next to the originals): ")
        if destination is None:
            continue
        if destination:
            args += ["--output", destination]

        if _ask_yes_no("Replace PDFs that already exist?"):
            args.append("--overwrite")

        print()
        return args

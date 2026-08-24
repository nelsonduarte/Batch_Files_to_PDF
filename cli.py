"""Command-line front end: argument parsing, reporting and exit codes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from converter import DEFAULT_TIMEOUT, convert
from engines import ENGINE_CHOICES, plan_jobs, resolve_engines
from jobs import build_jobs, collect_inputs
from menu import interactive, run_menu

EXAMPLES = """Examples:
  python files_to_pdf.py                                (interactive menu)
  python files_to_pdf.py document.docx
  python files_to_pdf.py document.docx -o out/report.pdf
  python files_to_pdf.py folder_with_files -o pdf_folder --recursive
  python files_to_pdf.py budget.xlsx slides.pptx page.html notes.txt
  python files_to_pdf.py photos -o album --engine image
  python files_to_pdf.py *.docx --engine libreoffice --overwrite"""


def _configure_console() -> None:
    """Avoid UnicodeEncodeError on Windows consoles with a legacy codepage.

    sys.stdout only exposes reconfigure when it is a real TextIOWrapper.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _seconds(value: str) -> int:
    """A --timeout of zero or less makes every file 'time out' before starting."""
    try:
        seconds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{value}' is not a whole number of seconds"
        ) from None
    if seconds < 1:
        raise argparse.ArgumentTypeError("must be at least 1 second")
    return seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="files_to_pdf",
        description="Convert documents, spreadsheets, presentations, web pages, "
                    "plain text, source code, e-books and images to PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXAMPLES,
    )
    parser.add_argument(
        "inputs", nargs="*",
        help="documents and/or folders; if omitted, an interactive menu is shown",
    )
    parser.add_argument(
        "-o", "--output",
        help="output .pdf file (single source) or destination folder; "
             "defaults to writing next to the original",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="walk subfolders when the input is a folder",
    )
    parser.add_argument(
        "-e", "--engine", choices=ENGINE_CHOICES, default="auto",
        help="conversion engine; 'auto' (default) routes per format, sending "
             "images to the image engine and everything Word cannot open "
             "faithfully to LibreOffice",
    )
    parser.add_argument(
        "-f", "--overwrite", action="store_true",
        help="replace PDFs that already exist",
    )
    parser.add_argument(
        "--timeout", type=_seconds, default=DEFAULT_TIMEOUT, metavar="SEC",
        help=f"time limit per file for the LibreOffice engine "
             f"(default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="show only errors and the summary",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(raw_args)

    if not args.inputs:
        if not interactive():
            print(
                "Error: pass the folder or file on the command line "
                "(without an interactive terminal the menu cannot be shown).",
                file=sys.stderr,
            )
            return 2
        extra = run_menu()
        if extra is None:
            return 0
        args = parser.parse_args(raw_args + extra)

    sources, warnings = collect_inputs(args.inputs, args.recursive)
    for message in warnings:
        print(f"[warning] {message}", file=sys.stderr)
    if not sources:
        print("No convertible file found.", file=sys.stderr)
        return 1

    try:
        jobs, skipped, warnings = build_jobs(sources, args.output, args.overwrite)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    for message in warnings:
        print(f"[warning] {message}", file=sys.stderr)
    for dst in skipped:
        print(f"[skipped] already exists: {dst}  (use --overwrite to replace)")

    if not jobs:
        print("Nothing to convert.")
        return 0

    try:
        avail = resolve_engines(args.engine)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3

    if not args.quiet:
        plan = plan_jobs(jobs, args.engine, avail)
        counts = [
            ("word", len(plan.word)),
            ("libreoffice", len(plan.libreoffice)),
            ("image", len(plan.image)),
            ("unsupported", len(plan.refused)),
        ]
        parts = [f"{name} ({n})" for name, n in counts if n]
        print(f"Engine: {', '.join(parts)} | files: {len(jobs)}")

    def report(src: Path, dst: Path, error: str | None) -> None:
        if error:
            print(f"[failed] {src.name}: {error}", file=sys.stderr)
        elif not args.quiet:
            print(f"[ok] {src.name} -> {dst}")

    try:
        results = convert(jobs, engine=args.engine, timeout_per_file=args.timeout,
                          on_result=report)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\nInterrupted by the user.", file=sys.stderr)
        return 130

    failures = [r for r in results if r[2]]
    print(f"\nDone: {len(results) - len(failures)} converted, "
          f"{len(failures)} failed, {len(skipped)} skipped.")
    return 1 if failures else 0

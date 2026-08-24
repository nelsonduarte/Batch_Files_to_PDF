"""Turning user input into (source, destination) pairs.

Everything here is silent: problems are returned as warning strings so the
caller decides how to show them.
"""

from __future__ import annotations

from pathlib import Path

from formats import is_supported

#: A unit of work: where to read from, where to write the PDF.
Job = tuple[Path, Path]

#: What a finished job reports back: the pair plus an error, or None on success.
Result = tuple[Path, Path, "str | None"]


def collect_inputs(paths: list[str], recursive: bool) -> tuple[list[Path], list[str]]:
    """Expand files and folders into a de-duplicated list of source documents.

    Returns (sources, warnings).
    """
    files: list[Path] = []
    warnings: list[str] = []

    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for found in sorted(it):
                if (
                    found.is_file()
                    and is_supported(found)
                    and not found.name.startswith("~$")  # Word lock files
                ):
                    files.append(found.resolve())
        elif p.is_file():
            files.append(p.resolve())
        else:
            warnings.append(f"path does not exist: {p}")

    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique, warnings


def build_jobs(
    sources: list[Path], output: str | None, overwrite: bool
) -> tuple[list[Job], list[Path], list[str]]:
    """Pair every source with its destination PDF.

    Returns (jobs, skipped, warnings), where skipped lists destinations that
    already exist and were left alone.
    """
    out_file: Path | None = None
    out_dir: Path | None = None

    if output:
        out_path = Path(output).expanduser()
        if out_path.suffix.lower() == ".pdf" and not out_path.is_dir():
            if len(sources) > 1:
                raise ValueError(
                    "--output points at a .pdf file but "
                    f"{len(sources)} sources were given; pass a destination folder "
                    "instead."
                )
            out_file = out_path.resolve()
        else:
            out_dir = out_path.resolve()

    jobs: list[Job] = []
    skipped: list[Path] = []
    warnings: list[str] = []
    taken: set[Path] = set()

    for src in sources:
        if out_file is not None:
            dst = out_file
        elif out_dir is not None:
            dst = out_dir / f"{src.stem}.pdf"
        else:
            dst = src.with_suffix(".pdf")

        # A source that is already a .pdf would give destination == source:
        # converting would wipe the very file we started from.
        if dst == src:
            warnings.append(f"skipped (destination equals source): {src}")
            continue

        # Sources in different folders can share a name and land on the same
        # destination; disambiguate instead of letting one overwrite the other.
        if dst in taken:
            base, counter = dst, 2
            while dst in taken:
                dst = base.with_name(f"{base.stem}_{counter}.pdf")
                counter += 1
            warnings.append(f"duplicate name: {src} -> {dst.name}")
        taken.add(dst)

        if dst.exists() and not overwrite:
            skipped.append(dst)
            continue
        jobs.append((src, dst))
    return jobs, skipped, warnings

"""LibreOffice engine: `soffice --headless --convert-to pdf`.

Cross-platform and handles every format the tool accepts.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Iterator

from jobs import Job

from . import epub

#: What a job looks like once EPUBs have been swapped for unpacked HTML:
#: (file to feed LibreOffice, destination PDF, file the user actually asked for).
Prepared = tuple[Path, Path, Path]

_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/snap/bin/libreoffice",
]


def find_soffice() -> str | None:
    """Return the path to the LibreOffice executable, or None."""
    for name in ("soffice", "soffice.exe", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    for candidate in _CANDIDATES:
        if Path(candidate).is_file():
            return candidate

    # The official .deb/.rpm packages install under /opt and do not always put
    # a plain "soffice" on PATH. (No-op on Windows: /opt simply does not exist.)
    for found_path in sorted(Path("/opt").glob("libreoffice*/program/soffice")):
        if found_path.is_file():
            return str(found_path)
    return None


#: Windows refuses a command line longer than 32767 characters, and every
#: source path is passed on it. Leave room for the fixed arguments and for the
#: quoting the OS adds around each path.
_MAX_COMMAND_LINE = 30000


def _batches(jobs: list[Prepared], fixed_length: int) -> Iterator[list[Prepared]]:
    """Group jobs into batches LibreOffice can take in a single invocation.

    Two constraints. LibreOffice always writes <stem>.pdf into --outdir, so two
    files sharing a name in different folders cannot go in the same batch. And
    the whole command line has to stay under the limit Windows imposes -- a
    recursive run over a large tree would otherwise fail with WinError 206 and
    lose the entire batch.
    """
    remaining = list(jobs)
    while remaining:
        batch: list[Prepared] = []
        leftovers: list[Prepared] = []
        seen: set[str] = set()
        length = fixed_length
        for job in remaining:
            stem = job[0].stem.lower()
            cost = len(str(job[0])) + 3  # two quotes and a separating space
            too_long = bool(batch) and length + cost > _MAX_COMMAND_LINE
            if stem in seen or too_long:
                leftovers.append(job)
            else:
                seen.add(stem)
                length += cost
                batch.append(job)
        yield batch
        remaining = leftovers


def _prepare(
    jobs: list[Job], workroot: Path, on_result: Callable[..., None]
) -> list[Prepared]:
    """Swap every EPUB for the HTML page we unpack it into.

    LibreOffice cannot read EPUB (its filter only writes it), so the book is
    stitched into one HTML file first. A book we fail to unpack is reported
    here and dropped: the rest of the run still converts.
    """
    prepared: list[Prepared] = []
    for index, (src, dst) in enumerate(jobs):
        if src.suffix.lower() != ".epub":
            prepared.append((src, dst, src))
            continue
        try:
            feed = epub.to_html(src, workroot / f"epub{index}")
        except (epub.EpubError, OSError, ValueError) as exc:
            on_result(src, dst, str(exc))
        else:
            prepared.append((feed, dst, src))
    return prepared


def convert_jobs(
    jobs: list[Job],
    on_result: Callable[..., None],
    soffice: str,
    timeout_per_file: int,
) -> None:
    """Convert every job, reporting each one through `on_result`."""
    with tempfile.TemporaryDirectory(prefix="files2pdf_") as tmp:
        tmp_path = Path(tmp)
        prepared = _prepare(jobs, tmp_path / "books", on_result)
        if not prepared:
            return
        profile = tmp_path / "profile"
        env_arg = f"-env:UserInstallation={profile.as_uri()}"
        fixed = len(soffice) + len(env_arg) + len(str(tmp_path)) + 80

        for index, batch in enumerate(_batches(prepared, fixed)):
            # A fresh folder per batch. Sharing one would let a PDF stranded by
            # an earlier batch (its move failed) be picked up as this batch's
            # output, silently writing the wrong document to the destination.
            outdir = tmp_path / f"out{index}"
            outdir.mkdir()

            cmd = [
                soffice,
                # throwaway profile: lets us convert even with LibreOffice open
                env_arg,
                "--headless",
                "--norestore",
                "--invisible",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                *[str(feed) for feed, _, _ in batch],
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_per_file * len(batch),
                )
                output = (proc.stderr or "").strip() or (proc.stdout or "").strip()
            except subprocess.TimeoutExpired:
                output = f"timed out ({timeout_per_file}s per file)"
            except OSError as exc:
                # Could not even launch soffice; the batch is lost but the
                # remaining batches still get their turn.
                output = f"could not run LibreOffice: {exc}"

            for feed, dst, original in batch:
                produced = outdir / f"{feed.stem}.pdf"
                if not produced.is_file():
                    on_result(original, dst, output or "LibreOffice produced no PDF")
                    continue
                # Write failures (destination open elsewhere, disk full,
                # permissions) are per file and must not kill the whole batch.
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists():
                        dst.unlink()
                    shutil.move(str(produced), str(dst))
                except OSError as exc:
                    on_result(original, dst, f"could not write the destination: {exc}")
                else:
                    on_result(original, dst, None)

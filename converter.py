"""The conversion entry point used by both the CLI and library callers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from engines import image, libreoffice, plan_jobs, resolve_engines, word
from jobs import Job, Result

DEFAULT_TIMEOUT = 120

__version__ = "1.1.0"


def convert(
    jobs: list[Job],
    engine: str = "auto",
    timeout_per_file: int = DEFAULT_TIMEOUT,
    on_result: Callable[[Path, Path, "str | None"], None] | None = None,
) -> list[Result]:
    """Convert a list of (source, destination) pairs.

    Each job is routed to an engine that can open its format, so one call may
    use several. Returns [(source, destination, error_or_None), ...].
    """
    results: list[Result] = []

    def collect(src: Path, dst: Path, error: str | None) -> None:
        results.append((src, dst, error))
        if on_result:
            on_result(src, dst, error)

    if not jobs:
        return results

    avail = resolve_engines(engine)
    plan = plan_jobs(jobs, engine, avail)

    if plan.word:
        word.convert_jobs(plan.word, collect)
    if plan.libreoffice and avail.soffice is not None:
        libreoffice.convert_jobs(
            plan.libreoffice, collect, avail.soffice, timeout_per_file
        )
    if plan.image:
        image.convert_jobs(plan.image, collect)
    for src, dst, reason in plan.refused:
        collect(src, dst, reason)
    return results

"""Engine detection and per-format routing.

Three engines, none of which covers everything: Word opens word-processing
documents, the image engine takes raster images, and LibreOffice handles the
rest (and can stand in for either of the other two). The choice is therefore
made per file rather than per run.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from formats import is_image, word_can_open
from jobs import Job
from . import image, libreoffice, word
from .libreoffice import find_soffice

#: A job no available engine can take, plus the reason why.
Refusal = tuple[Path, Path, str]

ENGINE_CHOICES = ("auto", "word", "libreoffice", "image")


class Availability(NamedTuple):
    """Which engines this machine can actually run."""

    word: bool
    soffice: str | None
    image: bool


class Plan(NamedTuple):
    """Every job sorted into the engine that will take it."""

    word: list[Job]
    libreoffice: list[Job]
    image: list[Job]
    refused: list[Refusal]


_PILLOW_HINT = "install Pillow (pip install Pillow) or LibreOffice"


def resolve_engines(requested: str) -> Availability:
    """Report what is usable. Raise RuntimeError if the run cannot proceed."""
    if requested == "word":
        if not word.available():
            raise RuntimeError(
                "Engine 'word' is unavailable: it needs Windows, Microsoft Word "
                "installed and the pywin32 package (pip install pywin32)."
            )
        return Availability(word=True, soffice=None, image=False)

    if requested == "image":
        if not image.available():
            raise RuntimeError(
                "Engine 'image' is unavailable: it needs the Pillow package "
                "(pip install Pillow)."
            )
        return Availability(word=False, soffice=None, image=True)

    soffice = find_soffice()
    if requested == "libreoffice":
        if soffice is None:
            raise RuntimeError(
                "Engine 'libreoffice' is unavailable: 'soffice' was not found on "
                "PATH nor in the usual install locations."
            )
        return Availability(word=False, soffice=soffice, image=False)

    has_word = word.available()
    has_image = image.available()
    if not has_word and soffice is None and not has_image:
        raise RuntimeError(
            "No conversion engine available.\n"
            "  - Windows with Word: pip install pywin32\n"
            "  - Images only: pip install Pillow\n"
            "  - Everything else: install LibreOffice "
            "(https://www.libreoffice.org/download/)"
        )
    return Availability(word=has_word, soffice=soffice, image=has_image)


def plan_jobs(jobs: list[Job], engine: str, avail: Availability) -> Plan:
    """Route each job to the engine that can actually open its format."""
    plan = Plan(word=[], libreoffice=[], image=[], refused=[])

    for src, dst in jobs:
        suffix = src.suffix.lower()

        if is_image(src):
            # Pillow first when both are around: LibreOffice would rescale the
            # image onto a Draw page instead of keeping it as it is.
            if engine == "word":
                plan.refused.append(
                    (src, dst, f"the word engine cannot open '{suffix}' files; "
                               "use --engine image or auto")
                )
            elif engine == "libreoffice":
                plan.libreoffice.append((src, dst))
            elif avail.image:
                plan.image.append((src, dst))
            elif avail.soffice:
                plan.libreoffice.append((src, dst))
            else:
                plan.refused.append((src, dst, f"'{suffix}' needs {_PILLOW_HINT}"))
            continue

        if engine == "image":
            plan.refused.append(
                (src, dst, f"the image engine only converts images, not "
                           f"'{suffix}' files; use --engine auto")
            )
            continue

        can_open = word_can_open(src)
        if engine == "word" and not can_open:
            plan.refused.append(
                (src, dst, f"the word engine cannot open '{suffix}' files; "
                           "use --engine libreoffice or auto")
            )
        elif engine == "word" or (engine == "auto" and avail.word and can_open):
            plan.word.append((src, dst))
        elif avail.soffice:
            plan.libreoffice.append((src, dst))
        else:
            plan.refused.append(
                (src, dst, f"'{suffix}' needs LibreOffice, which was not found")
            )
    return plan


def describe() -> str:
    """Human-readable summary of what is installed, for the menu."""
    lines = []
    if word.available():
        lines.append("  word        available  (text documents only)")
    else:
        lines.append("  word        missing    (needs Windows + Word + pywin32)")

    soffice = find_soffice()
    if soffice:
        lines.append(f"  libreoffice available  ({soffice})")
    else:
        lines.append("  libreoffice missing    ('soffice' not found)")

    if image.available():
        try:
            import pillow_heif  # noqa: F401
            heic = "with .heic support"
        except ImportError:
            heic = "no .heic; pip install pillow-heif"
        lines.append(f"  image       available  ({heic})")
    else:
        lines.append("  image       missing    (pip install Pillow)")
    return "\n".join(lines)


__all__ = [
    "Availability",
    "ENGINE_CHOICES",
    "Plan",
    "Refusal",
    "describe",
    "find_soffice",
    "image",
    "libreoffice",
    "plan_jobs",
    "resolve_engines",
    "word",
]

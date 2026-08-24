"""Image engine: wraps raster images into a PDF with Pillow.

LibreOffice can open images too, but it drops each one into a Draw page and
rescales it to fit that page's margins. Pillow lets the page be derived from
the image instead, so the pixels are embedded untouched -- nothing is
resampled, cropped or padded with white borders.

Optional: needs Pillow, and pillow-heif on top of it for .heic/.heif.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from jobs import Job

# A4 in inches. Each page is the image's own shape, shrunk to fit within these
# bounds, so a PDF of holiday photos still prints on ordinary paper.
_A4_SHORT_IN = 8.27
_A4_LONG_IN = 11.69

#: Formats where extra frames are pages of one document rather than animation.
#: A multi-page fax or scan arrives as TIFF; a .gif or .webp with 60 frames is
#: a moving picture, and turning it into a 60-page PDF helps nobody.
_MULTIPAGE_SUFFIXES = frozenset({".tif", ".tiff"})


def available() -> bool:
    """True when Pillow is installed."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


def _register_heif() -> None:
    """Teach Pillow about .heic/.heif when pillow-heif is present."""
    try:
        import pillow_heif
    except ImportError:
        return
    try:
        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001 - a broken optional plugin must not stop us
        pass


def _flatten(frame):
    """Return an RGB copy, compositing transparency onto white.

    PDF has no alpha channel here, and Pillow refuses to save RGBA as PDF.
    Pasting onto white keeps a transparent PNG looking like it does on a page
    instead of turning its background black.
    """
    from PIL import Image

    if frame.mode in ("RGBA", "LA") or (
        frame.mode == "P" and "transparency" in frame.info
    ):
        rgba = frame.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    if frame.mode != "RGB":
        return frame.convert("RGB")
    return frame


def _resolution(width: int, height: int) -> float:
    """Pick the DPI that makes this image fill a page no larger than A4.

    Pillow derives the page size from pixels / resolution, so choosing the
    resolution is how the page gets sized without touching the pixels. The
    page takes the image's orientation: a landscape photo lands on a
    landscape page rather than being letterboxed onto a portrait one.
    """
    if width >= height:
        page_w, page_h = _A4_LONG_IN, _A4_SHORT_IN
    else:
        page_w, page_h = _A4_SHORT_IN, _A4_LONG_IN
    # The larger of the two ratios is the binding one: it keeps the page within
    # A4 on both axes. Guard against a zero-sized axis in a corrupt file.
    return max(width / page_w, height / page_h, 1.0)


def _pages(image, suffix: str) -> list:
    """The frames that should become pages, already flattened to RGB."""
    from PIL import ImageOps, ImageSequence

    if suffix in _MULTIPAGE_SUFFIXES and getattr(image, "n_frames", 1) > 1:
        return [
            _flatten(ImageOps.exif_transpose(frame))
            for frame in ImageSequence.Iterator(image)
        ]
    # exif_transpose honours the orientation tag phones write, so a portrait
    # photo does not come out on its side.
    return [_flatten(ImageOps.exif_transpose(image))]


def convert_jobs(jobs: list[Job], on_result: Callable[..., None]) -> None:
    """Convert every job, reporting each one through `on_result`."""
    from PIL import Image

    _register_heif()

    for src, dst in jobs:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as image:
                pages = _pages(image, src.suffix.lower())
                if not pages:
                    on_result(src, dst, "the image has no frames to convert")
                    continue
                first, rest = pages[0], pages[1:]
                first.save(
                    dst,
                    format="PDF",
                    resolution=_resolution(*first.size),
                    save_all=bool(rest),
                    append_images=rest,
                )
        # Pillow raises UnidentifiedImageError for a file whose bytes are not
        # an image it knows, OSError for a truncated one, and ValueError for a
        # corrupt header. Each is one file's problem, not the run's.
        except Exception as exc:  # noqa: BLE001 - reported per file
            on_result(src, dst, str(exc))
        else:
            on_result(src, dst, None)

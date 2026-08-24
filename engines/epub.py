"""EPUB support: unpack the book into one HTML file LibreOffice can open.

LibreOffice ships an EPUB filter, but its flags read "EXPORT ALIEN": it writes
EPUB and cannot read it. An EPUB is only a zip of XHTML chapters with a
manifest naming their order, so unpacking it here and handing LibreOffice a
single stitched-together HTML page costs far less than the alternative and
keeps text, styling and images intact.

Nothing outside this module needs to know: the LibreOffice engine calls
`to_html` and converts the result as if the user had passed an .html file.
"""

from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_CONTAINER = "META-INF/container.xml"

#: URLs that are already absolute, or are not file references at all.
_ABSOLUTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|/|#)", re.I)

#: src="..." / href="..." in a chapter, so relative paths can be rebased.
_URL_ATTR = re.compile(r"""\b(src|href)\s*=\s*(["'])(.*?)\2""", re.I | re.S)

_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
_HEAD_LINKS = re.compile(
    r"<link\b[^>]*\brel\s*=\s*[\"']?stylesheet[\"']?[^>]*>|<style\b[^>]*>.*?</style>",
    re.I | re.S,
)


class EpubError(Exception):
    """The file is not an EPUB we can read."""


def _tag(element: ET.Element) -> str:
    """Local tag name, with the XML namespace stripped off."""
    return element.tag.rsplit("}", 1)[-1].lower()


def _find(root: ET.Element, name: str) -> "ET.Element | None":
    for element in root.iter():
        if _tag(element) == name:
            return element
    return None


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    """Extract, refusing members that would escape the destination folder.

    An archive can name a member "../../evil"; zipfile happily writes it. We
    open files the user did not create, so this has to be checked.
    """
    dest = dest.resolve()
    for member in archive.infolist():
        if member.is_dir():
            continue
        target = (dest / member.filename).resolve()
        if target == dest or dest not in target.parents:
            raise EpubError(f"refusing to unpack '{member.filename}' (path escapes)")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, open(target, "wb") as handle:
            handle.write(source.read())


def _opf_path(root: Path) -> str:
    """Where the manifest lives, per META-INF/container.xml."""
    container = root / _CONTAINER
    if not container.is_file():
        raise EpubError("not an EPUB: META-INF/container.xml is missing")
    rootfile = _find(ET.parse(container).getroot(), "rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        raise EpubError("not an EPUB: container.xml names no rootfile")
    return rootfile.get("full-path", "")


def _spine(root: Path, opf: str) -> tuple[str, list[str]]:
    """Return (title, chapter paths in reading order), relative to the root."""
    tree = ET.parse(root / opf)
    base = posixpath.dirname(opf)

    hrefs: dict[str, str] = {}
    for element in tree.getroot().iter():
        if _tag(element) == "item" and element.get("id") and element.get("href"):
            hrefs[element.get("id", "")] = posixpath.normpath(
                posixpath.join(base, element.get("href", ""))
            )

    chapters: list[str] = []
    for element in tree.getroot().iter():
        if _tag(element) == "itemref":
            href = hrefs.get(element.get("idref", ""))
            if href and (root / href).is_file():
                chapters.append(href)

    if not chapters:
        raise EpubError("the EPUB spine lists no readable chapter")

    title_element = _find(tree.getroot(), "title")
    title = (title_element.text or "").strip() if title_element is not None else ""
    return title, chapters


def _rebase(markup: str, chapter_dir: str) -> str:
    """Rewrite relative URLs so they resolve from the book root.

    Chapters can sit in OEBPS/text/ while their images sit in OEBPS/images/.
    The stitched page lives at the root, so every relative path in it has to be
    rewritten or the images silently vanish from the PDF.
    """
    if not chapter_dir:
        return markup

    def fix(match: "re.Match[str]") -> str:
        attr, quote, url = match.group(1), match.group(2), match.group(3)
        if not url or _ABSOLUTE.match(url):
            return match.group(0)
        rebased = posixpath.normpath(posixpath.join(chapter_dir, url))
        return f'{attr}={quote}{rebased}{quote}'

    return _URL_ATTR.sub(fix, markup)


def to_html(src: Path, workdir: Path) -> Path:
    """Unpack `src` into `workdir` and return the stitched HTML file.

    The HTML keeps the book's stem, so the PDF LibreOffice writes is named
    after the book rather than after a temporary file.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as archive:
            _safe_extract(archive, workdir)
    except zipfile.BadZipFile as exc:
        raise EpubError(f"not a readable EPUB archive: {exc}") from exc

    try:
        title, chapters = _spine(workdir, _opf_path(workdir))
    except ET.ParseError as exc:
        raise EpubError(f"the EPUB manifest is not valid XML: {exc}") from exc

    styles: list[str] = []
    bodies: list[str] = []
    for index, chapter in enumerate(chapters):
        markup = (workdir / chapter).read_text(encoding="utf-8", errors="replace")
        chapter_dir = posixpath.dirname(chapter)

        for style in _HEAD_LINKS.findall(markup):
            rebased = _rebase(style, chapter_dir)
            if rebased not in styles:
                styles.append(rebased)

        found = _BODY.search(markup)
        # A chapter with no <body> is usually a fragment; keeping it whole
        # loses nothing and keeps the text in the book.
        body = found.group(1) if found else markup
        # Each chapter starts on its own page, the way the book reads.
        separator = '<div style="page-break-before: always"></div>' if index else ""
        bodies.append(separator + _rebase(body, chapter_dir))

    heading = f"<title>{title}</title>" if title else ""
    page = (
        '<!DOCTYPE html>\n<html><head><meta charset="utf-8">'
        f'{heading}{"".join(styles)}</head><body>\n'
        f'{chr(10).join(bodies)}\n</body></html>\n'
    )

    out = workdir / f"{src.stem}.html"
    out.write_text(page, encoding="utf-8")
    return out

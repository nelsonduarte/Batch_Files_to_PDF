"""Accepted file extensions, grouped by the kind of file they hold.

The grouping is not cosmetic. Two of these sets drive engine routing:
WORD_SUFFIXES is exactly what Microsoft Word opens faithfully, and
IMAGE_SUFFIXES is what the Pillow-based image engine takes. Everything else
goes to LibreOffice.
"""

from __future__ import annotations

from pathlib import Path

# Word-processing formats Microsoft Word opens *faithfully*. This set is what
# drives engine routing, so nothing belongs here that Word merely accepts.
WORD_SUFFIXES = frozenset({
    ".docx", ".doc", ".docm", ".rtf", ".odt",
    ".dotx", ".dot", ".dotm", ".ott",          # templates
})

# Word-processing formats that must go to LibreOffice. Word opens both of these
# and renders neither: it treats them as plain text and prints the markup. A
# 13-page .fodt manual came out of Word as 32 pages of tags, and a .md file came
# out as its literal "#", "**" and pipe-table source. LibreOffice has real import
# filters for both.
TEXT_ONLY_SUFFIXES = frozenset({".fodt", ".md", ".markdown"})

TEXT_SUFFIXES = WORD_SUFFIXES | TEXT_ONLY_SUFFIXES

# Spreadsheets and presentations: LibreOffice only.
SHEET_SUFFIXES = frozenset({
    ".xlsx", ".xlsm", ".xls", ".xlsb", ".ods", ".fods", ".csv",
    ".xltx", ".xlt", ".xltm", ".ots",          # templates
})
SLIDE_SUFFIXES = frozenset({
    ".pptx", ".pptm", ".ppt", ".odp", ".fodp",
    ".ppsx", ".pps",                           # slideshows
    ".potx", ".pot", ".potm", ".otp",          # templates
})

# Web pages. LibreOffice routes these through its Writer/Web filter, which lays
# out the markup instead of printing it. Word also opens .html, but it is not in
# WORD_SUFFIXES because it rewrites the document as it imports.
WEB_SUFFIXES = frozenset({".html", ".htm", ".xhtml", ".mhtml", ".mht"})

# Plain text and source code. LibreOffice has no filter for these extensions,
# but it falls back to its plain-text import, which is precisely what they need:
# the file is typeset verbatim, one line per line. No syntax highlighting --
# for that a real pretty-printer would have to sit in front of the engine.
# (.csv is deliberately absent: it belongs to SHEET_SUFFIXES, where LibreOffice
# opens it as a spreadsheet with columns rather than as one long line.)
PLAINTEXT_SUFFIXES = frozenset({
    ".txt", ".log", ".text",
    ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".scala", ".pl", ".lua", ".r",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".m", ".mm",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".sql", ".css", ".scss", ".less",
})

# E-books. .fb2 has a real LibreOffice import filter; .epub does not (the
# EPUB filter is export-only), so engines/epub.py unpacks the book into HTML
# first and LibreOffice converts that.
EBOOK_SUFFIXES = frozenset({".epub", ".fb2"})

# Raster images, handled by the image engine (Pillow). Vector formats are not
# here: .svg goes to LibreOffice Draw, which renders it properly.
IMAGE_SUFFIXES = frozenset({
    ".jpg", ".jpeg", ".jpe", ".png", ".gif", ".bmp", ".dib",
    ".tif", ".tiff", ".webp", ".ico",
    ".heic", ".heif",                          # need pillow-heif installed
})

# Vector drawings LibreOffice Draw opens.
VECTOR_SUFFIXES = frozenset({".svg", ".odg", ".fodg", ".otg", ".wmf", ".emf"})

SUPPORTED_SUFFIXES = (
    TEXT_SUFFIXES
    | SHEET_SUFFIXES
    | SLIDE_SUFFIXES
    | WEB_SUFFIXES
    | PLAINTEXT_SUFFIXES
    | EBOOK_SUFFIXES
    | IMAGE_SUFFIXES
    | VECTOR_SUFFIXES
)


def is_supported(path: Path) -> bool:
    """True when the extension is one we know how to convert."""
    return path.suffix.lower() in SUPPORTED_SUFFIXES


def word_can_open(path: Path) -> bool:
    """True when Microsoft Word is able to open this format at all."""
    return path.suffix.lower() in WORD_SUFFIXES


def is_image(path: Path) -> bool:
    """True when this is a raster image the image engine can wrap into a PDF."""
    return path.suffix.lower() in IMAGE_SUFFIXES

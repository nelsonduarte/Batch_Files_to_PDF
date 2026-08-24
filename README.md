# files_to_pdf

Convert files to PDF from the command line — one file, a whole folder, or a folder
tree. Documents, spreadsheets, presentations, web pages, plain text, source code,
e-books, images and vector drawings. Run it with no arguments and it shows an
interactive menu.

The tool drives a real office suite instead of re-implementing the layout engine,
so the output keeps the original pagination, fonts, headers and footers.

| Kind | Extensions |
| --- | --- |
| Text documents | `.docx` `.doc` `.docm` `.rtf` `.odt` `.fodt` |
| Text templates | `.dotx` `.dot` `.dotm` `.ott` |
| Markdown | `.md` `.markdown` |
| Spreadsheets | `.xlsx` `.xlsm` `.xls` `.xlsb` `.ods` `.fods` `.csv` |
| Spreadsheet templates | `.xltx` `.xlt` `.xltm` `.ots` |
| Presentations | `.pptx` `.pptm` `.ppt` `.odp` `.fodp` |
| Slideshows | `.ppsx` `.pps` |
| Presentation templates | `.potx` `.pot` `.potm` `.otp` |
| Web pages | `.html` `.htm` `.xhtml` `.mhtml` `.mht` |
| Plain text | `.txt` `.log` `.text` |
| Data and config | `.json` `.xml` `.yaml` `.yml` `.toml` `.ini` `.cfg` `.conf` |
| Source code | `.py` `.js` `.ts` `.jsx` `.tsx` `.java` `.cs` `.go` `.rs` `.rb` `.php` `.swift` `.kt` `.scala` `.pl` `.lua` `.r` `.c` `.h` `.cpp` `.hpp` `.cc` `.m` `.mm` `.sh` `.bash` `.zsh` `.ps1` `.bat` `.cmd` `.sql` `.css` `.scss` `.less` |
| E-books | `.epub` `.fb2` |
| Images | `.jpg` `.jpeg` `.jpe` `.png` `.gif` `.bmp` `.dib` `.tif` `.tiff` `.webp` `.ico` `.heic` `.heif` |
| Vector drawings | `.svg` `.odg` `.fodg` `.otg` `.wmf` `.emf` |

Word lock files (`~$name.docx`) are ignored.

> **A folder scan sweeps up a lot.** Because source code, text and images are all
> accepted, pointing `--recursive` at a project directory will convert every
> `.py`, `.json`, `.log`, `.md` and screenshot it finds — hundreds of PDFs from
> one command. Aim it at a folder of things you actually want converted, or pass
> the files explicitly. See [Narrowing the format list](#narrowing-the-format-list).

## Layout

Flat: every module sits at the top level, and `files_to_pdf.py` puts that folder
on `sys.path` before importing from it.

```
files_to_pdf.py           launcher and entry point
cli.py                    argument parsing, reporting, exit codes
menu.py                   the interactive menu
converter.py              convert(): runs a batch across the engines
jobs.py                   source/destination pairing (silent, returns warnings)
formats.py                accepted extensions, grouped by kind
engines/
    __init__.py           detection and per-format routing
    word.py               Microsoft Word over COM
    libreoffice.py        soffice --headless
    image.py              Pillow
    epub.py               unpacks a book into HTML for LibreOffice
requirements.txt
```

## Engines

| Engine | Handles | Requirements | Notes |
| --- | --- | --- | --- |
| `word` | Text documents only | Windows + Microsoft Word installed + `pywin32` | Highest fidelity; turns Word headings into PDF bookmarks |
| `libreoffice` | Everything except images | LibreOffice installed (`soffice` on PATH or in a standard location) | Cross-platform, no Word needed |
| `image` | Raster images only | `Pillow` (plus `pillow-heif` for `.heic`) | Embeds the pixels untouched; no resampling |

None of them covers everything, which is why the engine is chosen per file.

### Routing

`--engine auto` (the default) decides **per file**, not per run:

- **Images** go to the image engine when Pillow is installed, and fall back to
  LibreOffice when it is not.
- **Text documents and their templates** go to Word when it is available.
- **Everything else** goes to LibreOffice.

Two text formats are deliberately kept away from Word: `.fodt` and `.md`. Word
opens both and renders neither — it treats them as plain text and prints the
markup — so they are routed to LibreOffice even when Word is available. `.html` is
kept away for a related reason: Word rewrites the document as it imports, while
LibreOffice's Writer/Web filter lays it out.

A single run can therefore use all three engines, and says so:

```
Engine: word (1), libreoffice (9), image (9) | files: 19
```

On Linux and macOS the Word engine is never selected, so `auto` there means
LibreOffice plus the image engine.

Forcing an engine on a file it cannot open does not abort the run — that file is
reported as failed and the rest still convert:

```
[failed] budget.xlsx: the word engine cannot open '.xlsx' files; use --engine libreoffice or auto
[failed] script.py: the image engine only converts images, not '.py' files; use --engine auto
```

The same happens in reverse: with Word installed but no LibreOffice, your `.docx`
files convert and the spreadsheets report `needs LibreOffice, which was not found`.

`soffice` is looked up on PATH, then in the usual install locations, including
`/usr/bin`, `/snap/bin` and `/opt/libreoffice*/program/`. A Flatpak-only install
is **not** detected — put the wrapper on PATH or install the distro package.

### How images are laid out

The image engine sizes the page from the image rather than the other way round:
the PDF page takes the image's own shape and orientation, shrunk to fit within
A4. The pixels are embedded as they are — nothing is resampled, cropped, or
padded with white margins.

- Orientation tags written by phones are honoured, so a portrait photo does not
  come out on its side.
- Transparency is composited onto white, not onto black.
- A multi-page `.tif` becomes a multi-page PDF, one page per frame — that is what
  scanners and fax tools produce. An animated `.gif` or `.webp` does **not**: only
  its first frame is used, because a 60-frame animation is not a 60-page document.

Forcing `--engine libreoffice` on an image also works, but LibreOffice drops it
onto a Draw page and rescales it to that page's margins.

### E-books

`.fb2` has a real LibreOffice import filter. `.epub` does not — LibreOffice's
EPUB filter is *export-only* (its flags read `EXPORT ALIEN`), so it can write the
format but not read it.

Since an EPUB is only a zip of XHTML chapters plus a manifest naming their order,
`engines/epub.py` unpacks the book, stitches the chapters into a single HTML page
in spine order with a page break between each, and hands that to LibreOffice.
Stylesheets are carried over and relative links to images are rewritten so they
still resolve. Archive members whose paths would escape the extraction folder are
refused.

## Install

No mandatory Python dependencies — just Python 3.10+ and an office suite to drive.

```bash
python -m pip install -r requirements.txt
```

Every entry in `requirements.txt` is optional, and each unlocks one engine:

| Package | Unlocks | Without it |
| --- | --- | --- |
| `pywin32` (Windows only) | the Word engine | Text documents go to LibreOffice |
| `Pillow` | the image engine | Images go to LibreOffice, rescaled onto a Draw page |
| `pillow-heif` | `.heic`/`.heif` in the image engine | iPhone photos are reported as failed |

`pywin32` is guarded by a `sys_platform == "win32"` marker, so on Linux and macOS
it resolves to nothing and pip reports that it is ignoring the package because the
marker does not match the environment.

Use `python -m pip` rather than a bare `pip`, and run it with the **same**
interpreter you use for the tool — installing into a different Python is the most
common reason an engine goes missing.

On a Debian/Ubuntu system Python, pip fails with
`error: externally-managed-environment` (PEP 668) — that is pip protecting the
system, not a problem with this project. Use a virtual environment:

```bash
python3 -m venv venv && ./venv/bin/python -m pip install -r requirements.txt
```

LibreOffice is a system dependency and is not installable from PyPI:

```bash
sudo apt install libreoffice          # Debian/Ubuntu
sudo dnf install libreoffice          # Fedora
winget install TheDocumentFoundation.LibreOffice   # Windows
```

## Usage

```bash
# Interactive menu
python files_to_pdf.py

# A single file, PDF written next to the original
python files_to_pdf.py document.docx

# A single file with an explicit output name
python files_to_pdf.py document.docx -o out/report.pdf

# A whole folder tree into a separate output folder
python files_to_pdf.py folder_with_files -o pdf_folder --recursive

# Mixed formats in one run — routed to the right engine automatically
python files_to_pdf.py report.docx budget.xlsx page.html notes.txt -o pdf_folder

# A folder of photos
python files_to_pdf.py photos -o album --engine image

# Force an engine and replace existing PDFs
python files_to_pdf.py *.docx --engine libreoffice --overwrite
```

### The menu

Started with no arguments:

```
+----------------------------------------------------+
|  files_to_pdf - convert many kinds of file to PDF  |
+----------------------------------------------------+

  1) Convert a folder
  2) Convert a folder and its subfolders
  3) Convert a single file
  4) Show detected engines
  5) Quit

Choose [1-5]:
```

It then asks for the path, the destination folder (Enter keeps the PDFs next to
the originals) and whether to replace existing PDFs. Paths are re-asked until they
exist, and the quotes Windows Explorer's *Copy as path* adds are stripped.

The menu converts nothing itself — it builds the same arguments you would have
typed and hands them to the CLI, so there is one code path for both.

Option 4 reports what is installed:

```
  word        available  (text documents only)
  libreoffice available  (C:\Program Files\LibreOffice\program\soffice.exe)
  image       available  (with .heic support)
```

## Options

| Option | Meaning |
| --- | --- |
| `inputs` | Files and/or folders; if omitted, the menu is shown |
| `-o`, `--output` | Output `.pdf` file (single source) or destination folder. Default: next to the original |
| `-r`, `--recursive` | Walk subfolders when the input is a folder |
| `-e`, `--engine` | `auto` (default, routes per format), `word`, `libreoffice`, or `image` |
| `-f`, `--overwrite` | Replace PDFs that already exist |
| `--timeout SEC` | Time limit per file for the LibreOffice engine (default: 120) |
| `-q`, `--quiet` | Show only errors and the summary |

### Narrowing the format list

The accepted extensions are plain `frozenset`s in `formats.py`, grouped by kind.
Delete a group, or individual extensions from one, and folder scans stop picking
those files up. `PLAINTEXT_SUFFIXES` is the widest by far — dropping it takes the
tool back to documents, web pages, e-books and images.

Adding is the same move in reverse: LibreOffice ships around 180 import filters,
so `.vsdx` (Visio) and `.pub` (Publisher) work if you add them.

Two rules when editing these sets:

- Only `WORD_SUFFIXES` and `IMAGE_SUFFIXES` affect routing; everything else
  automatically goes to LibreOffice. Put a format in `WORD_SUFFIXES` only if Word
  renders it *faithfully* — Word accepts more than it renders correctly, which is
  what `TEXT_ONLY_SUFFIXES` is for.
- Extensions LibreOffice has no filter for still convert: it falls back to its
  plain-text import and typesets the file verbatim, one line per line. That is
  exactly right for source code — but it means there is no syntax highlighting,
  and a format that only *looks* textual will come out as its raw markup.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Everything converted, there was nothing to do, or the menu was quit |
| `1` | No convertible file found, or at least one file failed |
| `2` | Bad arguments, or no terminal for the menu |
| `3` | No conversion engine available |
| `130` | Interrupted with Ctrl+C |

## Safeguards

- **Never overwrites a source.** A `.pdf` input would otherwise map onto itself;
  such a job is refused rather than destroying the original.
- **Name collisions are disambiguated.** Two `report.docx` in different
  subfolders become `report.pdf` and `report_2.pdf` instead of one silently
  replacing the other. This now matters far more often than it used to: `a.py`
  and `a.txt` in the same folder collide too.
- **One bad file does not stop the batch.** Conversion and write errors (a PDF open
  in a viewer, permissions, a full disk, a truncated image, an unreadable e-book)
  are reported per file; the remaining files still convert.
- **Existing PDFs are kept** unless `--overwrite` is given.
- **Your open Word is left alone.** The Word engine starts a dedicated, invisible
  instance and quits it at the end. The LibreOffice engine uses a throwaway user
  profile, so it works even while LibreOffice is running.
- **Archives are unpacked defensively.** An `.epub` naming a member outside the
  extraction folder is refused instead of writing there.

## Use as a library

The modules import each other by plain name, so put the project folder on
`sys.path` first:

```python
import sys
from pathlib import Path

sys.path.insert(0, "/path/to/Batch_Files_to_PDF")

from converter import convert

results = convert([(Path("a.docx"), Path("a.pdf"))], engine="auto")
for src, dst, error in results:
    print(src.name, "->", dst if error is None else f"FAILED: {error}")
```

`convert()` returns a list of `(source, destination, error_or_None)` and accepts an
`on_result` callback for progress reporting. Also available: `collect_inputs` and
`build_jobs` from `jobs`, `resolve_engines` and `plan_jobs` from `engines`, and the
suffix sets from `formats`.

`collect_inputs` and `build_jobs` print nothing — they return warnings as strings
for the caller to display.

## Troubleshooting

**`Engine 'word' is unavailable`** — `pywin32` is missing from the interpreter you
are running. Check with:

```bash
python -c "import win32com.client; print('ok')"
```

If that fails but the package is installed, you have more than one Python and it
went into the other one. Reinstall with the interpreter you actually run:

```bash
path\to\the\python.exe -m pip install -r requirements.txt
```

**`Engine 'image' is unavailable`** — install Pillow into that same interpreter:
`python -m pip install Pillow`.

**A `.heic` photo fails while other images convert** — Pillow does not read HEIC
on its own. Run `python -m pip install pillow-heif`; menu option 4 then reports
`image available (with .heic support)`.

**Pylance warns that `win32com.client` could not be resolved from source** —
harmless, and confined to `engines/word.py`. It means the type stubs were found but
the package is not installed in the interpreter VS Code has selected. Point VS Code
at the interpreter that has `pywin32`.

**LibreOffice produces no PDF** — check that the document is not password
protected, and raise `--timeout` for very large files.

**A whole source tree turned into PDFs** — that is `--recursive` meeting the wide
format list. See [Narrowing the format list](#narrowing-the-format-list).

**An `.xlsb` sheet comes out portrait when it should be landscape** — a
limitation of LibreOffice's `.xlsb` import filter, which does not read per-sheet
page setup as completely as the `.xlsx` one. The same workbook saved both ways
gave 80 pages either way, but the one landscape sheet stayed landscape only from
the `.xlsx`; from the `.xlsb` it came out portrait with the wide content
clipped. Prefer the `.xlsx` when you have both. There is no engine to fall back
on: Word cannot open spreadsheets at all.

## Verified on

**Windows 11** — Python 3.10, Microsoft Word, LibreOffice 26.2, Pillow 12.3 and
pillow-heif 1.5.

**The wide format run** — a 20-file folder covering every group in the table
above converted 18 of the 19 accepted files in one command, reporting
`Engine: word (1), libreoffice (9), image (9)`. The nineteenth was a deliberately
corrupted `.png`, reported per file while the rest converted; the twentieth file
was a `.zip`, correctly ignored as unsupported. Every output PDF was reopened and
checked: page counts, page sizes, and extracted text where the source had text
(`.txt`, `.py`, `.json`, `.log`, `.html`, `.md`, `.csv`, `.rtf`, `.epub`).

**Images** — page geometry checked against A4 for landscape, portrait, square and
extreme aspect ratios; EXIF orientation 6 confirmed to rotate a 400×200 source to
a 200×400 page; transparency confirmed to composite onto white; a 3-frame `.tiff`
produced 3 pages while a 3-frame animated `.gif` produced 1.

**E-books** — a book with chapters in `OEBPS/text/`, its stylesheet in
`OEBPS/css/` and its image in `OEBPS/images/` was unpacked with spine order, page
breaks, rewritten relative paths and an untouched absolute URL; the resulting PDF
carried the chapter text. A zip-slip archive and a zip that is not an EPUB were
both refused with a clear message.

**Engine selection** — `--engine word` on a `.jpg`, `--engine image` on a `.py`,
`--engine libreoffice` on a `.png` and `--engine word` on a `.rtf` all behaved as
documented.

The entries below predate the flat layout and the wider format list. They were
verified against the same conversion core, which is unchanged.

**Documents** — on a real 21-page technical manual both engines produced 21 pages
and 24 PDF bookmarks with identical text and accented characters. A folder scan of
twelve template, slideshow and flat-ODF files picked up all twelve and no PDF
differed from its source in page count. A genuine `.xlsb` (48 binary parts, not a
renamed `.xlsx`) matched its `.xlsx` twin at 80 pages, with the page-setup caveat
noted under Troubleshooting. `.potm` is the one accepted extension never
converted from a real sample: LibreOffice cannot export it, so none could be
produced, and it is accepted by parity with `.pptm`.

**Markdown** — a file exercising headings, bold, italic, inline code, nested and
numbered lists, a table, a blockquote, a fenced code block, a link and a
horizontal rule rendered with all of them styled. The same file through Word came
out as its literal `#`, `**` and pipe-table source, which is why `.md` is in
`TEXT_ONLY_SUFFIXES`.

**The menu** — driven through a simulated terminal: engine listing, invalid choice,
non-existent path, quoted path, Enter-for-default destination, single-file mode,
and a full run ending in four PDFs.

**Linux** — Ubuntu and Debian (WSL2), Python 3.13 and 3.14, LibreOffice from
`/usr/bin/soffice`. The `#!` shebang, recursive batches, duplicate-name
disambiguation, case-sensitive names (`Report.docx` and `report.docx` side by
side), `~` expansion and the non-interactive fallbacks all behaved as on Windows.

**macOS** — the `soffice` lookup path is implemented but has not been exercised.

"""Tests for the parts that run without an office suite.

CI runners have no Microsoft Word and no LibreOffice, so the engines that drive
them cannot be exercised here. Everything else can: format classification,
routing, source/destination pairing, the Pillow image engine and the EPUB
unpacker. Those are also the parts most likely to break silently.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import formats
from engines import Availability, plan_jobs
from engines import epub as epub_engine
from jobs import build_jobs, collect_inputs

ALL = Availability(word=True, soffice="/usr/bin/soffice", image=True)
NO_WORD = Availability(word=False, soffice="/usr/bin/soffice", image=True)
NO_PILLOW = Availability(word=False, soffice="/usr/bin/soffice", image=False)
ONLY_IMAGE = Availability(word=False, soffice=None, image=True)


def job(name: str) -> tuple[Path, Path]:
    return (Path("/src") / name, Path("/out") / f"{Path(name).stem}.pdf")


class TestFormats(unittest.TestCase):
    def test_every_group_is_accepted(self):
        for suffix in (".docx", ".xlsx", ".pptx", ".html", ".txt", ".py",
                       ".json", ".epub", ".fb2", ".png", ".heic", ".svg", ".md"):
            with self.subTest(suffix=suffix):
                self.assertTrue(formats.is_supported(Path("x" + suffix)))

    def test_unknown_and_pdf_are_not_accepted(self):
        # .pdf must stay out: a PDF source would map onto itself as destination.
        for suffix in (".pdf", ".zip", ".exe", ".mp4", ""):
            with self.subTest(suffix=suffix):
                self.assertFalse(formats.is_supported(Path("x" + suffix)))

    def test_extension_matching_ignores_case(self):
        self.assertTrue(formats.is_supported(Path("REPORT.DOCX")))
        self.assertTrue(formats.is_image(Path("PHOTO.JPG")))

    def test_word_claims_only_what_it_renders(self):
        self.assertTrue(formats.word_can_open(Path("a.docx")))
        # Word opens these and prints their markup instead of rendering it.
        for suffix in (".md", ".fodt", ".html", ".txt"):
            with self.subTest(suffix=suffix):
                self.assertFalse(formats.word_can_open(Path("a" + suffix)))

    def test_groups_do_not_overlap(self):
        # .csv belongs to spreadsheets, not plain text: LibreOffice must open it
        # as a sheet with columns rather than as one long line.
        self.assertIn(".csv", formats.SHEET_SUFFIXES)
        self.assertNotIn(".csv", formats.PLAINTEXT_SUFFIXES)
        self.assertFalse(formats.IMAGE_SUFFIXES & formats.PLAINTEXT_SUFFIXES)
        self.assertFalse(formats.WORD_SUFFIXES & formats.TEXT_ONLY_SUFFIXES)


class TestRouting(unittest.TestCase):
    def test_auto_sends_each_kind_to_its_engine(self):
        plan = plan_jobs([job("a.docx"), job("b.xlsx"), job("c.png")], "auto", ALL)
        self.assertEqual([j[0].name for j in plan.word], ["a.docx"])
        self.assertEqual([j[0].name for j in plan.libreoffice], ["b.xlsx"])
        self.assertEqual([j[0].name for j in plan.image], ["c.png"])
        self.assertFalse(plan.refused)

    def test_without_word_documents_fall_back_to_libreoffice(self):
        plan = plan_jobs([job("a.docx")], "auto", NO_WORD)
        self.assertEqual(len(plan.libreoffice), 1)
        self.assertFalse(plan.word)

    def test_without_pillow_images_fall_back_to_libreoffice(self):
        plan = plan_jobs([job("c.png")], "auto", NO_PILLOW)
        self.assertEqual(len(plan.libreoffice), 1)
        self.assertFalse(plan.image)

    def test_markdown_avoids_word_even_when_word_is_there(self):
        plan = plan_jobs([job("readme.md"), job("flat.fodt")], "auto", ALL)
        self.assertFalse(plan.word)
        self.assertEqual(len(plan.libreoffice), 2)

    def test_forcing_an_engine_refuses_only_the_files_it_cannot_open(self):
        plan = plan_jobs([job("a.docx"), job("b.xlsx")], "word", ALL)
        self.assertEqual([j[0].name for j in plan.word], ["a.docx"])
        self.assertEqual(len(plan.refused), 1)
        self.assertIn("cannot open '.xlsx'", plan.refused[0][2])

    def test_image_engine_refuses_documents(self):
        plan = plan_jobs([job("a.py")], "image", ONLY_IMAGE)
        self.assertEqual(len(plan.refused), 1)
        self.assertIn("only converts images", plan.refused[0][2])

    def test_nothing_is_ever_silently_dropped(self):
        jobs = [job(n) for n in ("a.docx", "b.xlsx", "c.png", "d.py", "e.epub")]
        for engine, avail in (("auto", ALL), ("word", ALL),
                              ("libreoffice", NO_WORD), ("image", ONLY_IMAGE)):
            with self.subTest(engine=engine):
                plan = plan_jobs(jobs, engine, avail)
                total = len(plan.word) + len(plan.libreoffice) + len(plan.image)
                self.assertEqual(total + len(plan.refused), len(jobs))


class TestJobs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_same_stem_different_types_get_distinct_destinations(self):
        # The wide format list makes this collision ordinary rather than rare.
        names = ["r.txt", "r.py", "r.json", "r.png"]
        sources = []
        for name in names:
            path = self.tmp / name
            path.write_text("x", encoding="utf-8")
            sources.append(path)
        jobs, _, warnings = build_jobs(sources, str(self.tmp / "out"), False)
        destinations = {dst for _, dst in jobs}
        self.assertEqual(len(destinations), len(names))
        self.assertEqual(len(warnings), len(names) - 1)

    def test_a_source_is_never_its_own_destination(self):
        source = self.tmp / "already.pdf"
        source.write_bytes(b"%PDF-1.4")
        jobs, _, warnings = build_jobs([source], None, True)
        self.assertFalse(jobs)
        self.assertTrue(any("destination equals source" in w for w in warnings))

    def test_existing_destinations_are_kept_unless_overwriting(self):
        source = self.tmp / "a.txt"
        source.write_text("x", encoding="utf-8")
        (self.tmp / "a.pdf").write_bytes(b"%PDF-1.4")
        jobs, skipped, _ = build_jobs([source], None, False)
        self.assertFalse(jobs)
        self.assertEqual(len(skipped), 1)
        jobs, skipped, _ = build_jobs([source], None, True)
        self.assertEqual(len(jobs), 1)
        self.assertFalse(skipped)

    def test_folder_scan_skips_unsupported_and_word_lock_files(self):
        for name in ("keep.txt", "skip.zip", "~$locked.docx"):
            (self.tmp / name).write_text("x", encoding="utf-8")
        found, _ = collect_inputs([str(self.tmp)], False)
        self.assertEqual([p.name for p in found], ["keep.txt"])

    def test_a_missing_path_is_a_warning_not_a_crash(self):
        found, warnings = collect_inputs([str(self.tmp / "nope")], False)
        self.assertFalse(found)
        self.assertEqual(len(warnings), 1)


class TestImageEngine(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow is not installed")
        from engines import image

        self.engine = image

    def test_transparency_lands_on_white_not_black(self):
        from PIL import Image

        flat = self.engine._flatten(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))
        self.assertEqual(flat.mode, "RGB")
        self.assertEqual(flat.getpixel((0, 0)), (255, 255, 255))

    def test_palette_with_transparency_is_flattened_too(self):
        from PIL import Image

        palette = Image.new("P", (10, 10))
        palette.info["transparency"] = 0
        self.assertEqual(self.engine._flatten(palette).mode, "RGB")

    def test_every_shape_fits_on_a_page_no_larger_than_a4(self):
        for width, height in ((6000, 4000), (4000, 6000), (100, 100), (9000, 300)):
            with self.subTest(size=(width, height)):
                resolution = self.engine._resolution(width, height)
                page = sorted((width / resolution, height / resolution))
                self.assertLessEqual(page[0], 8.28)
                self.assertLessEqual(page[1], 11.70)

    def test_orientation_tag_is_honoured(self):
        from PIL import Image

        tmp = Path(tempfile.mkdtemp()) / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6  # Orientation: rotate 90 degrees
        Image.new("RGB", (400, 200), "red").save(tmp, exif=exif)
        with Image.open(tmp) as opened:
            self.assertEqual(self.engine._pages(opened, ".jpg")[0].size, (200, 400))

    def test_tiff_frames_are_pages_but_gif_frames_are_animation(self):
        from PIL import Image

        tmp = Path(tempfile.mkdtemp())
        frames = [Image.new("RGB", (40, 40), c) for c in ("red", "green", "blue")]

        frames[0].save(tmp / "scan.tiff", save_all=True, append_images=frames[1:])
        with Image.open(tmp / "scan.tiff") as opened:
            self.assertEqual(len(self.engine._pages(opened, ".tiff")), 3)

        frames[0].save(tmp / "anim.gif", save_all=True, append_images=frames[1:])
        with Image.open(tmp / "anim.gif") as opened:
            self.assertEqual(len(self.engine._pages(opened, ".gif")), 1)

    def test_a_broken_image_is_reported_not_raised(self):
        tmp = Path(tempfile.mkdtemp())
        broken = tmp / "broken.png"
        broken.write_bytes(b"not a png at all")
        reported: list[tuple] = []
        self.engine.convert_jobs(
            [(broken, tmp / "broken.pdf")],
            lambda src, dst, err: reported.append((src, dst, err)),
        )
        self.assertEqual(len(reported), 1)
        self.assertIsNotNone(reported[0][2])

    def test_a_real_image_produces_a_pdf(self):
        from PIL import Image

        tmp = Path(tempfile.mkdtemp())
        source = tmp / "photo.png"
        Image.new("RGB", (300, 200), "gold").save(source)
        destination = tmp / "photo.pdf"
        errors: list = []
        self.engine.convert_jobs(
            [(source, destination)], lambda s, d, e: errors.append(e)
        )
        self.assertEqual(errors, [None])
        self.assertTrue(destination.is_file())
        self.assertTrue(destination.read_bytes().startswith(b"%PDF"))


def build_epub(path: Path, *, chapters_in_subfolder: bool = True) -> Path:
    """A small but structurally real EPUB, optionally with nested folders."""
    prefix = "OEBPS/text/" if chapters_in_subfolder else "OEBPS/"
    back = "../" if chapters_in_subfolder else ""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
            '<rootfile full-path="OEBPS/book.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(
            "OEBPS/book.opf",
            '<?xml version="1.0"?><package '
            'xmlns="http://www.idpf.org/2007/opf" version="2.0" '
            'unique-identifier="i"><metadata '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>A Test Book</dc:title>"
            '<dc:identifier id="i">urn:uuid:1</dc:identifier></metadata>'
            f'<manifest><item id="c1" href="{prefix[6:]}one.xhtml" '
            'media-type="application/xhtml+xml"/>'
            f'<item id="c2" href="{prefix[6:]}two.xhtml" '
            'media-type="application/xhtml+xml"/>'
            '<item id="s" href="css/style.css" media-type="text/css"/>'
            '</manifest><spine><itemref idref="c1"/><itemref idref="c2"/>'
            "</spine></package>",
        )
        archive.writestr("OEBPS/css/style.css", "h1 { color: teal; }")
        archive.writestr(
            prefix + "one.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
            f'<link rel="stylesheet" href="{back}css/style.css"/></head>'
            f'<body><h1>Chapter One</h1><img src="{back}images/cover.png"/>'
            "</body></html>",
        )
        archive.writestr(
            prefix + "two.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><head/><body>'
            '<h1>Chapter Two</h1><a href="https://example.org">out</a>'
            "</body></html>",
        )
        archive.writestr("OEBPS/images/cover.png", b"\x89PNG\r\n\x1a\n")
    return path


class TestEpubUnpacker(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_chapters_come_out_in_spine_order(self):
        book = build_epub(self.tmp / "book.epub")
        page = epub_engine.to_html(book, self.tmp / "out").read_text(encoding="utf-8")
        self.assertLess(page.index("Chapter One"), page.index("Chapter Two"))

    def test_the_html_is_named_after_the_book(self):
        # LibreOffice names the PDF after the file it is given, so the stem
        # has to survive the detour through HTML.
        book = build_epub(self.tmp / "my-novel.epub")
        self.assertEqual(epub_engine.to_html(book, self.tmp / "o").name,
                         "my-novel.html")

    def test_chapters_start_on_their_own_page(self):
        book = build_epub(self.tmp / "book.epub")
        page = epub_engine.to_html(book, self.tmp / "out").read_text(encoding="utf-8")
        self.assertEqual(page.count("page-break-before"), 1)

    def test_the_title_is_taken_from_the_manifest(self):
        book = build_epub(self.tmp / "book.epub")
        page = epub_engine.to_html(book, self.tmp / "out").read_text(encoding="utf-8")
        self.assertIn("<title>A Test Book</title>", page)

    def test_relative_paths_are_rebased_and_absolute_ones_left_alone(self):
        book = build_epub(self.tmp / "book.epub")
        out = self.tmp / "out"
        page = epub_engine.to_html(book, out).read_text(encoding="utf-8")
        self.assertIn('src="OEBPS/images/cover.png"', page)
        self.assertIn('href="OEBPS/css/style.css"', page)
        self.assertIn('href="https://example.org"', page)
        self.assertTrue((out / "OEBPS/images/cover.png").is_file())

    def test_flat_books_work_too(self):
        book = build_epub(self.tmp / "flat.epub", chapters_in_subfolder=False)
        page = epub_engine.to_html(book, self.tmp / "out").read_text(encoding="utf-8")
        self.assertIn("Chapter One", page)
        self.assertIn('src="OEBPS/images/cover.png"', page)

    def test_a_member_escaping_the_folder_is_refused(self):
        evil = self.tmp / "evil.epub"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("META-INF/container.xml", "<x/>")
            archive.writestr("../escaped.txt", "should never be written")
        with self.assertRaises(epub_engine.EpubError) as caught:
            epub_engine.to_html(evil, self.tmp / "out")
        self.assertIn("escapes", str(caught.exception))
        self.assertFalse((self.tmp / "escaped.txt").exists())
        self.assertFalse((self.tmp.parent / "escaped.txt").exists())

    def test_a_zip_that_is_not_a_book_says_so(self):
        plain = self.tmp / "plain.epub"
        with zipfile.ZipFile(plain, "w") as archive:
            archive.writestr("hello.txt", "nothing here")
        with self.assertRaises(epub_engine.EpubError) as caught:
            epub_engine.to_html(plain, self.tmp / "out")
        self.assertIn("container.xml", str(caught.exception))

    def test_a_file_that_is_not_a_zip_says_so(self):
        broken = self.tmp / "broken.epub"
        broken.write_bytes(b"this is not a zip file")
        with self.assertRaises(epub_engine.EpubError):
            epub_engine.to_html(broken, self.tmp / "out")


if __name__ == "__main__":
    unittest.main(verbosity=2)

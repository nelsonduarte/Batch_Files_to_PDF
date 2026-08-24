"""Microsoft Word engine: drives a real Word instance over COM.

Windows only, and only for word-processing formats — Word cannot open
spreadsheets or presentations. Requires pywin32.
"""

from __future__ import annotations

import sys
from typing import Callable

from jobs import Job

# wdExportFormatPDF / wdExportCreateHeadingBookmarks
EXPORT_PDF = 17
HEADING_BOOKMARKS = 1


def available() -> bool:
    """True when running on Windows with pywin32 and Word registered."""
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    try:
        import winreg

        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Word.Application"))
        return True
    except OSError:
        return False


def convert_jobs(jobs: list[Job], on_result: Callable[..., None]) -> None:
    """Convert every job, reporting each one through `on_result`."""
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    word = None
    try:
        try:
            # DispatchEx starts a dedicated instance, leaving the user's Word alone.
            word = win32.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
        except Exception as exc:  # noqa: BLE001 - Word is registered but won't start
            # available() only proves Word is registered, not that it can run
            # (mid-update, broken COM registration, no interactive desktop when
            # running as a service). Report the jobs instead of letting the
            # exception escape: the run still has LibreOffice files to convert.
            reason = f"could not start Microsoft Word: {exc}"
            for src, dst in jobs:
                on_result(src, dst, reason)
            return

        for src, dst in jobs:
            doc = None
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                doc = word.Documents.Open(
                    str(src),
                    ConfirmConversions=False,
                    ReadOnly=True,
                    AddToRecentFiles=False,
                    PasswordDocument="",       # avoids hanging on a password prompt
                )
                doc.ExportAsFixedFormat(
                    OutputFileName=str(dst),
                    ExportFormat=EXPORT_PDF,
                    OpenAfterExport=False,
                    CreateBookmarks=HEADING_BOOKMARKS,
                )
                on_result(src, dst, None)
            except Exception as exc:  # noqa: BLE001 - reported per file
                on_result(src, dst, str(exc))
            finally:
                if doc is not None:
                    try:
                        doc.Close(0)  # wdDoNotSaveChanges
                    except Exception:  # noqa: BLE001
                        pass
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass
        pythoncom.CoUninitialize()

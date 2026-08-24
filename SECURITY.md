# Security Policy

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue.

Use [GitHub's private vulnerability reporting](https://github.com/nelsonduarte/Batch_Files_to_PDF/security/advisories/new)
— the *Report a vulnerability* button under the repository's **Security** tab.
It opens a private advisory visible only to you and the maintainer.

Expect an acknowledgement within a few days. If a fix is warranted it will be
released together with a published advisory crediting you, unless you would
rather stay anonymous.

## Supported versions

This is a single-branch project: only the latest commit on `main` is supported.
There are no maintained release branches to backport fixes to.

## What this tool does with your files

Understanding the shape of the risk matters more here than a list of rules.

**It runs other programs on your files.** The whole design is to hand documents
to Microsoft Word (over COM) or LibreOffice (as a subprocess) rather than to
parse them here. That is deliberate — those suites have far better import
filters than anything this project could write — but it means **the real attack
surface is theirs, not ours**. A malicious `.docx` that exploits Word exploits
it through this tool just as it would through a double-click.

Keep Word and LibreOffice patched. That does more for your safety than
anything in this repository.

**It reads archives.** `.epub` files are unpacked by `engines/epub.py`, which is
our own code and therefore our own risk. Two mitigations are in place and are
covered by tests:

- Archive members whose paths would resolve outside the extraction folder are
  refused (`zip-slip`), so a crafted book cannot write into your home directory.
- Books are always unpacked into a fresh temporary folder that is removed when
  the run ends.

Note what is *not* mitigated: a zip bomb. A deliberately crafted `.epub` can
still expand to far more than its packed size and fill the disk. If you convert
books from untrusted sources, watch your free space.

**It writes PDFs next to your files by default.** Existing PDFs are never
replaced unless you pass `--overwrite`, and a source file is never used as its
own destination. Converting a folder you do not control still means writing into
that folder — pass `-o` to send the output somewhere else.

**It sends nothing anywhere.** There is no network access, no telemetry, and no
data leaves your machine. The only outbound traffic this project ever causes is
`pip` fetching its optional dependencies.

## Dependencies

All three Python dependencies are optional, and each unlocks one engine:
`pywin32`, `Pillow` and `pillow-heif`. Dependabot watches them, and GitHub
Actions are pinned to commit SHAs rather than moving tags so a compromised tag
cannot silently change what CI runs.

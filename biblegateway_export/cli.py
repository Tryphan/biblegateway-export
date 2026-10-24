"""Command-line interface, network lookup, UTF-8 files, and optional clipboard."""
import argparse
from http.client import HTTPException
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import __version__


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bg-export", description=(
        "Export one BibleGateway passage to Markdown, Org, or plain text. "
        "Short exclusion options retain their original meanings."))
    parser.add_argument("--format", choices=("markdown", "md", "org", "txt"), default="markdown")
    parser.add_argument("-o", "--output", type=Path, help="save UTF-8 output to FILE")
    clipboard = parser.add_mutually_exclusive_group()
    clipboard.add_argument("--clipboard", dest="clipboard", action="store_true")
    clipboard.add_argument("--no-clipboard", dest="clipboard", action="store_false")
    parser.set_defaults(clipboard=True)
    parser.add_argument("--script-version", action="version", version=__version__)
    parser.add_argument("-b", "--boldwords", action="store_true", help="bold the words of Jesus (Org/Markdown only)")
    for short, long, help_text in (
        ("c", "copyright", "copyright notice"), ("e", "headers", "editorial headings"),
        ("f", "footnotes", "footnotes"), ("n", "numbering", "verse and chapter numbers"),
        ("r", "crossrefs", "cross-references"),
    ):
        parser.add_argument(f"-{short}", f"--{long}", action="store_false",
                            help=f"exclude {help_text}")
    parser.add_argument("-i", "--info", action="store_true", help="diagnostics on stderr")
    parser.add_argument("-l", "--newline", action="store_true", help="chapter/verse lines (level 5/6 headings in Org/Markdown)")
    parser.add_argument("-t", "--test", type=Path, help="read local HTML instead of fetching")
    parser.add_argument("-v", "--version", default="NET", metavar="TRANSLATION",
                        help="BibleGateway translation abbreviation (default: NET)")
    parser.add_argument("reference", nargs="+", help="passage reference; spaces may be quoted")
    return parser


def fetch_html(reference: str, translation: str) -> str:
    url = "https://www.biblegateway.com/passage/?" + urlencode(
        {"interface": "print", "version": translation, "search": reference})
    request = Request(url, headers={"User-Agent": f"BibleGateway-Export/{__version__}"})
    with urlopen(request, timeout=30) as response:
        # BibleGateway uses UTF-8 even when no charset header is present.
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def copy_to_clipboard(text: str) -> None:
    """Use existing OS utilities without a Python clipboard dependency."""
    candidates = []
    if sys.platform == "darwin":
        candidates.append(["pbcopy"])
    elif os.name == "nt":
        # PowerShell reads Unicode stdin explicitly. No passage text is code.
        candidates.append(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                           "[Console]::InputEncoding=[Text.Encoding]::UTF8; "
                           "$input | Set-Clipboard"])
    else:
        if os.environ.get("WAYLAND_DISPLAY"):
            candidates.append(["wl-copy"])
        if os.environ.get("DISPLAY"):
            candidates.extend((["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]))
    for command in candidates:
        if shutil.which(command[0]):
            subprocess.run(command, input=text.encode("utf-8"), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=10)
            return
    raise OSError("no clipboard backend; install wl-clipboard on Wayland or use --no-clipboard")


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    reference = " ".join(args.reference).strip()
    if not reference or not args.version.strip():
        print("Error: passage and translation must not be empty", file=sys.stderr)
        return 1
    # Load the external parser only after --help/--script-version have exited.
    try:
        from .parser import PassageError, parse_passage
        from .render import Options, Renderer
    except ModuleNotFoundError as exc:
        print(f"Error: missing dependency {exc.name!r}; install beautifulsoup4 "
              "(Arch: sudo pacman -S python-beautifulsoup4)", file=sys.stderr)
        return 1
    try:
        if args.test:
            if args.info:
                print(f"Using test data from {args.test}", file=sys.stderr)
            html = args.test.read_text(encoding="utf-8")
        else:
            if args.info:
                print(f"Fetching {reference} ({args.version})", file=sys.stderr)
            html = fetch_html(reference, args.version)
        passage = parse_passage(html, reference, args.version)
        options = Options(**{key: getattr(args, key) for key in Options.__dataclass_fields__})
        text = Renderer(options).render(passage)
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        if args.clipboard:
            try:
                copy_to_clipboard(text)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f"Warning: clipboard unavailable ({exc}); use --no-clipboard to disable",
                      file=sys.stderr)
        return 0
    except (OSError, URLError, HTTPException, UnicodeError, PassageError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130

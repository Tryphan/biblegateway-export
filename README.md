# BibleGateway Export

Export BibleGateway passages to **Emacs Org mode** or **Markdown** from the command
line or directly into an Org buffer. Includes titles, editorial headings, chapter
and verse numbers, footnotes, cross-references, and copyright notices.

Version **2.0.0** is implemented in Python. The command remains `bg-export`, and
existing CLI options retain their meanings. No Ruby runtime or gems are needed.

Based on Jonathan Clark's
[BibleGateway-to-Markdown](https://github.com/jgclark/BibleGateway-to-Markdown)
(upstream commit `3d2104c6114a421edd428c29a3af5f0800e07eaf`). The Python implementation
uses Beautiful Soup to parse HTML into a passage model, then renders Org or
Markdown directly. The original Ruby versions remain in Git history.

## Requirements

- Python **3.10 or newer**.
- Beautiful Soup 4 (`beautifulsoup4>=4.12,<5`). Its transitive dependencies are
  installed by pip or your distribution package manager.
- Internet access for live lookups. Offline tests use local synthetic HTML.
- Git for repository management.
- Optional: Emacs **27.1 or newer** with its bundled Org mode.
- Optional: `wl-clipboard` for clipboard copying on Niri/Wayland.

There is no compilation/build step when running from a checkout. Python's
standard library supplies networking, argument parsing, and the test runner.

## Install on Arch Linux

```bash
sudo pacman -S --needed git python python-beautifulsoup4
```

If the repository already exists on your Forgejo instance:

```bash
mkdir -p ~/devel
git clone forgejo:bwarkentin/biblegateway-export.git ~/devel/biblegateway-export
cd ~/devel/biblegateway-export
```

Alternatively, clone the downloadable repository bundle:

```bash
mkdir -p ~/devel
git clone ~/Downloads/biblegateway-export-v2.0.0.bundle ~/devel/biblegateway-export
cd ~/devel/biblegateway-export
```

Run from the checkout:

```bash
python ./bg-export --no-clipboard --format org "John 3:16"
```

Keep the complete checkout in `~/devel/biblegateway-export`. To run from anywhere,
link the executable into a directory already on your PATH:

```bash
mkdir -p ~/scripts
ln -s ~/devel/biblegateway-export/bg-export ~/scripts/bg-export
```

`~/.local/bin` is another suitable location for the link. Existing links to
`bg-export` continue to work. Do not copy the launcher alone: it needs the
`biblegateway_export/` directory beside the real file.

### Other systems / virtual environment

Install Python, then create a virtual environment in the checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/bg-export --no-clipboard --format org "John 3:16"
```

For this setup, point the Emacs interpreter setting below to
`~/devel/biblegateway-export/.venv/bin/python`. Installing with pip also provides
the `bg-export` console command. Run `python -m biblegateway_export` as an
alternative entry point from a checkout or installed environment.

## Upgrade from Ruby v1.7.0

From a clean checkout of the earlier project, download the new bundle and run:

```bash
cd ~/devel/biblegateway-export
git fetch ~/Downloads/biblegateway-export-v2.0.0.bundle main --tags
git merge --ff-only FETCH_HEAD
```

This preserves your existing `origin`, including a Forgejo remote. Install the
Python dependencies above. Replace `biblegateway-export-ruby-program` in your
Emacs configuration with `biblegateway-export-python-program`, set to
`"/usr/bin/python"` on Arch, then restart Emacs. The old Ruby setting is no longer
used. Script paths, key bindings, CLI options, and the Emacs insertion command
keep the same names. Keep Ruby installed if other projects need it.

If you have your own commits or edits and a fast-forward is not possible, use the
provided v2.0.0 patch after reviewing it:

```bash
git apply --check ~/Downloads/biblegateway-export-v2.0.0.patch
git apply ~/Downloads/biblegateway-export-v2.0.0.patch
git add .
git commit -m "Port BibleGateway Export to Python"
```

The patch is based on v1.7.0; the check will report conflicting local changes.

## Usage

Save an Org passage for Emacs:

```bash
mkdir -p ~/faith/biblestudy
python ./bg-export --no-clipboard --format org -v NET \
  --output ~/faith/biblestudy/john-3.org "John 3"
```

Save Markdown:

```bash
python ./bg-export --no-clipboard --output john-3.md "John 3"
```

Markdown remains the default. Specify `--format org` explicitly even if the
filename ends in `.org`. Files use UTF-8; existing files are replaced, and parent
directories must already exist. Without `--output`, output goes to stdout.
Diagnostics go to stderr. Failures return a nonzero exit status.

References containing spaces can be quoted or supplied as multiple arguments.
Multiple noncontiguous passages or parallel translations are rejected: request
one at a time. Spacing and blank lines may differ from the Ruby output. Unicode
punctuation is preserved instead of replacing smart quotes and em dashes.

| Option | Effect |
| --- | --- |
| `--format markdown\|org` | Select output syntax; default Markdown |
| `-o FILE`, `--output FILE` | Write output to a file instead of stdout |
| `--no-clipboard` | Disable clipboard copying |
| `--clipboard` | Attempt clipboard copying (default) |
| `-v TRANSLATION`, `--version TRANSLATION` | Translation abbreviation; default NET |
| `-b`, `--boldwords` | Bold the words of Jesus |
| `-c`, `--copyright` | Exclude copyright notice |
| `-e`, `--headers` | Exclude editorial headings |
| `-f`, `--footnotes` | Exclude footnotes |
| `-r`, `--crossrefs` | Exclude cross-references |
| `-n`, `--numbering` | Exclude chapter and verse numbers |
| `-l`, `--newline` | Put chapters and verses under level 5 and 6 headings |
| `-i`, `--info` | Print lookup diagnostics to stderr |
| `-t FILE`, `--test FILE` | Read local HTML; a reference argument is still required |
| `--script-version` | Show program version |
| `-h`, `--help` | Show help |

Org uses star headings, `*bold*`, `/italics/`, `[fn:a]` footnotes, and native line
breaks. Cross-references use uppercase footnote labels. Both output formats are
rendered from the same parsed content; no Markdown-to-Org conversion is used.

## Emacs integration

Add this to your init file or an Emacs Lisp source block in `bsw-emacs.org`:

```elisp
(add-to-list 'load-path
             (expand-file-name "~/devel/biblegateway-export/emacs"))
(require 'biblegateway-export)

(setq biblegateway-export-script
      (expand-file-name "~/devel/biblegateway-export/bg-export")
      biblegateway-export-python-program "/usr/bin/python"
      biblegateway-export-translation "NET")

;; Optional: choose another key if C-c b is already assigned.
(define-key org-mode-map (kbd "C-c b") #'biblegateway-export-insert)
```

This is also provided in `emacs/config-example.el`. Restart Emacs after upgrading
from the Ruby version. In an Org buffer, put point where the passage should go,
then run `M-x biblegateway-export-insert` or `C-c b`. Enter a passage such as
`John 3:16-18`, then accept NET or enter another translation abbreviation.

The request runs asynchronously while you edit. The insertion marker follows
edits. The passage becomes a child of the heading containing point when you
started; before the first heading, it is a level-one heading. To always insert
top-level passages, set:

```elisp
(setq biblegateway-export-heading-level 1)
```

Each lookup gets unique footnote labels. Insertion is a single undo group and
does not replace selected text. Failures leave your note unchanged and show an
error buffer. If the note closes or becomes read-only during the fetch, the
result is kept in a separate buffer. Emacs invokes Python directly, disables
clipboard copying, and does not need the `~/scripts` symlink or a PATH change.

## Clipboard

The Python implementation uses existing OS utilities instead of a clipboard
library: `wl-copy` on Wayland, `xclip`/`xsel` on X11, `pbcopy` on macOS, and
PowerShell on Windows. A missing or failing backend produces a warning; saving
or printing the passage still succeeds. Clipboard behavior has automated tests
for the Wayland command selection; other platforms are not verified here.

For your Niri setup:

```bash
sudo pacman -S --needed wl-clipboard
bg-export --format org "John 3:16"
```

Alternatively, avoid automatic copying and use Emacs or a pipeline:

```bash
bg-export --no-clipboard --format org "John 3:16" | wl-copy
```

## Tests

No test framework dependency is needed beyond the runtime dependencies:

```bash
python -m unittest discover -s tests -v
emacs -Q --batch -L emacs -l tests/test_emacs.el -f ert-run-tests-batch-and-exit
```

If your test interpreter is not named `python3`, set `BG_TEST_PYTHON` to its
absolute filename when running the Emacs tests. The end-to-end Emacs test calls
the real Python exporter with synthetic HTML; no network request is required.

Tests cover formats, notes, headings, exclusions, Unicode, HTML variations,
file output, CLI errors, network failures, URL encoding, symlink execution,
clipboard fallback, and asynchronous Emacs insertion. Live NET, NIV, and LEB
samples were also checked during development. This does not guarantee every
translation or future BibleGateway markup will work.

## Repository structure

| Path | Purpose |
| --- | --- |
| `bg-export` | Python launcher, including symlink support |
| `biblegateway_export/cli.py` | CLI, fetching, file saving, clipboard |
| `biblegateway_export/parser.py` | HTML extraction using Beautiful Soup |
| `biblegateway_export/model.py` | Format-independent passage data |
| `biblegateway_export/render.py` | Markdown and Org rendering |
| `biblegateway_export/__init__.py` | Program version |
| `biblegateway_export/__main__.py` | `python -m` entry point |
| `pyproject.toml` | Requirements and installable package configuration |
| `emacs/` | Org insertion command and example configuration |
| `tests/` | Offline Python and Emacs tests and synthetic HTML fixture |
| `docs/` | Historical upstream notes and original README |
| `CHANGELOG.md` | Version history |

## Attribution and scope

The original Ruby script was written by Jonathan Clark. Its original README is
preserved in `docs/upstream-readme.md`, and the Ruby source remains in repository
history. The upstream snapshot did not include a license file; this project does
not assign a new license to that original code or documentation.

This project is not affiliated with BibleGateway. Translation copyrights remain
with their respective owners. Site structure can change without notice.

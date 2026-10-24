# BibleGateway Export

Export BibleGateway passages to **Emacs Org mode** or **Markdown** from the command
line. Includes passage titles, editorial headings, verse numbers, footnotes,
cross-references, and copyright notices, with options to omit these elements.

Derived from Jonathan Clark's
[BibleGateway-to-Markdown](https://github.com/jgclark/BibleGateway-to-Markdown),
upstream commit `3d2104c6114a421edd428c29a3af5f0800e07eaf`.
This repository adds Org output and reliability fixes. The command is `bg-export`.

## Install on Arch Linux

```bash
sudo pacman -S --needed git ruby
```

If you downloaded the Git bundle, create your working repository with:

```bash
mkdir -p ~/devel
git clone ~/Downloads/biblegateway-export-v1.7.0.bundle ~/devel/biblegateway-export
cd ~/devel/biblegateway-export
```

The bundle includes the initial commit and the `main` branch. Its clone source
will be the local bundle. To publish to your own Forgejo or GitHub repository,
create an empty repository there, then replace the remote:

```bash
git remote remove origin
git remote add origin YOUR_NEW_REPOSITORY_SSH_URL
git push -u origin main
```

Alternatively, extract the source archive and run `git init -b main` inside it.
The source archive does not include Git metadata.

Keep `lib/` beside `bg-export`. To run the command from anywhere:

```bash
mkdir -p ~/.local/bin
ln -s ~/devel/biblegateway-export/bg-export ~/.local/bin/bg-export
```

Ensure `~/.local/bin` is in your PATH. You can always run `ruby ./bg-export`
from the repository directory instead.

## Usage

Save Org for Emacs:

```bash
mkdir -p ~/faith/biblestudy
ruby ./bg-export --no-clipboard --format org -v NET \
  --output ~/faith/biblestudy/john-3.org "John 3"
```

Save Markdown:

```bash
ruby ./bg-export --no-clipboard --output john-3.md "John 3"
```

Preview in the terminal:

```bash
ruby ./bg-export --no-clipboard --format org "John 3:16"
```

Markdown is the default. Specify `--format org` even when the output filename ends
in `.org`. Files use UTF-8; existing files are replaced. Parent directories must
already exist. Without `--output`, the result goes to standard output; diagnostics
go to standard error. Failures return a nonzero exit status.

References containing spaces can be quoted or supplied as multiple arguments.
Separate, noncontiguous passages are not supported; run the command separately.

| Option | Effect |
| --- | --- |
| `--format markdown\|org` | Select output syntax; default Markdown |
| `-o FILE`, `--output FILE` | Save to a file instead of stdout |
| `--no-clipboard` | Disable clipboard copying |
| `--clipboard` | Attempt clipboard copying (default) |
| `-v VERSION`, `--version VERSION` | BibleGateway translation abbreviation; default NET |
| `-b`, `--boldwords` | Bold the words of Jesus |
| `-c`, `--copyright` | Exclude copyright notice |
| `-e`, `--headers` | Exclude editorial headings |
| `-f`, `--footnotes` | Exclude footnotes |
| `-r`, `--crossrefs` | Exclude cross-references |
| `-n`, `--numbering` | Exclude chapter and verse numbers |
| `-l`, `--newline` | Put chapters and verses under level 5 and 6 headings |
| `-i`, `--info` | Print parsing diagnostics to stderr |
| `-t FILE`, `--test FILE` | Read local HTML; a reference argument is still required |
| `--script-version` | Print program version |
| `-h`, `--help` | Show help |

Org output uses star headings, `*bold*`, `/italics/`, and `[fn:a]` footnotes.
Cross-references use uppercase footnote labels. The formatter handles the syntax
produced by this parser; it does not convert arbitrary Markdown.

## Emacs integration

Requires Emacs 27.1 or newer and its bundled Org mode. No additional Emacs
packages are needed. Add the following to your init file, or to an Emacs Lisp
source block in your literate `bsw-emacs.org` configuration:

```elisp
(add-to-list 'load-path
             (expand-file-name "~/devel/biblegateway-export/emacs"))
(require 'biblegateway-export)

(setq biblegateway-export-script
      (expand-file-name "~/devel/biblegateway-export/bg-export")
      biblegateway-export-ruby-program "/usr/bin/ruby"
      biblegateway-export-translation "NET")

;; Optional: choose another key if C-c b is already in use.
(define-key org-mode-map (kbd "C-c b") #'biblegateway-export-insert)
```

The same configuration is in `emacs/config-example.el`. Evaluate the block or
restart Emacs. In an Org buffer, put point where the passage should go and run
`M-x biblegateway-export-insert` (or `C-c b`). Enter a passage such as
`John 3:16-18`, then accept `NET` or enter another translation abbreviation.

Fetching runs asynchronously: keep editing while it works. The insertion position
follows your edits. By default the passage becomes a child of the heading that
contained point when you started the lookup; before the first heading it is a
level-one heading. To always insert top-level passages, set:

```elisp
(setq biblegateway-export-heading-level 1)
```

Each lookup gets unique Org footnote labels so passages inserted in the same note
do not share conflicting definitions. Insertion is a single undo group. Failed
lookups leave your note alone and show an error buffer. If you close the note or
make it read-only during the fetch, the result is preserved in a separate buffer.
The command inserts at point; it does not replace selected text. It disables
clipboard copying and invokes Ruby with an argument list, without a shell.

### Should this go in ~/scripts?

Keep the complete Git repository in `~/devel/biblegateway-export`. Its `lib/`
directory is required, so copying only `bg-export` into `~/scripts` will not work.
For terminal use, link the command into a directory already on your PATH:

```bash
mkdir -p ~/scripts
ln -s ~/devel/biblegateway-export/bg-export ~/scripts/bg-export
```

Use either this link or the earlier `~/.local/bin` link; both point to the same
checkout. If you prefer to keep the whole project under `~/scripts`, use
`~/scripts/biblegateway-export` and update both Emacs paths accordingly.
Emacs uses the absolute paths above and needs neither symlink nor PATH changes.

## Clipboard

File saving requires only Ruby's standard library. Optional clipboard copying
requires the `clipboard` gem and a working system clipboard backend:

```bash
gem install --user-install clipboard
```

On Niri/Wayland, use `--no-clipboard` and copy from Emacs, or install `wl-clipboard`
and pipe standard output to `wl-copy`:

```bash
ruby ./bg-export --no-clipboard --format org "John 3:16" | wl-copy
```

## Tests

Install the test dependency if needed:

```bash
gem install --user-install minitest
ruby test/test_cli.rb
```

Run the offline Emacs tests with:

```bash
emacs -Q --batch -L emacs -l test/test_emacs.el -f ert-run-tests-batch-and-exit
```

The offline suite uses synthetic HTML and checks both output formats, notes,
headings, exclusion options, file output, diagnostics, errors, and current title
and footer markup. A NET passage was also fetched for manual verification during
development. Other translations and future BibleGateway markup can differ.

## Files

| File | Purpose |
| --- | --- |
| `bg-export` | Executable Ruby command and HTML parser |
| `lib/output_format.rb` | Native Org formatting |
| `test/test_cli.rb` | Offline CLI regression tests |
| `emacs/biblegateway-export.el` | Asynchronous Org insertion command |
| `emacs/config-example.el` | Example Emacs configuration |
| `test/test_emacs.el` | Offline Emacs integration tests |
| `test/fixtures/passage.fixture` | Synthetic HTML input for tests |
| `README.md` | Installation and usage |
| `CHANGELOG.md` | Change history, including upstream history |
| `docs/biblegateway-html.md` | Upstream HTML structure notes (historical) |
| `docs/upstream-readme.md` | Original upstream README and attribution |
| `.gitignore`, `.gitattributes` | Git housekeeping |

## Attribution and scope

Original script by Jonathan Clark. Original documentation is preserved in
`docs/upstream-readme.md`. The upstream snapshot did not include a license file;
this derivative does not assign a new license to the original code.

This project is not affiliated with BibleGateway. Translation copyrights remain
with their respective owners. See `CHANGELOG.md` for changes in this extension.

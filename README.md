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
git clone ~/Downloads/biblegateway-export.bundle ~/devel/biblegateway-export
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

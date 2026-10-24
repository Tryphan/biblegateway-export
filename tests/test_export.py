"""Offline regression tests; run with python -m unittest discover -s tests -v."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from biblegateway_export import __version__
from biblegateway_export.cli import copy_to_clipboard, fetch_html, main
from biblegateway_export.parser import PassageError, alphabetical, parse_passage
from biblegateway_export.render import Options, Renderer

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/passage.fixture"
HTML = FIXTURE.read_text(encoding="utf-8")


def render(html=HTML, **options):
    return Renderer(Options(**options)).render(parse_passage(html))


class ParserAndRendererTests(unittest.TestCase):
    def test_markdown_default(self):
        out = render(boldwords=True)
        for text in ("# Sample 1:1-12 (TEST)", "## Sample heading",
                     "**Sample words** _supplied words_ & text <literal>",
                     "10-12", "[^a]: Sample 1:1 A **sample** note.",
                     "[^A]: Sample 2:1", "Sample copyright & notice."):
            self.assertIn(text, out)

    def test_org_headings_notes_and_breaks(self):
        out = render(format="org", boldwords=True, newline=True)
        for text in ("* Sample 1:1-12 (TEST)", "** Sample heading",
                     "***** Chapter 1", "****** 10-12",
                     "*Sample words* /supplied words/", "[fn:a][fn:A]",
                     "[fn:a] Sample 1:1 A *sample* note.",
                     "[fn:A] Sample 2:1", " \\\\\nNext line."):
            self.assertIn(text, out)
        self.assertNotIn("[^", out)
        self.assertNotIn("**Sample words**", out)

    def test_exclusions(self):
        out = render(headers=False, footnotes=False, crossrefs=False,
                     numbering=False, copyright=False)
        for text in ("Sample heading", "Footnotes", "Crossrefs", "copyright", "[^", "10-12"):
            self.assertNotIn(text, out)
        self.assertIn("Sample words", out)

    def test_modern_containers_scope_and_metadata(self):
        html = """<p>Navigation junk</p><section class='passage-box'>
        <h1 class='passage-display'><span class='bcv'><span>Current 2:1</span></span>
        <span class='translation'>Test version</span></h1>
        <div class='passage-text'><div class='passage-content'>
        <h3>Editorial title</h3><p><span class='text'><span class='chapternum'>2</span>
        Unicode “words”—αβ &amp; &lt;literal&gt; <span class='small-caps'>Lord</span>.
        </span></p></div></div>
        <div class='copyright-table'><div class='publisher-info-bottom'>
        <p>Copyright outside passage-text.</p></div></div></section>
        <p>Unrelated paragraph</p><footer><h3>Font Size</h3><p>Footer junk</p></footer>"""
        out = render(html)
        for text in ("# Current 2:1 (Test version)", "Unicode “words”—αβ & <literal>",
                     "LORD", "Copyright outside passage-text."):
            self.assertIn(text, out)
        for text in ("Navigation junk", "Unrelated paragraph", "Font Size", "Footer junk"):
            self.assertNotIn(text, out)

    def test_current_saved_fixture_with_poetry_and_nested_notes(self):
        html = (FIXTURE.parent / 'current.fixture').read_text(encoding='utf-8')
        passage = parse_passage(html)
        self.assertEqual(passage.reference, 'Sample 2:1-3')
        self.assertEqual(len(passage.blocks), 3)
        for fmt in ['markdown', 'org']:
            out = Renderer(Options(format=fmt, boldwords=True)).render(passage)
            self.assertIn('Sample copyright & notice.', out)
            self.assertIn('Sample 4:1; Sample 5:1', out)
            self.assertIn('Greek αβ.', out)
            self.assertIn('Another sample line.', out)
            self.assertNotIn('Navigation junk', out)
            self.assertNotIn('Footer junk', out)

    def test_legacy_div_titles(self):
        html = HTML.replace('class="passage-display-bcv"', 'class="bcv"').replace(
            'class="passage-display-version"', 'class="translation"')
        self.assertIn("# Sample 1:1-12 (TEST)", render(html))

    def test_attribute_order_quotes_and_multiline(self):
        html = HTML.replace('<sup class="versenum">', "<sup\n data-extra='x' class='mid-line versenum'>")
        html = html.replace('<i>', '<em data-extra="x">').replace('</i>', '</em>')
        self.assertIn("10-12", render(html))
        self.assertIn("_supplied words_", render(html))

    def test_nested_words_and_italics(self):
        html = HTML.replace('Sample words</span>', 'Sample <em>nested</em> words</span>')
        self.assertIn("*Sample /nested/ words*", render(html, format="org", boldwords=True))

    def test_redletter_wrapping_keeps_verse_headings_and_breaks(self):
        html = HTML.replace('<span class="woj">Sample words</span>',
                            '<span class="woj"><sup class="versenum">2</sup>'
                            'Sample words<br/>More words</span>')
        for fmt, expected in [('org', '****** 2 *Sample words*'),
                              ('markdown', '###### 2 **Sample words**')]:
            with self.subTest(format=fmt):
                out = render(html, format=fmt, boldwords=True, newline=True)
                self.assertIn(expected, out)
                self.assertNotIn('**######', out)
                self.assertNotIn('*More words \\\\*', out)

    def test_literal_markup_is_not_converted_by_org_renderer(self):
        html = HTML.replace('Sample words', 'Literal **stars** and _underscores_')
        self.assertIn('Literal **stars** and _underscores_', render(html, format="org"))

    def test_notes_use_ids_rather_than_list_position(self):
        html = HTML.replace("data-fn='a'", "data-fn='#fen-TEST-123aa'").replace(
            '>a</a>', '>aa</a>').replace('<li><a title="note">', '<li id="fen-TEST-123aa"><a title="note">')
        self.assertIn('[^aa]:', render(html))
        self.assertNotIn('[^a]:', render(html))
        self.assertEqual(alphabetical(26), 'aa')
        self.assertEqual(alphabetical(702, True), 'AAA')

    def test_multiple_crossref_links(self):
        html = HTML.replace('</a></li>', '</a>; <a class="crossref-link">Sample 3:1</a></li>')
        out = render(html)
        self.assertIn('[^A]: Sample 2:1; Sample 3:1', out)
        self.assertNotIn('[^B]:', out)

    def test_rejects_multiple_passages(self):
        with self.assertRaisesRegex(PassageError, 'Multiple passages'):
            parse_passage('<div class="passage-content"></div>' * 2)

    def test_rejects_error_pages_and_heading_only(self):
        for html in ('', '<p>Service unavailable</p>', '<h1 class="passage-display">Oops</h1>',
                     '<div class="passage-content"><p><sup class="versenum">1</sup></p></div>'):
            with self.subTest(html=html), self.assertRaises(PassageError):
                parse_passage(html)

    def test_parser_model_is_format_independent(self):
        passage = parse_passage(HTML)
        self.assertEqual(passage.reference, "Sample 1:1-12")
        self.assertEqual(passage.footnotes[0].label, "a")
        self.assertEqual(passage.crossrefs[0].label, "A")
        self.assertNotIn('[fn:', repr(passage))


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'bg-export'), '--no-clipboard', *args],
                              capture_output=True, text=True, encoding='utf-8')

    def test_cli_org(self):
        result = self.cli('-t', str(FIXTURE), '--format', 'org', 'Sample', '1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertTrue(result.stdout.startswith('* Sample'))

    def test_output_file_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'passage.org'
            result = self.cli('-t', str(FIXTURE), '-i', '--format', 'org', '-o', str(path), 'Sample')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertIn('Using test data', result.stderr)
            self.assertTrue(path.read_text(encoding='utf-8').startswith('* Sample'))

    def test_invalid_arguments_and_missing_file(self):
        for args in ([], ['--format', 'invalid'], ['-t', '/no/such/file', 'Sample'], ['   ']):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('error:', result.stderr.lower())
                self.assertNotIn('Traceback', result.stderr)

    def test_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'existing.org'
            output.write_text('Existing note', encoding='utf-8')
            html = Path(tmp) / 'invalid.html'
            html.write_text('<p>Not a passage</p>', encoding='utf-8')
            result = self.cli('-t', str(html), '-o', str(output), 'Sample')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), 'Existing note')

    def test_output_write_failure(self):
        result = self.cli('-t', str(FIXTURE), '-o', '/no/such/parent/out.org', 'Sample')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('Traceback', result.stderr)

    def test_help_version_and_module_entry_point(self):
        for args, expected in ((['--help'], '--format'), (['--script-version'], __version__)):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)
        result = subprocess.run([sys.executable, '-m', 'biblegateway_export', '--script-version'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(__version__, result.stdout)

    @unittest.skipUnless(hasattr(os, 'symlink'), 'requires symlinks')
    def test_symlink_from_other_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / 'bg-export'
            link.symlink_to(ROOT / 'bg-export')
            result = subprocess.run([sys.executable, str(link), '--script-version'],
                                    cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(__version__, result.stdout)

    def test_reference_is_joined_and_translation_preserved(self):
        out, err = io.StringIO(), io.StringIO()
        with patch('biblegateway_export.cli.fetch_html', return_value=HTML) as fetch:
            with redirect_stdout(out), redirect_stderr(err):
                result = main(['--no-clipboard', '-v', 'NIV', 'John', '3:16'])
        self.assertEqual(result, 0)
        fetch.assert_called_once_with('John 3:16', 'NIV')

    def test_fetch_url_encoding_timeout_and_utf8(self):
        class Response:
            from email.message import Message
            headers = Message()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return 'αβ'.encode('utf-8')
        with patch('biblegateway_export.cli.urlopen', return_value=Response()) as urlopen:
            self.assertEqual(fetch_html('1 Cor 12:31-13:13', 'NET'), 'αβ')
            request = urlopen.call_args.args[0]
            self.assertEqual(parse_qs(urlparse(request.full_url).query)['search'], ['1 Cor 12:31-13:13'])
            self.assertEqual(urlopen.call_args.kwargs['timeout'], 30)

    def test_network_errors(self):
        for error in (URLError('offline'), HTTPError('https://example.test', 503, 'Unavailable', {}, None)):
            out, err = io.StringIO(), io.StringIO()
            with patch('biblegateway_export.cli.fetch_html', side_effect=error):
                with redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(main(['--no-clipboard', 'John 3:16']), 1)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('Error:', err.getvalue())

    def test_clipboard_failure_is_nonfatal(self):
        out, err = io.StringIO(), io.StringIO()
        with patch('biblegateway_export.cli.copy_to_clipboard', side_effect=OSError('missing')):
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(main(['--clipboard', '-t', str(FIXTURE), 'Sample']), 0)
        self.assertIn('# Sample', out.getvalue())
        self.assertIn('Warning: clipboard unavailable', err.getvalue())

    def test_wayland_clipboard_backend(self):
        with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-1'}, clear=True):
            with patch('biblegateway_export.cli.shutil.which', return_value='/usr/bin/wl-copy'):
                with patch('biblegateway_export.cli.subprocess.run') as run:
                    copy_to_clipboard('αβ')
        self.assertEqual(run.call_args.args[0], ['wl-copy'])
        self.assertEqual(run.call_args.kwargs['input'], 'αβ'.encode('utf-8'))


if __name__ == '__main__':
    unittest.main()

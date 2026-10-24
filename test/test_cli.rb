require 'minitest/autorun'
require 'open3'
require 'tmpdir'
require 'rbconfig'
require_relative '../lib/output_format'

class CliTest < Minitest::Test
  SCRIPT = File.expand_path('../bg-export', __dir__)
  FIXTURE = File.expand_path('fixtures/passage.fixture', __dir__)

  def run_cli(*args)
    Open3.capture3(RbConfig.ruby, SCRIPT, '--no-clipboard', *args)
  end

  def test_markdown_default
    out, err, status = run_cli('-t', FIXTURE, '-b', 'Sample', '1')
    assert status.success?, err
    assert_empty err
    assert_includes out, '# Sample 1:1-12 (TEST)'
    assert_includes out, '**Sample words** _supplied words_ & text <literal>'
    assert_match(/10-12\s+More/, out)
    assert_includes out, '[^a]: Sample 1:1 A **sample** note.'
    assert_includes out, '[^A]: Sample 2:1'
  end

  def test_org_with_headings_and_notes
    out, err, status = run_cli('-t', FIXTURE, '-b', '-l', '--format', 'org', 'Sample 1')
    assert status.success?, err
    assert_includes out, '* Sample 1:1-12 (TEST)'
    assert_includes out, '** Sample heading'
    assert_includes out, '***** Chapter 1'
    assert_includes out, '****** 10-12'
    assert_includes out, '*Sample words* /supplied words/'
    assert_includes out, '[fn:a]'
    assert_includes out, '[fn:a] Sample 1:1 A *sample* note.'
    assert_includes out, '[fn:A] Sample 2:1'
    refute_match(/\[\^|^\#/, out)
    assert_includes out, " \\\\\n"
  end

  def test_exclusion_options
    out, err, status = run_cli('-t', FIXTURE, '-e', '-f', '-r', '-n', '-c', 'Sample')
    assert status.success?, err
    %w[heading Footnotes Crossrefs copyright chapternum versenum].each { |word| refute_includes out, word }
    refute_includes out, '10-12 More'
    refute_includes out, '[^'
  end

  def test_output_file_and_verbose_stderr
    Dir.mktmpdir do |dir|
      path = File.join(dir, 'sample.org')
      out, err, status = run_cli('-t', FIXTURE, '-i', '--format', 'org', '-o', path, 'Sample')
      assert status.success?, err
      assert_empty out
      assert_includes err, 'Using test data'
      assert File.read(path).start_with?('* Sample')
    end
  end

  def test_errors
    [[], ['--format', 'invalid'], ['-t', '/does/not/exist', 'Sample']].each do |args|
      out, err, status = run_cli(*args)
      refute status.success?
      assert_empty out
      assert_includes err, 'Error:'
    end
  end

  def test_current_span_title_and_footer
    Dir.mktmpdir do |dir|
      html = File.read(FIXTURE)
        .sub('<span class="passage-display-bcv">', %q{<span class='bcv'><span class="dropdown-display"><span class="dropdown-display-text">})
        .sub('<span class="passage-display-version">', %q{<span class='translation'><span class="dropdown-display"><span class="dropdown-display-text">})
        .sub('<section class="other-resources">', '<footer><h3>Font Size</h3><p>Footer junk</p>')
      path = File.join(dir, 'current.fixture')
      File.write(path, html)
      out, err, status = run_cli('-t', path, 'Sample')
      assert status.success?, err
      assert_includes out, '# Sample 1:1-12 (TEST)'
      refute_includes out, 'Font Size'
      refute_includes out, 'Footer junk'
    end
  end

  def test_help
    out, err, status = run_cli('--help')
    assert status.success?, err
    assert_includes out, '--format'
  end
end

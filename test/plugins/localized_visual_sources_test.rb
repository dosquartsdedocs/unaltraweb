# frozen_string_literal: true

require "fileutils"
require "jekyll"
require "minitest/autorun"
require "tmpdir"

require_relative "../../_plugins/localized_visual_sources"

class LocalizedVisualSourcesTest < Minitest::Test
  def setup
    @temporary = Dir.mktmpdir
    @project = File.realpath(@temporary)
  end

  def teardown
    FileUtils.remove_entry(@temporary)
  end

  def write(path)
    absolute = File.join(@project, path)
    FileUtils.mkdir_p(File.dirname(absolute))
    File.write(absolute, "visual")
  end

  def select(path, lang: "ca")
    Unaltraweb::LocalizedVisualSources.select_url(
      path,
      site_source: @project,
      lang: lang,
      default_lang: "en",
      languages: %w[en es ca]
    )
  end

  def test_selects_localized_variants_before_complete_suffixes
    %w[
      map.ca.svg plot.ca.qmd bars.ca.vl.json flow.ca.puml
      sidebar.ca.capture.yml flow.ca.puml.edited.svg
    ].each { |path| write("assets/#{path}") }

    assert_equal "assets/map.ca.svg", select("assets/map.svg")
    assert_equal "assets/plot.ca.qmd", select("assets/plot.qmd")
    assert_equal "assets/bars.ca.vl.json", select("assets/bars.vl.json")
    assert_equal "assets/flow.ca.puml", select("assets/flow.puml")
    assert_equal "assets/sidebar.ca.capture.yml", select("assets/sidebar.capture.yml")
    assert_equal "assets/flow.ca.puml.edited.svg", select("assets/flow.puml.edited.svg")
  end

  def test_preserves_baseurl_decoration_and_falls_back_to_default_source
    write("assets/map.ca.svg")
    write("assets/default.svg")

    assert_equal "{{ site.baseurl }}/assets/map.ca.svg?v=2#panel", select("{{ site.baseurl }}/assets/map.svg?v=2#panel")
    assert_equal "assets/default.svg", select("assets/default.svg")
  end

  def test_leaves_default_remote_and_explicit_localized_paths_unchanged
    write("assets/map.ca.svg")

    assert_equal "assets/map.svg", select("assets/map.svg", lang: "en")
    assert_equal "https://example.org/map.svg", select("https://example.org/map.svg")
    assert_equal "assets/map.ca.svg", select("assets/map.ca.svg")
  end

  def test_rewrites_markdown_and_html_but_not_code
    write("assets/map.ca.svg")
    source = <<~MARKDOWN
      ![Map]({{ site.baseurl }}/assets/map.svg "Caption")
      <img src="assets/map.svg" alt="Map">
      `![Inline](assets/map.svg)`
      ```markdown
      ![Example](assets/map.svg)
      ```
    MARKDOWN

    result = Unaltraweb::LocalizedVisualSources.rewrite(
      source,
      site_source: @project,
      lang: "ca",
      default_lang: "en",
      languages: %w[en ca]
    )

    assert_includes result, "![Map]({{ site.baseurl }}/assets/map.ca.svg"
    assert_includes result, '<img src="assets/map.ca.svg"'
    assert_includes result, "`![Inline](assets/map.svg)`"
    assert_includes result, "![Example](assets/map.svg)"
  end

  def test_restores_many_inline_code_tokens_without_prefix_collisions
    write("assets/map.ca.svg")
    code = (0..12).map { |index| "`command-#{index}`" }.join(" ")
    source = "#{code}\n\n![Map](assets/map.svg)\n"

    result = Unaltraweb::LocalizedVisualSources.rewrite(
      source,
      site_source: @project,
      lang: "ca",
      default_lang: "en",
      languages: %w[en ca]
    )

    (0..12).each { |index| assert_includes result, "`command-#{index}`" }
    assert_includes result, "![Map](assets/map.ca.svg)"
  end
end

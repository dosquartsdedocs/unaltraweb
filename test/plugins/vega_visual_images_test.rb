# frozen_string_literal: true

require "fileutils"
require "jekyll"
require "minitest/autorun"
require "tmpdir"
require "yaml"

require_relative "../../_plugins/vega_visual_images"

class VegaVisualImagesTest < Minitest::Test
  def setup
    @temporary = Dir.mktmpdir
    @project = File.realpath(@temporary)
  end

  def teardown
    FileUtils.remove_entry(@temporary)
  end

  def write(path, content = "")
    absolute = File.join(@project, path)
    FileUtils.mkdir_p(File.dirname(absolute))
    File.binwrite(absolute, content)
  end

  def write_manifest(items)
    manifest = {
      "version" => 1,
      "profile" => "vl-convert-1.9.0",
      "family" => "benizar",
      "visualizations" => items
    }
    write(".vegavisuals.yml", YAML.safe_dump(manifest, aliases: false))
  end

  def visualization(name:, source:, output:)
    { "name" => name, "source" => source, "output" => output }
  end

  def assert_fatal(pattern)
    error = assert_raises(Jekyll::Errors::FatalException) { yield }
    assert_match(pattern, error.message)
  end

  def prepare_visualizations
    write("assets/charts/bars.vl.json", "{}")
    write("assets/charts/network.vg.json", "{}")
    write("assets/img/bars.svg", "<svg/>")
    write("assets/img/network.png", "png")
    write_manifest(
      [
        visualization(name: "bars", source: "assets/charts/bars.vl.json", output: "assets/img/bars.svg"),
        visualization(name: "network", source: "assets/charts/network.vg.json", output: "assets/img/network.png")
      ]
    )
  end

  def test_rewrites_markdown_and_preserves_title_attributes_and_url_decoration
    prepare_visualizations
    source = '![Bars]({{ site.baseurl }}/assets/charts/bars.vl.json?v=4#view "Quarterly bars"){: #bars .wide data-figure-width="42rem"}'

    result = Unaltraweb::VegaVisualImages.rewrite(source, site_source: @project)

    assert_equal '![Bars]({{ site.baseurl }}/assets/img/bars.svg?v=4#view "Quarterly bars"){: #bars .wide data-figure-width="42rem"}', result
  end

  def test_rewrites_html_img_src_without_changing_other_attributes
    prepare_visualizations
    source = "<figure><img class='chart' src='/assets/charts/network.vg.json#marks' alt='Network' data-kind='vega'></figure>"

    result = Unaltraweb::VegaVisualImages.rewrite(source, site_source: @project)

    assert_equal "<figure><img class='chart' src='/assets/img/network.png#marks' alt='Network' data-kind='vega'></figure>", result
  end

  def test_roots_relative_outputs_at_the_site_baseurl
    prepare_visualizations

    result = Unaltraweb::VegaVisualImages.rewrite(
      "![Bars](assets/charts/bars.vl.json)",
      site_source: @project
    )

    assert_equal "![Bars]({{ site.baseurl }}/assets/img/bars.svg)", result
  end

  def test_uses_project_manifest_when_jekyll_source_is_a_subdirectory
    write("docs/assets/charts/bars.vl.json", "{}")
    write("docs/assets/img/bars.svg", "<svg/>")
    write_manifest(
      [visualization(name: "bars", source: "docs/assets/charts/bars.vl.json", output: "docs/assets/img/bars.svg")]
    )

    result = Dir.chdir(@project) do
      Unaltraweb::VegaVisualImages.rewrite(
        "![Bars](docs/assets/charts/bars.vl.json)",
        site_source: File.join(@project, "docs")
      )
    end

    assert_equal "![Bars]({{ site.baseurl }}/assets/img/bars.svg)", result
  end

  def test_skips_fenced_code_and_non_exact_suffixes
    prepare_visualizations
    source = <<~MARKDOWN
      ```markdown
      ![Example](assets/charts/bars.vl.json "Example")
      ```

      ![Archive](assets/charts/bars.vl.json.backup "Archive")
    MARKDOWN

    assert_equal source, Unaltraweb::VegaVisualImages.rewrite(source, site_source: @project)
  end

  def test_skips_inline_code_spans
    prepare_visualizations
    source = "Use `![Bars](assets/charts/bars.vl.json)` as documented syntax."

    assert_equal source, Unaltraweb::VegaVisualImages.rewrite(source, site_source: @project)
  end

  def test_rejects_absent_manifest_and_missing_source
    write("assets/charts/bars.vl.json", "{}")
    assert_fatal(/Missing required.*\.vegavisuals\.yml/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end

    write_manifest([visualization(name: "bars", source: "assets/charts/missing.vl.json", output: "assets/img/bars.svg")])
    assert_fatal(/source for Vega visualization bars is not a file/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end

  def test_rejects_undeclared_source_and_missing_output
    write("assets/charts/bars.vl.json", "{}")
    write("assets/charts/other.vl.json", "{}")
    write("assets/img/other.svg", "<svg/>")
    write_manifest([visualization(name: "other", source: "assets/charts/other.vl.json", output: "assets/img/other.svg")])
    assert_fatal(/not declared/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end

    write_manifest([visualization(name: "bars", source: "assets/charts/bars.vl.json", output: "assets/img/missing.svg")])
    assert_fatal(/output is not a file/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end

  def test_rejects_pdf_output_for_web_image_references
    write("assets/charts/bars.vl.json", "{}")
    write("assets/img/bars.pdf", "%PDF-1.4")
    write_manifest([visualization(name: "bars", source: "assets/charts/bars.vl.json", output: "assets/img/bars.pdf")])

    assert_fatal(/cannot be embedded as a web image.*SVG or PNG/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end

  def test_rejects_unsafe_reference_and_manifest_escapes
    assert_fatal(/safe project-relative path/) do
      Unaltraweb::VegaVisualImages.rewrite("![Outside](../outside.vl.json)", site_source: @project)
    end

    write("assets/charts/bars.vl.json", "{}")
    write_manifest([visualization(name: "bars", source: "../outside.vl.json", output: "assets/img/bars.svg")])
    assert_fatal(/safe project-relative path/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end

    write_manifest([visualization(name: "bars", source: "assets/charts/bars.vl.json", output: "../outside.svg")])
    assert_fatal(/safe project-relative path/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end

  def test_rejects_duplicate_sources
    write("assets/charts/bars.vl.json", "{}")
    write_manifest(
      [
        visualization(name: "bars-svg", source: "assets/charts/bars.vl.json", output: "assets/img/bars.svg"),
        visualization(name: "bars-png", source: "assets/charts/bars.vl.json", output: "assets/img/bars.png")
      ]
    )

    assert_fatal(/Duplicate Vega visualization source/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end

  def test_rejects_duplicate_yaml_keys_aliases_and_wrong_version
    write("assets/charts/bars.vl.json", "{}")
    duplicate = <<~YAML
      version: 1
      version: 1
      profile: vl-convert-1.9.0
      family: benizar
      visualizations: []
    YAML
    write(".vegavisuals.yml", duplicate)
    assert_fatal(/Duplicate YAML key/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end

    aliases = <<~YAML
      version: 1
      profile: vl-convert-1.9.0
      family: benizar
      visualizations: &visualizations []
      other: *visualizations
    YAML
    write(".vegavisuals.yml", aliases)
    assert_fatal(/YAML aliases are not allowed/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end

    write(".vegavisuals.yml", "version: 2\nprofile: vl-convert-1.9.0\nfamily: benizar\nvisualizations: []\n")
    assert_fatal(/version must be 1/) do
      Unaltraweb::VegaVisualImages.rewrite("![Bars](assets/charts/bars.vl.json)", site_source: @project)
    end
  end
end

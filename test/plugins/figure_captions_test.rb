# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "nokogiri"

require_relative "../../_plugins/figure_captions"

class FigureCaptionsTest < Minitest::Test
  def test_uses_web_dimensions_and_ignores_pdf_dimensions_in_html_layout
    markdown = <<~MARKDOWN.strip
      ![Map](assets/img/map.svg "Map caption"){: data-figure-width-web="44rem" data-figure-height-web="32rem" data-figure-width-pdf="82%" data-figure-height-pdf="420pt"}
    MARKDOWN

    result = Unaltraweb::FigureCaptions.transform_markdown_images(markdown, "en", "Figure")
    fragment = Nokogiri::HTML::DocumentFragment.parse(result)
    figure = fragment.at_css("figure.md-figure")

    assert_includes figure["style"], "--md-figure-width: 44rem;"
    assert_includes figure["style"], "--md-figure-height: 32rem;"
    assert_includes figure["style"], "--md-figure-image-width: 100%;"
    refute_includes figure["style"], "82%"
    refute_includes figure["style"], "420pt"
  end

  def test_legacy_width_remains_the_web_fallback
    markdown = '![Flow](assets/diagrams/flow.mmd "Flow"){: data-figure-width="22rem"}'

    result = Unaltraweb::FigureCaptions.transform_markdown_images(markdown, "en", "Figure")
    figure = Nokogiri::HTML::DocumentFragment.parse(result).at_css("figure.md-figure")

    assert_includes figure["style"], "--md-figure-width: 22rem;"
  end

  def test_post_render_fallback_preserves_web_dimensions
    html = <<~HTML
      <p><img src="assets/img/map.svg" alt="Map" data-figure-width-web="37rem" data-figure-width-pdf="82%"></p>
    HTML

    result = Unaltraweb::FigureCaptions.wrap_html_images(html, "en", "Figure")
    figure = Nokogiri::HTML::DocumentFragment.parse(result).at_css("figure.md-figure")

    assert_includes figure["style"], "--md-figure-width: 37rem;"
    refute_includes figure["style"], "82%"
  end

  def test_subfigures_apply_web_dimensions_to_the_image_not_the_pdf_dimensions
    markdown = <<~MARKDOWN
      ::: subfigures a+b "Comparison"
      ![A](a.svg "Panel A"){: data-figure-width-web="80%" data-figure-height-web="18rem" data-figure-width-pdf="95%"}
      ![B](b.svg "Panel B")
      :::
    MARKDOWN

    result = Unaltraweb::FigureCaptions.transform_markdown_images(markdown, "en", "Figure")
    first_panel = Nokogiri::HTML::DocumentFragment.parse(result).at_css('.md-subfigure[data-panel="a"]')

    assert_includes first_panel["style"], "--md-subfigure-image-width: 80%;"
    assert_includes first_panel["style"], "--md-subfigure-image-max-height: 18rem;"
    refute_includes first_panel["style"], "95%"
  end
end

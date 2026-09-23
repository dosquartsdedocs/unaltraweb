# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "nokogiri"

require_relative "../../_plugins/figure_captions"

class FigureCaptionsTest < Minitest::Test
  def test_figure_caption_has_separate_number_description_and_source
    markdown = %q{![Accessible map](map.svg "A descriptive caption"){: data-caption-source="Source: [Verified origin](https://example.org/)." data-figure-width="22rem"}}
    result = Unaltraweb::FigureCaptions.transform_markdown_images(markdown, "en", "Figure")
    figure = Nokogiri::HTML::DocumentFragment.parse(result).at_css("figure")

    assert_equal "Figure 1.", figure.at_css(".figlabel").text
    assert_equal "A descriptive caption", figure.at_css(".md-caption-text").text
    assert_equal "Source: Verified origin.", figure.at_css(".md-caption-source").text
    assert_equal "https://example.org/", figure.at_css(".md-caption-source a")["href"]
    assert_equal "Accessible map", figure.at_css("img")["alt"]
    assert_nil figure.at_css("img")["data-caption-source"]
    assert_includes figure["style"], "22rem"
  end

  def test_source_with_liquid_braces_and_unicode_apostrophe_is_not_truncated
    markdown = %q{![Map](map.svg "Description"){: data-caption-source='Font: {% cite verified %}; elaboració de l’autor.'}}
    result = Unaltraweb::FigureCaptions.transform_markdown_images(markdown, "ca", "Figura")
    figure = Nokogiri::HTML::DocumentFragment.parse(result).at_css("figure")

    assert_equal "Font: {% cite verified %}; elaboració de l’autor.", figure.at_css(".md-caption-source").text
    assert_equal ["src", "alt"], figure.at_css("img").attribute_nodes.map(&:name)
  end

  def test_table_and_subfigures_keep_sources_with_the_correct_caption
    markdown = <<~MARKDOWN
      ::: table "Table description" {: data-caption-source="Source: synthetic values."}
      | A | B |
      | --- | --- |
      | 1 | 2 |
      :::

      ::: subfigures a+b "Shared description" {: data-caption-source="Source: shared credits."}
      ![A](a.svg "Panel A"){: data-caption-source="Source: panel A."}
      ![B](b.svg "Panel B")
      :::
    MARKDOWN
    result = Unaltraweb::FigureCaptions.transform_markdown_sugar(markdown, "en", "Figure", "Table")
    fragment = Nokogiri::HTML::DocumentFragment.parse(result)

    assert_equal "Source: synthetic values.", fragment.at_css(".md-table-caption .md-caption-source").text
    assert_equal "Table 1.", fragment.at_css(".md-table .figlabel").text
    assert_equal "Source: shared credits.", fragment.at_css(".md-figcaption .md-caption-source").text
    assert_equal "Source: panel A.", fragment.at_css(".md-subfigure-caption .md-caption-source").text
    assert_equal 3, fragment.css(".md-caption-source").length
  end

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

  def test_captioned_listing_wraps_exactly_one_fence_with_localized_numbering
    markdown = <<~MARKDOWN
      ::: listing "Read a layer"
      ```python
      print("roads")
      ```
      :::
    MARKDOWN

    result = Unaltraweb::FigureCaptions.transform_markdown_sugar(
      markdown,
      "en",
      "Figure",
      "Table",
      "Code example"
    )
    fragment = Nokogiri::HTML::DocumentFragment.parse(result)
    listing = fragment.at_css("figure.md-code-listing")

    assert_equal "lst-en-1", listing["id"]
    assert_equal "Code example 1. Read a layer", listing.at_css(".md-code-caption").text.strip
    assert_includes result, "```python\nprint(\"roads\")\n```"
  end

  def test_listing_requires_exactly_one_fenced_block
    markdown = <<~MARKDOWN
      ::: listing "Two blocks"
      ```python
      print(1)
      ```

      ```python
      print(2)
      ```
      :::
    MARKDOWN

    result = Unaltraweb::FigureCaptions.transform_markdown_sugar(markdown, "en", "Figure", "Table", "Listing")

    assert_includes result, '::: listing "Two blocks"'
    refute_includes result, "md-code-listing"
  end

  def test_listing_syntax_inside_a_code_example_is_not_transformed
    markdown = <<~MARKDOWN
      ````markdown
      ::: listing "Example"
      ```python
      print(1)
      ```
      :::
      ````
    MARKDOWN

    result = Unaltraweb::FigureCaptions.transform_markdown_sugar(markdown, "en", "Figure", "Table", "Listing")

    assert_equal markdown, result
  end
end

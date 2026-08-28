# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "nokogiri"
require "ostruct"

require_relative "../../_plugins/code_blocks"

class CodeBlocksTest < Minitest::Test
  def setup
    @site = OpenStruct.new(
      config: { "default_lang" => "en" },
      data: {
        "i18n" => {
          "ca" => { "code_blocks" => { "label" => "Fragment" } }
        }
      }
    )
  end

  def test_adds_language_header_and_accessible_line_numbers_without_losing_highlighting
    html = <<~HTML
      <div class="language-python highlighter-rouge"><div class="highlight"><pre class="highlight"><code><span class="nb">print</span>(1)
      <span class="nb">print</span>(2)
      </code></pre></div></div>
    HTML

    result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "en")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_equal "Python", block.at_css(".uw-code-language").text
    assert_equal "python", block["data-code-language"]
    assert_equal "group", block["role"]
    assert_equal "Python", block["aria-label"]
    assert_equal "1\n2", block.at_css("pre.lineno").text.strip
    assert_equal "true", block.at_css(".rouge-gutter")["aria-hidden"]
    assert_equal "print", block.at_css(".rouge-code .nb").text
    assert_equal "presentation", block.at_css("table.rouge-table")["role"]
  end

  def test_uses_localized_generic_label_for_text_code
    html = '<div class="language-text highlighter-rouge"><div class="highlight"><pre><code>plain</code></pre></div></div>'

    result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "ca")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_equal "Fragment", block.at_css(".uw-code-language").text
    assert_equal "text", block["data-code-language"]
  end

  def test_wraps_an_unlabelled_fence_with_the_standard_code_label
    result = Unaltraweb::CodeBlocks.transform_html("<pre><code>first\nsecond\n</code></pre>", site: @site, lang: "es")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_equal "Código", block.at_css(".uw-code-language").text
    assert_equal "1\n2", block.at_css("pre.lineno").text.strip
    assert_equal "first\nsecond", block.at_css(".rouge-code code").text.strip
  end

  def test_does_not_duplicate_existing_structure
    html = '<div class="language-sql highlighter-rouge"><div class="highlight"><pre><code>SELECT 1;</code></pre></div></div>'
    once = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "en")
    twice = Unaltraweb::CodeBlocks.transform_html(once, site: @site, lang: "en")
    fragment = Nokogiri::HTML::DocumentFragment.parse(twice)

    assert_equal 1, fragment.css(".uw-code-header").length
    assert_equal 1, fragment.css("table.rouge-table").length
  end

  def test_leaves_inline_highlighted_code_unchanged
    html = '<p>Use <code class="language-plaintext highlighter-rouge">ST_Area</code> here.</p>'

    result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "en")
    fragment = Nokogiri::HTML::DocumentFragment.parse(result)

    assert_equal "ST_Area", fragment.at_css("p > code").text
    refute fragment.at_css(".uw-code-block")
    refute fragment.at_css(".uw-code-header")
  end
end

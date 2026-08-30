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

  def test_renders_text_code_without_a_header_or_line_numbers
    html = '<div class="language-text highlighter-rouge"><div class="highlight"><pre><code>plain</code></pre></div></div>'

    result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "ca")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_includes block["class"], "uw-code-verbatim"
    assert_equal "text", block["data-code-language"]
    assert_nil block.at_css(".uw-code-header")
    assert_nil block.at_css("pre.lineno")
    assert_nil block.at_css("table.rouge-table")
    assert_equal "plain", block.at_css("pre > code").text
  end

  def test_adds_localized_headers_to_semantic_blocks
    cases = {
      "url" => "URL",
      "spreadsheet" => "Fórmula",
      "filetree" => "Fitxers"
    }

    cases.each do |language, label|
      html = %(<div class="language-#{language} highlighter-rouge"><div class="highlight"><pre><code>value</code></pre></div></div>)
      result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "ca")
      block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

      assert_equal label, block.at_css(".uw-code-language").text
      assert block.at_css("table.rouge-table"), language
    end
  end

  def test_registers_semantic_rouge_lexers
    cases = {
      "url" => ["https://example.test/path?x=1", 'class="na"'],
      "spreadsheet" => ["=SUM(A2:A10)", 'class="nb"'],
      "filetree" => ["outputs/maps/map.svg", 'class="na"']
    }

    cases.each do |language, (source, token_class)|
      lexer = Rouge::Lexer.find(language)
      highlighted = Rouge::Formatters::HTML.new.format(lexer.lex(source))

      assert_includes highlighted, token_class, language
    end
  end

  def test_wraps_an_unlabelled_fence_as_plain_verbatim
    result = Unaltraweb::CodeBlocks.transform_html("<pre><code>first\nsecond\n</code></pre>", site: @site, lang: "es")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_includes block["class"], "uw-code-verbatim"
    assert_nil block.at_css(".uw-code-header")
    assert_nil block.at_css("pre.lineno")
    assert_equal "first\nsecond", block.at_css("pre > code").text.strip
  end

  def test_treats_an_unknown_language_as_plain_verbatim
    html = '<div class="language-unknown highlighter-rouge"><div class="highlight"><pre><code>raw</code></pre></div></div>'

    result = Unaltraweb::CodeBlocks.transform_html(html, site: @site, lang: "en")
    block = Nokogiri::HTML::DocumentFragment.parse(result).at_css(".uw-code-block")

    assert_includes block["class"], "uw-code-verbatim"
    assert_nil block.at_css(".uw-code-header")
    assert_nil block.at_css("table.rouge-table")
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

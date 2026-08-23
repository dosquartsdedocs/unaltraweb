# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "nokogiri"
require "ostruct"

require_relative "../../_plugins/callouts"

class CalloutsTest < Minitest::Test
  def setup
    @site = OpenStruct.new(
      config: { "default_lang" => "en" },
      data: {
        "i18n" => {
          "ca" => {
            "callouts" => {
              "objectives" => "OBJECTIUS PERSONALITZATS"
            }
          }
        }
      }
    )
  end

  def test_renders_nested_blockquotes_as_localized_callout_html
    html = nested_blockquotes(5, "<p>Aprendre a interpretar dades.</p>")

    result = Unaltraweb::Callouts.transform_html(html, site: @site, lang: "ca")
    fragment = Nokogiri::HTML::DocumentFragment.parse(result)
    blockquotes = fragment.css("blockquote")
    callout = blockquotes.last

    assert_equal 5, blockquotes.length
    blockquotes.first(4).each { |wrapper| assert_includes wrapper["class"].split, "uw-callout-wrapper" }
    assert_includes callout["class"].split, "uw-callout-objectives"
    assert_equal "objectives", callout["data-callout"]
    assert_equal "OBJECTIUS PERSONALITZATS", callout.element_children.first.text
    assert_equal "Aprendre a interpretar dades.", callout.element_children.last.text
  end

  def test_maps_each_supported_depth_and_caps_deeper_callouts_at_danger
    expected = %w[info example warning objectives danger danger]

    expected.each_with_index do |type, index|
      result = Unaltraweb::Callouts.transform_html(
        nested_blockquotes(index + 2, "<p>Text</p>"),
        site: @site,
        lang: "en"
      )
      callout = Nokogiri::HTML::DocumentFragment.parse(result).css("blockquote").last

      assert_equal type, callout["data-callout"]
      assert_includes callout["class"].split, "uw-callout-#{type}"
    end
  end

  def test_leaves_an_ordinary_blockquote_unchanged
    html = '<blockquote class="quotation"><p>A cited passage.</p></blockquote>'

    result = Unaltraweb::Callouts.transform_html(html, site: @site, lang: "en")
    blockquote = Nokogiri::HTML::DocumentFragment.parse(result).at_css("blockquote")

    assert_equal ["quotation"], blockquote["class"].split
    refute blockquote.key?("data-callout")
    assert_nil blockquote.at_css(".uw-callout-title")
  end

  private

  def nested_blockquotes(count, content)
    ("<blockquote>" * count) + content + ("</blockquote>" * count)
  end
end

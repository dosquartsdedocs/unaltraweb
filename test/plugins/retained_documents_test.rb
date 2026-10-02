# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "nokogiri"
require_relative "../../_plugins/retained_documents"

class RetainedDocumentsTest < Minitest::Test
  def test_native_tag_embeds_verified_pdf_and_escapes_title
    site = Struct.new(:config).new({ "baseurl" => "/manual", "unaltraweb_retained_documents" => { "letter" => { "pdf" => "assets/documents/letter.pdf" } } })
    html = Liquid::Template.parse("{% retained_document letter %}").render!(
      { "page" => { "title" => "Letter <review> & evidence" } }, registers: { site: site }
    )
    node = Nokogiri::HTML::DocumentFragment.parse(html)
    assert_equal "/manual/assets/documents/letter.pdf", node.at_css("object")["data"]
    assert_equal "application/pdf", node.at_css("object")["type"]
    assert_equal "Letter <review> & evidence", node.at_css("object")["aria-label"]
    assert_equal "/manual/assets/documents/letter.pdf", node.at_css("figcaption a")["href"]
    assert_empty node.css("review")
  end

  def test_unverified_or_nonliteral_reference_is_rejected
    site = Struct.new(:config).new({})
    assert_raises(Jekyll::Errors::FatalException) do
      Liquid::Template.parse("{% retained_document missing %}").render!({}, registers: { site: site })
    end
    assert_raises(ArgumentError) { Liquid::Template.parse("{% retained_document ../outside %}") }
  end

  def test_core_loader_registers_the_native_tag
    assert_includes File.read(File.expand_path("../../lib/unaltraweb.rb", __dir__)), "retained_documents"
  end
end

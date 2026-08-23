# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"

class FooterTest < Minitest::Test
  ROOT = File.expand_path("..", __dir__)
  TEMPLATE_PATH = File.join(ROOT, "_includes", "footer.liquid")

  def test_custom_footer_text_keeps_configured_logo
    html = render_footer("Custom footer")

    assert_includes html, "Custom footer"
    assert_equal 1, html.scan('class="footer-logo-stack"').length
    refute_includes html, "footer-product-credit"
  end

  def test_default_footer_keeps_product_and_brand_credit
    html = render_footer(nil)

    assert_includes html, 'class="footer-product-credit"'
    assert_includes html, 'href="https://github.com/dosquartsdedocs/unaltraweb"'
    assert_includes html, 'href="https://example.test/brand">Example Brand</a>'
    assert_equal 1, html.scan('class="footer-logo-stack"').length
  end

  private

  def render_footer(footer_text)
    config = Jekyll::Configuration.from(
      "source" => ROOT,
      "destination" => "/tmp/unaltraweb-footer-test",
      "safe" => true,
      "disable_disk_cache" => true,
      "baseurl" => "/example",
      "default_lang" => "en",
      "footer_text" => footer_text,
      "unaltraweb" => {
        "logos" => {
          "default" => "/assets/dark.svg",
          "inverse" => "/assets/light.svg"
        },
        "footer" => {
          "show_logo" => true,
          "brand_name" => "Example Brand",
          "brand_url" => "https://example.test/brand"
        }
      }
    )
    site = Jekyll::Site.new(config)
    template = site.liquid_renderer.file(TEMPLATE_PATH).parse(File.read(TEMPLATE_PATH))

    template.render!(site.site_payload, { "page" => {} }, registers: { site: site, page: {} })
  end
end

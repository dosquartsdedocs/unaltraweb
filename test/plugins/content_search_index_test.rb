# frozen_string_literal: true

require "jekyll"
require "minitest/autorun"
require "ostruct"

require_relative "../../_plugins/content_search_index"

class ContentSearchIndexTest < Minitest::Test
  Item = Struct.new(:data, :content, :url, :output, keyword_init: true)
  Collection = Struct.new(:metadata, :docs, keyword_init: true)

  def test_builds_content_entries_for_every_site_profile
    Unaltraweb::ContentSearchIndex::SUPPORTED_PROFILES.each do |profile|
      entries = Unaltraweb::ContentSearchIndex.content_entries(site_for(profile))

      assert_equal ["Shared page"], entries.map { |entry| entry[:title] }, profile
      assert_equal "/base/en/shared-page/", entries.first[:url]
      assert_equal "en", entries.first[:lang]
    end
  end

  def test_filters_profiles_exclusions_unpublished_content_and_private_collections
    site = site_for("unaltremanual")
    site.pages.concat([
      item("Other profile", profiles: ["unaltreselfie"]),
      item("Excluded", search_exclude: true),
      item("Unpublished", published: false)
    ])
    site.collections["chapters"] = Collection.new(
      metadata: {"output" => true},
      docs: [item("Manual chapter", profiles: ["unaltremanual"])]
    )
    site.collections["private"] = Collection.new(
      metadata: {"output" => false},
      docs: [item("Private notes")]
    )

    entries = Unaltraweb::ContentSearchIndex.content_entries(site)

    assert_equal ["Manual chapter", "Shared page"], entries.map { |entry| entry[:title] }.sort
  end

  def test_preserves_repeated_code_text_and_documentation_profiles
    page = item(
      "Unicode search",
      body: "```python\nprint('cafè')\n```\nCafé café.",
      documentation_profiles: ["Local Authors"]
    )
    site = site_for("unaltredocs", pages: [page])

    entry = Unaltraweb::ContentSearchIndex.content_entries(site).first

    assert_includes entry[:body], "print 'cafè'"
    assert_includes entry[:body], "Café café"
    assert_equal ["local-authors"], entry[:documentation_profile_slugs]
  end

  def test_indexes_rendered_text_segments_used_by_browser_highlighting
    page = item(
      "Rendered search",
      body: "Source text is replaced during rendering.",
      output: <<~HTML
        <main data-content-search-root>
          <p>co<em>operate</em> and Café <em>terrain</em> terrain.</p>
          <button>Hidden terrain</button>
          <span aria-hidden="true">Hidden terrain</span>
          <details><summary>More</summary><p>Collapsed terrain</p></details>
          <pre><code class="language-mermaid">Hidden diagram terrain</code></pre>
        </main>
      HTML
    )
    entry = Unaltraweb::ContentSearchIndex.content_entries(site_for("unaltreselfie", pages: [page])).first

    assert_equal ["cooperate and Café terrain terrain. More Collapsed terrain"], entry[:segments]
    assert_equal "cooperate and Café terrain terrain. More Collapsed terrain", entry[:body]
  end

  def test_uses_the_profile_specific_content_root
    page = item(
      "Manual search",
      output: <<~HTML
        <main data-content-search-root>
          <nav>Outer navigation text</nav>
          <article class="manual-main">
            <h1>Chapter title</h1>
            <div class="manual-content"><p>Chapter terrain terrain.</p></div>
          </article>
        </main>
      HTML
    )
    entry = Unaltraweb::ContentSearchIndex.content_entries(site_for("unaltremanual", pages: [page])).first

    assert_equal ["Chapter title Chapter terrain terrain."], entry[:segments]
  end

  def test_uses_site_language_when_default_language_is_not_configured
    site = site_for("unaltreselfie")
    site.config.delete("default_lang")
    site.config["lang"] = "ca"
    site.pages.first.data.delete("lang")

    entry = Unaltraweb::ContentSearchIndex.content_entries(site).first

    assert_equal "ca", entry[:lang]
  end

  def test_finalizes_the_generated_page_after_content_rendering
    page = item("Rendered page", output: '<main data-content-search-root><p>Final text.</p></main>')
    site = site_for("unaltreprojecte", pages: [page])
    index_page = Item.new(
      data: {"content_search_index" => true, "search_exclude" => true},
      content: "[]\n",
      url: Unaltraweb::ContentSearchIndex::INDEX_PATH
    )
    site.pages << index_page

    Unaltraweb::ContentSearchIndex.finalize_page(site)

    payload = JSON.parse(index_page.output)
    assert_equal ["Final text."], payload.first.fetch("segments")
  end

  def test_detects_consumer_managed_index_collisions
    page = item("Search index")
    page.url = Unaltraweb::ContentSearchIndex::INDEX_PATH
    static_file = OpenStruct.new(relative_path: Unaltraweb::ContentSearchIndex::INDEX_PATH)
    site = OpenStruct.new(pages: [page], static_files: [])

    assert Unaltraweb::ContentSearchIndex.index_collision?(site)

    site.pages = []
    site.static_files = [static_file]
    assert Unaltraweb::ContentSearchIndex.index_collision?(site)
  end

  private

  def item(title, body: "Repeated terrain terrain content.", output: nil, **data)
    slug = title.downcase.gsub(/[^a-z0-9]+/, "-").gsub(/^-|-$/, "")
    Item.new(
      data: {"title" => title, "lang" => "en"}.merge(data.transform_keys(&:to_s)),
      content: body,
      url: "/en/#{slug}/",
      output: output
    )
  end

  def site_for(profile, pages: nil)
    OpenStruct.new(
      source: Dir.pwd,
      config: {
        "baseurl" => "/base",
        "default_lang" => "en",
        "unaltraweb" => {"site_profile" => profile}
      },
      pages: pages || [item("Shared page")],
      collections: {}
    )
  end
end

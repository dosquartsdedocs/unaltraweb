# frozen_string_literal: true

require "cgi"
require "json"
require "nokogiri"

module Unaltraweb
  module ContentSearchIndex
    module_function

    SUPPORTED_PROFILES = %w[unaltreselfie unaltreprojecte unaltremanual unaltredocs].freeze
    INDEX_PATH = "/assets/js/content-search-index.json"
    EXCLUDED_TAGS = %w[script style template noscript textarea input select button nav].freeze
    BLOCK_TAGS = %w[address article aside blockquote div dl dt dd fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr li main ol p pre section table tbody td tfoot th thead tr ul].freeze
    DYNAMIC_SOURCE_LANGUAGES = %w[language-mermaid language-vega_lite language-plotly language-echarts language-geojson language-diff2html].freeze

    def active_profile(site)
      config = site.config["unaltraweb"] || {}
      (config["site_profile"] || "unaltreprojecte").to_s
    end

    def add_page(site)
      profile = active_profile(site)
      return unless SUPPORTED_PROFILES.include?(profile)
      if index_collision?(site)
        raise Jekyll::Errors::FatalException, "Content search index conflicts with a consumer-managed #{INDEX_PATH}"
      end

      page = Jekyll::PageWithoutAFile.new(site, site.source, "assets/js", "content-search-index.json")
      page.content = "[]\n"
      page.data["layout"] = nil
      page.data["sitemap"] = false
      page.data["search_exclude"] = true
      page.data["content_search_index"] = true
      site.pages << page
    end

    def finalize_page(site)
      page = Array(site.pages).find do |candidate|
        candidate.url.to_s == INDEX_PATH && candidate.data["content_search_index"] == true
      end
      return unless page

      payload = "#{JSON.pretty_generate(content_entries(site))}\n"
      page.content = payload
      page.output = payload
    end

    def index_collision?(site)
      page_collision = Array(site.pages).any? { |page| page.url.to_s == INDEX_PATH }
      static_collision = Array(site.static_files).any? { |file| file.relative_path.to_s == INDEX_PATH }
      page_collision || static_collision
    end

    def content_entries(site)
      profile = active_profile(site)
      documents = site.collections.values.flat_map do |collection|
        collection_output?(collection) ? collection.docs : []
      end
      items = (site.pages + documents).select { |item| searchable?(item, profile) }
      items = items.sort_by { |item| [item.url.to_s, item.data["title"].to_s] }
                   .uniq { |item| item.url.to_s }

      items.map { |item| entry(site, item) }
    end

    def collection_output?(collection)
      metadata = collection.respond_to?(:metadata) ? collection.metadata : {}
      metadata.fetch("output", false) == true
    end

    def searchable?(item, profile)
      data = item.data || {}
      return false if data["title"].to_s.strip.empty? || item.url.to_s.strip.empty?
      return false if data["published"] == false || data["published"].to_s == "false"
      return false if truthy?(data["search_exclude"])

      profile_match?(item, [profile])
    end

    def entry(site, item)
      segments = rendered_segments(site, item)
      if segments.empty? && (!item.respond_to?(:output) || item.output.to_s.empty?)
        segments = [normalize_text(item.content)].reject(&:empty?)
      end
      documentation_profiles = metadata_values(item, "documentation_profiles")

      {
        title: item.data["title"].to_s,
        description: item.data["description"].to_s,
        lang: item.data["lang"].to_s.empty? ? (site.config["default_lang"] || site.config["lang"]).to_s : item.data["lang"].to_s,
        url: relative_url(site, item.url),
        section: item.data["section"].to_s,
        subsection: item.data["subsection"].to_s,
        keywords: Array(item.data["keywords"] || item.data["tags"]).join(" "),
        documentation_profiles: documentation_profiles,
        documentation_profile_slugs: documentation_profiles.map { |value| Jekyll::Utils.slugify(value) },
        body: segments.join(" "),
        segments: segments,
      }
    end

    def metadata_values(item, *keys)
      keys.flat_map { |key| Array(item.data[key]) }
          .map { |value| value.to_s.strip }
          .reject(&:empty?)
          .uniq
    end

    def rendered_segments(site, item)
      output = item.respond_to?(:output) ? item.output.to_s : ""
      return [] if output.empty?

      document = Nokogiri::HTML::Document.parse(output)
      root = search_root_selectors(site).filter_map { |selector| document.at_css(selector) }.first
      return [] unless root

      chunks = []
      append_searchable_text(root, chunks)
      body = normalize_segment(chunks.join)
      body.empty? ? [] : [body]
    end

    def search_root_selectors(site)
      case active_profile(site)
      when "unaltremanual"
        [".manual-main", "[data-content-search-root]"]
      when "unaltredocs"
        [".documentation-main", "[data-content-search-root]"]
      else
        ["[data-content-search-root]"]
      end
    end

    def append_searchable_text(node, chunks)
      node.children.each do |child|
        if child.text?
          chunks << child.text
          next
        end
        next unless child.element?
        next if excluded_element?(child)

        block = BLOCK_TAGS.include?(child.name.downcase) || child.name.downcase == "br"
        chunks << " " if block
        append_searchable_text(child, chunks) unless child.name.downcase == "br"
        chunks << " " if block
      end
    end

    def excluded_element?(element)
      classes = element["class"].to_s.split
      EXCLUDED_TAGS.include?(element.name.downcase) ||
        element.key?("hidden") ||
        element.key?("inert") ||
        element["aria-hidden"] == "true" ||
        classes.include?("content-search-navigation") ||
        classes.include?("documentation-index") ||
        dynamic_source?(element, classes)
    end

    def dynamic_source?(element, classes)
      element.name.downcase == "code" && !(classes & DYNAMIC_SOURCE_LANGUAGES).empty?
    end

    def normalize_segment(value)
      value.to_s.gsub(/[[:space:]\u00a0]+/, " ").strip
    end

    def truthy?(value)
      %w[true yes 1 selected].include?(value.to_s.strip.downcase)
    end

    def profile_match?(item, profiles)
      item_profiles = Array(item.data["profiles"] || item.data["site_profiles"]).map(&:to_s)
      item_profiles.empty? || (item_profiles & profiles).any?
    end

    def normalize_text(value)
      text = value.to_s.dup
      text.gsub!(/\{%.*?%\}/m, " ")
      text.gsub!(/\{\{.*?\}\}/m, " ")
      text.gsub!(/^[ \t]*(?:`{3,}|~{3,})[^\n]*$/, " ")
      text.gsub!(/<[^>]+>/m, " ")
      text.gsub!(/!\[[^\]]*\]\([^)]*\)/m, " ")
      text.gsub!(/\[([^\]]+)\]\([^)]*\)/m, "\\1")
      text.gsub!(/[#>*_`|{}\[\]()]/, " ")
      CGI.unescapeHTML(text).gsub(/\s+/, " ").strip
    end

    def relative_url(site, url)
      baseurl = site.config["baseurl"].to_s.chomp("/")
      path = url.start_with?("/") ? url : "/#{url}"
      "#{baseurl}#{path}"
    end
  end
end

class UnaltrawebContentSearchIndexGenerator < Jekyll::Generator
  safe true
  priority :low

  def generate(site)
    Unaltraweb::ContentSearchIndex.add_page(site)
  end
end

Jekyll::Hooks.register :site, :post_render do |site|
  Unaltraweb::ContentSearchIndex.finalize_page(site)
end

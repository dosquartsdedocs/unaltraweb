# frozen_string_literal: true

require "cgi"
require "json"

module Unaltraweb
  module ManualSearchIndex
    module_function

    def active_profile(site)
      config = site.config["unaltraweb"] || {}
      (config["site_profile"] || config["site_type"] || "project").to_s
    end

    def manual_collection(site)
      config = site.config["unaltraweb"] || {}
      manual = config["manual"] || {}
      (manual["collection"] || "chapters").to_s
    end

    def documentation_collection(site)
      config = site.config["unaltraweb"] || {}
      documentation = config["documentation"] || {}
      (documentation["collection"] || "documentation").to_s
    end

    def add_page(site)
      profile = active_profile(site)
      add_manual_page(site) if profile == "manual"
      add_documentation_page(site) if %w[techdocs software].include?(profile)
    end

    def add_manual_page(site)
      page = Jekyll::PageWithoutAFile.new(site, site.source, "assets/js", "manual-search-index.json")
      page.content = JSON.pretty_generate(manual_entries(site))
      page.data["layout"] = nil
      page.data["sitemap"] = false
      site.pages << page
    end

    def add_documentation_page(site)
      page = Jekyll::PageWithoutAFile.new(site, site.source, "assets/js", "documentation-search-index.json")
      page.content = JSON.pretty_generate(documentation_entries(site))
      page.data["layout"] = nil
      page.data["sitemap"] = false
      site.pages << page
    end

    def manual_entries(site)
      collection_name = manual_collection(site)
      docs = site.collections[collection_name]&.docs || []
      pages = site.pages.select do |page|
        page.data["layout"].to_s == "manual-home" && profile_match?(page, ["manual"])
      end
      items = (pages + docs).select { |item| item.data["title"].to_s.strip != "" }

      items.map { |item| entry(site, item) }
    end

    def documentation_entries(site)
      profile = active_profile(site)
      profile_aliases = profile == "software" ? %w[software techdocs] : %w[techdocs software]
      collection_name = documentation_collection(site)
      docs = site.collections[collection_name]&.docs || []
      docs = docs.select { |doc| profile_match?(doc, profile_aliases) }
      pages = site.pages.select do |page|
        page.data["layout"].to_s == "documentation-home" && profile_match?(page, profile_aliases)
      end
      items = (pages + docs).select { |item| item.data["title"].to_s.strip != "" }

      items.map { |item| entry(site, item) }
    end

    def entry(site, item)
      {
        title: item.data["title"].to_s,
        description: item.data["description"].to_s,
        lang: item.data["lang"].to_s,
        url: relative_url(site, item.url),
        section: item.data["section"].to_s,
        subsection: item.data["subsection"].to_s,
        keywords: Array(item.data["keywords"] || item.data["tags"]).join(" "),
        body: normalize_text(item.content),
      }
    end

    def profile_match?(item, profiles)
      item_profiles = Array(item.data["profiles"] || item.data["site_profiles"]).map(&:to_s)
      item_profiles.empty? || (item_profiles & profiles).any?
    end

    def normalize_text(value)
      text = value.to_s.dup
      text.gsub!(/\{%.*?%\}/m, " ")
      text.gsub!(/\{\{.*?\}\}/m, " ")
      text.gsub!(/```.*?```/m, " ")
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

class UnaltrawebManualSearchIndexGenerator < Jekyll::Generator
  safe true
  priority :low

  def generate(site)
    Unaltraweb::ManualSearchIndex.add_page(site)
  end
end

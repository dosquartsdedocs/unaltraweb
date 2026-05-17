# frozen_string_literal: true

require "cgi"
require "fileutils"
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

    def write(site)
      return unless active_profile(site) == "manual"

      target = site.in_dest_dir("assets/js/manual-search-index.json")
      FileUtils.mkdir_p(File.dirname(target))
      File.write(target, JSON.pretty_generate(entries(site)))
    end

    def entries(site)
      collection_name = manual_collection(site)
      docs = site.collections[collection_name]&.docs || []
      pages = site.pages.select { |page| Array(page.data["profiles"] || page.data["site_profiles"]).map(&:to_s).include?("manual") }
      items = (pages + docs).select { |item| item.data["title"].to_s.strip != "" }

      items.map do |item|
        {
          title: item.data["title"].to_s,
          description: item.data["description"].to_s,
          lang: item.data["lang"].to_s,
          url: relative_url(site, item.url),
          keywords: Array(item.data["keywords"] || item.data["tags"]).join(" "),
          body: normalize_text(item.content),
        }
      end
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

Jekyll::Hooks.register :site, :post_write do |site|
  Unaltraweb::ManualSearchIndex.write(site)
end

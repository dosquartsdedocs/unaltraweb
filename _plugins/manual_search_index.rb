# frozen_string_literal: true

require "cgi"
require "json"

module Unaltraweb
  module ManualSearchIndex
    module_function

    def active_profile(site)
      config = site.config["unaltraweb"] || {}
      (config["site_profile"] || "unaltreprojecte").to_s
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
      add_manual_page(site) if profile == "unaltremanual"
      add_documentation_page(site) if profile == "unaltredocs"
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
        page.data["layout"].to_s == "manual-home" && profile_match?(page, ["unaltremanual"])
      end
      items = (pages + docs).select { |item| item.data["title"].to_s.strip != "" }

      items.map { |item| entry(site, item) }
    end

    def documentation_entries(site)
      profile = active_profile(site)
      collection_name = documentation_collection(site)
      docs = site.collections[collection_name]&.docs || []
      docs = docs.select { |doc| profile_match?(doc, [profile]) }
      pages = site.pages.select do |page|
        page.data["layout"].to_s == "documentation-home" && profile_match?(page, [profile])
      end
      items = (pages + docs).select { |item| item.data["title"].to_s.strip != "" }

      items.map { |item| entry(site, item) }
    end

    def entry(site, item)
      body = item.content.to_s
      if manual_bibliography_page?(item)
        body = "#{body}\n\n#{manual_bibliography_text(site, item.data["lang"].to_s)}"
      end

      {
        title: item.data["title"].to_s,
        description: item.data["description"].to_s,
        lang: item.data["lang"].to_s,
        url: relative_url(site, item.url),
        section: item.data["section"].to_s,
        subsection: item.data["subsection"].to_s,
        keywords: Array(item.data["keywords"] || item.data["tags"]).join(" "),
        body: normalize_text(body),
      }
    end

    def manual_bibliography_page?(item)
      item.data["ref"].to_s == "manual-bibliography" || item.content.to_s.include?("manual-bibliography.liquid")
    end

    def manual_bibliography_text(site, lang)
      manual_bib_entries(site).map do |fields|
        localized_values(fields, lang).join(" ")
      end.join("\n")
    end

    def localized_values(fields, lang)
      keys = [
        "title",
        "author",
        "editor",
        "year",
        "journal",
        "booktitle",
        "publisher",
        "doi",
        "url",
        "website",
        "abstract",
        "manual_kind",
        "manual_kind_#{lang}",
        "manual_badge",
        "manual_badge_#{lang}",
        "manual_comment",
        "manual_comment_#{lang}",
        "manual_collection_ref",
        "manual_collection_#{lang}",
      ]
      keys.map { |key| fields[key].to_s }.reject(&:empty?)
    end

    def manual_bib_entries(site)
      manual_bibliography_paths(site).flat_map do |path|
        next [] unless File.file?(path)

        parse_bib_entries(File.read(path, encoding: "UTF-8"))
      end.select { |fields| truthy?(fields["manual"]) }
    end

    def manual_bibliography_paths(site)
      manual = site.config.dig("unaltraweb", "manual") || {}
      bibliography = manual["bibliography_file"].to_s
      bibliography = "manual.bib" if bibliography.empty?
      bibliography_paths(site, bibliography)
    end

    def bibliography_paths(site, bibliography = nil)
      scholar = site.config["scholar"] || {}
      source = scholar.fetch("source", "_bibliography").to_s.sub(%r{\A/+}, "")
      bibliography ||= scholar.fetch("bibliography", "references.bib").to_s
      pattern = File.join(site.source, source, bibliography)
      paths = bibliography.include?("*") ? Dir.glob(pattern) : [pattern]
      paths.select { |path| File.extname(path).match?(/\.bib(?:tex)?\z/) }
    end

    def parse_bib_entries(text)
      entries = []
      index = 0
      while (at_index = text.index("@", index))
        brace_index = text.index("{", at_index)
        break unless brace_index

        end_index = matching_brace_index(text, brace_index)
        break unless end_index

        raw_entry = text[at_index..end_index]
        if raw_entry =~ /\A@(\w+)\s*\{\s*([^,]+)\s*,(.*)\}\s*\z/m
          fields = parse_bib_fields(Regexp.last_match(3))
          fields["type"] = Regexp.last_match(1)
          fields["key"] = Regexp.last_match(2).strip
          entries << fields
        end
        index = end_index + 1
      end
      entries
    end

    def matching_brace_index(text, open_index)
      depth = 0
      index = open_index
      while index < text.length
        case text[index]
        when "{"
          depth += 1
        when "}"
          depth -= 1
          return index if depth.zero?
        end
        index += 1
      end
      nil
    end

    def parse_bib_fields(body)
      fields = {}
      index = 0
      while index < body.length
        index += 1 while index < body.length && body[index].match?(/[\s,]/)
        match = body[index..]&.match(/\A([A-Za-z0-9_:-]+)\s*=\s*/)
        break unless match

        key = match[1].downcase
        index += match[0].length
        value, index = parse_bib_value(body, index)
        fields[key] = clean_bib_value(value)
      end
      fields
    end

    def parse_bib_value(body, index)
      case body[index]
      when "{"
        close_index = matching_brace_index(body, index)
        return [body[(index + 1)...close_index].to_s, close_index.to_i + 1]
      when '"'
        close_index = body.index('"', index + 1) || body.length
        return [body[(index + 1)...close_index].to_s, close_index + 1]
      else
        close_index = body.index(",", index) || body.length
        return [body[index...close_index].to_s, close_index]
      end
    end

    def clean_bib_value(value)
      value.to_s.gsub(/[{}]/, "").gsub(/\s+/, " ").strip
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

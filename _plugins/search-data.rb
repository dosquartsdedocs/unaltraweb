# frozen_string_literal: true

require "fileutils"
require "json"

module Jekyll
  module UnaltrawebSearchData
    module_function

    def write(site)
      return unless site.config["search_enabled"]

      target = site.in_dest_dir("assets/js/search-data.js")
      FileUtils.mkdir_p(File.dirname(target))
      File.write(target, script(entries(site)))
    end

    def entries(site)
      pages = site.pages.select { |page| page.data["nav"] && !page.data["autogen"] }
      collections = site.collections.respond_to?(:values) ? site.collections.values : site.collections
      docs = collections.reject { |collection| collection.label == "posts" }.flat_map(&:docs)

      (pages + site.posts.docs + docs).filter_map do |item|
        title = item.data["title"].to_s.strip
        next if title.empty?

        {
          id: "search-#{Jekyll::Utils.slugify(title)}",
          title: title,
          description: item.data["description"].to_s.gsub(/\s+/, " ").strip,
          section: search_section(item),
          url: relative_url(site, item.url),
        }
      end
    end

    def search_section(item)
      return "Navigation" unless item.respond_to?(:collection) && item.collection

      collection = item.collection
      label = collection.respond_to?(:label) ? collection.label : collection.to_s
      return "Posts" if label == "posts"
      return label.capitalize unless label.empty?

      "Navigation"
    end

    def relative_url(site, url)
      return url if url.start_with?("http://", "https://")

      baseurl = site.config["baseurl"].to_s.chomp("/")
      path = url.start_with?("/") ? url : "/#{url}"
      "#{baseurl}#{path}"
    end

    def script(entries)
      rows = entries.map do |entry|
        <<~JS
          {
            id: #{JSON.generate(entry[:id])},
            title: #{JSON.generate(entry[:title])},
            description: #{JSON.generate(entry[:description])},
            section: #{JSON.generate(entry[:section])},
            handler: () => { window.location.href = #{JSON.generate(entry[:url])}; },
          }
        JS
      end.join(",\n")

      <<~JS
        const ninja = document.querySelector("ninja-keys");
        if (ninja) {
          ninja.data = [
        #{rows}
          ];
        }
      JS
    end
  end

  Hooks.register :site, :post_write do |site|
    UnaltrawebSearchData.write(site)
  end
end

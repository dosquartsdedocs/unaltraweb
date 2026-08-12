# frozen_string_literal: true

require "yaml"
require "pathname"

module Unaltraweb
  module ComputationSources
    SUFFIXES = %w[.qmd .rmd .r .py .ipynb].freeze

    def self.source_roots(site)
      config_path = File.join(site.source, ".unaltraweb", "computations.yml")
      config = File.file?(config_path) ? YAML.safe_load_file(config_path, aliases: false) : {}
      roots = config.is_a?(Hash) ? config.fetch("source_roots", ["_chapters"]) : ["_chapters"]
      Array(roots).map do |root|
        path = Pathname.new(root.to_s)
        value = path.cleanpath.to_s.downcase
        if path.absolute? || value.empty? || value == "." || value.split("/").include?("..")
          raise Jekyll::Errors::FatalException, "Invalid computation source root: #{root}"
        end
        "/#{value}/"
      end
    rescue Psych::Exception => e
      raise Jekyll::Errors::FatalException, "Invalid .unaltraweb/computations.yml: #{e.message}"
    end

    Jekyll::Hooks.register :site, :post_read do |site|
      roots = source_roots(site)
      site.static_files.reject! do |file|
        relative = file.relative_path.to_s.downcase
        relative.start_with?("/.unaltraweb/") ||
          (roots.any? { |root| relative.start_with?(root) } &&
            (relative.include?("/.quarto/") || relative.end_with?(".quarto_ipynb") || SUFFIXES.any? { |suffix| relative.end_with?(suffix) }))
      end

      site.collections.each_value do |collection|
        collection.docs.reject! do |document|
          SUFFIXES.include?(File.extname(document.path).downcase)
        end
      end
    end
  end
end

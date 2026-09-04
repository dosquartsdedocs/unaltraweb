# frozen_string_literal: true

require "cgi"
require "jekyll/scholar"

module Unaltraweb
  module BibliographyProfiles
    PROFILE_SORTS = {
      "unaltreselfie" => {
        "sort_by" => %w[year month name title],
        "order" => %w[descending descending ascending ascending],
        "group_by" => "year",
        "group_order" => "descending"
      },
      "unaltreprojecte" => {
        "sort_by" => %w[year month name title],
        "order" => %w[descending descending ascending ascending],
        "group_by" => "year",
        "group_order" => "descending"
      },
      "unaltremanual" => {
        "sort_by" => %w[name year title],
        "order" => %w[ascending ascending ascending],
        "group_by" => "none",
        "group_order" => "ascending",
        "query" => "@*",
        "source" => "_bibliography"
      }
    }.freeze

    module_function

    def configure(site)
      profile = site.config.dig("unaltraweb", "site_profile").to_s
      settings = PROFILE_SORTS[profile]
      return unless settings

      site.config["scholar"] ||= {}
      site.config["scholar"].merge!(settings)
      if profile == "unaltremanual"
        manual = site.config.dig("unaltraweb", "manual") || {}
        manual = {} unless manual.is_a?(Hash)
        bibliography = (manual["bibliography_file"] || "manual.bib").to_s.strip
        unless bibliography.match?(/\A[A-Za-z0-9][A-Za-z0-9_.-]*\.bib\z/) && File.basename(bibliography) == bibliography
          raise Jekyll::Errors::FatalException, "unaltraweb.manual.bibliography_file must be a .bib filename under _bibliography/"
        end
        validate_bibliography_location(site, bibliography)
        site.config["scholar"]["bibliography"] = bibliography
      end
    end

    def validate_bibliography_location(site, bibliography)
      return unless site.respond_to?(:source) && site.source

      source = File.realpath(site.source)
      root = File.join(source, "_bibliography")
      return unless File.exist?(root) || File.symlink?(root)

      resolved_root = File.realpath(root)
      target = File.join(root, bibliography)
      resolved_target = if File.exist?(target) || File.symlink?(target)
                          File.realpath(target)
                        else
                          target
                        end
      root_prefix = resolved_root.end_with?(File::SEPARATOR) ? resolved_root : "#{resolved_root}#{File::SEPARATOR}"
      source_prefix = source.end_with?(File::SEPARATOR) ? source : "#{source}#{File::SEPARATOR}"
      confined = (resolved_root == source || resolved_root.start_with?(source_prefix)) && resolved_target.start_with?(root_prefix)
      return if confined

      raise Jekyll::Errors::FatalException, "unaltraweb.manual.bibliography_file must remain under the site's _bibliography/ directory"
    rescue Errno::ENOENT, Errno::ELOOP
      raise Jekyll::Errors::FatalException, "unaltraweb.manual.bibliography_file must resolve safely under _bibliography/"
    end

    def strip_web_access(reference, doi = nil, *urls)
      rendered = reference.to_s.dup
      variants = access_variants(doi, *urls).sort_by { |value| -value.length }
      loop do
        previous = rendered.dup
        variants.each do |value|
          escaped = Regexp.escape(value)
          rendered.sub!(%r{\s*(?:doi:\s*)?(?:<a\b[^>]*>\s*)?#{escaped}(?:\s*</a>)?\s*\.?(?=(?:\s*</[a-z][^>]*>)*\s*\z)}i, "")
        end
        break if rendered == previous
      end
      rendered.rstrip
    end

    def access_variants(doi, *urls)
      values = []
      normalized_doi = doi.to_s.strip.sub(%r{\Ahttps?://(?:dx\.)?doi\.org/}i, "").sub(/\Adoi:\s*/i, "")
      unless normalized_doi.empty?
        values.concat([
          "https://doi.org/#{normalized_doi}",
          "http://doi.org/#{normalized_doi}",
          "http://dx.doi.org/#{normalized_doi}",
          "doi:#{normalized_doi}",
          normalized_doi
        ])
      end
      urls.each { |url| values << url.to_s.strip unless url.to_s.strip.empty? }
      values.flat_map { |value| [value, CGI.escapeHTML(value)] }.uniq
    end

    def strip_reference_ids(reference)
      reference.to_s.gsub(/\s+id=(['"])[^'"]*\1/i, "")
    end

    def escape_liquid_markers(value)
      value.to_s.gsub("{{", "<span>{</span>{").gsub("{%", "<span>{</span>%")
    end

    def fold_sort_value(value)
      BibTeX::Value.new(value.to_s).convert(:latex).to_s.unicode_normalize(:nfkd).gsub(/\p{Mn}/, "")
    end
  end

  module ScholarProfileRendering
    def resolve_sort_value(entry, key)
      value = super
      return value unless key == "name" && unaltraweb_profile_sorting?

      BibTeX::Value.new(BibliographyProfiles.fold_sort_value(value))
    end

    def render_bibliography(entry, index = nil)
      citation_numbers = context && context["citation_numbers"]
      if index && unaltraweb_profile_sorting? && citation_numbers&.key?(entry.key) && unaltraweb_numeric_bibliography_style?
        index = citation_numbers[entry.key]
      end
      super(entry, index)
    end

    private

    def unaltraweb_profile_sorting?
      BibliographyProfiles::PROFILE_SORTS.key?(site&.config&.dig("unaltraweb", "site_profile").to_s)
    end

    def unaltraweb_numeric_bibliography_style?
      @unaltraweb_numeric_bibliography_styles ||= {}
      @unaltraweb_numeric_bibliography_styles[style] ||= styles(style).to_xml.include?('variable="citation-number"')
    end
  end

  module BibliographyProfileFilters
    def stripBibliographyAccess(input, doi = nil, *urls)
      BibliographyProfiles.strip_web_access(input, doi, *urls)
    end

    def stripBibliographyIds(input)
      BibliographyProfiles.strip_reference_ids(input)
    end

    def escapeLiquidMarkers(input)
      BibliographyProfiles.escape_liquid_markers(input)
    end
  end
end

Jekyll::Scholar::Utilities.prepend(Unaltraweb::ScholarProfileRendering) unless Jekyll::Scholar::Utilities.ancestors.include?(Unaltraweb::ScholarProfileRendering)
Liquid::Template.register_filter(Unaltraweb::BibliographyProfileFilters)
Jekyll::Hooks.register(:site, :post_read) { |site| Unaltraweb::BibliographyProfiles.configure(site) }

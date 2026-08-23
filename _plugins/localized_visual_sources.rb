# frozen_string_literal: true

module Unaltraweb
  module LocalizedVisualSources
    module_function

    VISUAL_SUFFIXES = %w[
      .capture.edited.svg .capture.yaml .capture.yml .capture.svg
      .mermaid.edited.svg .mermaid.svg .plantuml.edited.svg .plantuml.svg
      .mmd.edited.svg .mmd.svg .puml.edited.svg .puml.svg .uml.edited.svg .uml.svg
      .vl.json .vg.json .edited.svg
      .qmd .rmd .ipynb .mermaid .plantuml .mmd .puml .uml .py .r
      .jpeg .tiff .webp .gif .jpg .png .svg .pdf
    ].sort_by { |suffix| -suffix.length }.freeze
    FENCED_CODE_BLOCK = /^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$/m.freeze
    INLINE_CODE = /(`+)[^\n]*?\1/.freeze
    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_URL = /\A(?:[a-z][a-z0-9+.-]*:)?\/\//i.freeze

    def select_url(raw_url, site_source:, lang:, default_lang:, languages:)
      value = raw_url.to_s
      return value if value.empty?

      prefix = value[BASEURL_PREFIX].to_s
      without_prefix = prefix.empty? ? value : value[prefix.length..]
      decoration_index = [without_prefix.index("?"), without_prefix.index("#")].compact.min
      path = decoration_index ? without_prefix[0...decoration_index] : without_prefix
      decoration = decoration_index ? without_prefix[decoration_index..] : ""
      return value if path.empty? || path.start_with?("#", "data:") || path.match?(REMOTE_URL)

      current = lang.to_s.strip
      default = default_lang.to_s.strip
      return value if current.empty? || current == default

      suffix = VISUAL_SUFFIXES.find { |candidate| path.downcase.end_with?(candidate) }
      return value unless suffix

      stem = path[0...-suffix.length]
      configured = Array(languages).map(&:to_s).map(&:strip).reject(&:empty?) | [current, default]
      return value if configured.any? { |code| stem.downcase.end_with?(".#{code.downcase}") }

      localized_path = "#{stem}.#{current}#{suffix}"
      local_reference = localized_path.sub(%r{\A/+}, "")
      root = File.realpath(site_source)
      candidate = File.expand_path(local_reference, root)
      return value unless candidate.start_with?(root + File::SEPARATOR) && File.file?(candidate)

      "#{prefix}#{localized_path}#{decoration}"
    rescue Errno::ENOENT
      value
    end

    def rewrite(content, site_source:, lang:, default_lang:, languages:)
      source = content.to_s
      return source if lang.to_s.empty? || lang.to_s == default_lang.to_s

      protected = []
      protected_source = source.gsub(FENCED_CODE_BLOCK) do
        token = "UNALTRAWEBLOCALIZEDVISUALFENCE_#{protected.length}_END"
        protected << Regexp.last_match(0)
        token
      end
      output = rewrite_chunk(
        protected_source,
        site_source: site_source,
        lang: lang,
        default_lang: default_lang,
        languages: languages
      )
      (protected.length - 1).downto(0) do |index|
        output.gsub!("UNALTRAWEBLOCALIZEDVISUALFENCE_#{index}_END", protected[index])
      end
      output
    end

    def rewrite_chunk(chunk, site_source:, lang:, default_lang:, languages:)
      protected = []
      output = chunk.gsub(INLINE_CODE) do
        token = "UNALTRAWEBLOCALIZEDVISUALCODE_#{protected.length}_END"
        protected << Regexp.last_match(0)
        token
      end
      selector = lambda do |url|
        select_url(url, site_source: site_source, lang: lang, default_lang: default_lang, languages: languages)
      end
      output.gsub!(/(!\[[^\]]*\]\()((?:\{\{\s*site\.baseurl\s*\}\})?[^)\s]+)/) do
        "#{Regexp.last_match(1)}#{selector.call(Regexp.last_match(2))}"
      end
      output.gsub!(/(<img\b[^>]*\bsrc\s*=\s*["'])([^"']+)(["'])/i) do
        "#{Regexp.last_match(1)}#{selector.call(Regexp.last_match(2))}#{Regexp.last_match(3)}"
      end
      (protected.length - 1).downto(0) do |index|
        output.gsub!("UNALTRAWEBLOCALIZEDVISUALCODE_#{index}_END", protected[index])
      end
      output
    end

    def document_language(document, site)
      value = document.data["lang"].to_s
      return value unless value.empty?

      relative = document.respond_to?(:relative_path) ? document.relative_path.to_s.tr("\\", "/") : ""
      candidate = relative.split("/")[1].to_s
      candidate.empty? ? (site.config["default_lang"] || site.config["lang"]).to_s : candidate
    end
  end

  module LocalizedVisualFilter
    def localized_visual(raw_url)
      site = @context.registers[:site]
      page = @context.registers[:page]
      lang = page.respond_to?(:[]) ? page["lang"] : nil
      default_lang = site.config["default_lang"] || site.config["lang"]
      LocalizedVisualSources.select_url(
        raw_url,
        site_source: site.source,
        lang: lang || default_lang,
        default_lang: default_lang,
        languages: site.config["languages"]
      )
    end
  end
end

Liquid::Template.register_filter(Unaltraweb::LocalizedVisualFilter)

class UnaltrawebLocalizedVisualSourceGenerator < Jekyll::Generator
  safe true
  priority :highest

  def generate(site)
    documents = site.collections.values.flat_map(&:docs) + site.pages
    documents.each do |document|
      lang = Unaltraweb::LocalizedVisualSources.document_language(document, site)
      default_lang = (site.config["default_lang"] || site.config["lang"]).to_s
      document.content = Unaltraweb::LocalizedVisualSources.rewrite(
        document.content,
        site_source: site.source,
        lang: lang,
        default_lang: default_lang,
        languages: site.config["languages"]
      )
    end
  end
end

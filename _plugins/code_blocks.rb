# frozen_string_literal: true

require "nokogiri"

module Unaltraweb
  module CodeBlocks
    module_function

    DEFAULT_LABELS = {
      "ca" => "Codi",
      "es" => "Código",
      "en" => "Code"
    }.freeze
    GENERIC_LANGUAGES = %w[text plaintext plain txt].freeze
    LANGUAGE_LABELS = {
      "bash" => "Bash",
      "c" => "C",
      "console" => "Console",
      "cpp" => "C++",
      "csharp" => "C#",
      "css" => "CSS",
      "go" => "Go",
      "haskell" => "Haskell",
      "html" => "HTML",
      "java" => "Java",
      "javascript" => "JavaScript",
      "js" => "JavaScript",
      "json" => "JSON",
      "julia" => "Julia",
      "latex" => "LaTeX",
      "markdown" => "Markdown",
      "matlab" => "MATLAB",
      "php" => "PHP",
      "powershell" => "PowerShell",
      "python" => "Python",
      "r" => "R",
      "ruby" => "Ruby",
      "rust" => "Rust",
      "shell" => "Shell",
      "sh" => "Shell",
      "sql" => "SQL",
      "typescript" => "TypeScript",
      "ts" => "TypeScript",
      "xml" => "XML",
      "yaml" => "YAML",
      "yml" => "YAML"
    }.freeze

    def transform_html(html, site:, lang:)
      source = html.to_s
      return source unless source.match?(/<pre(?:\s|>)/i)

      fragment = Nokogiri::HTML::DocumentFragment.parse(source)
      generic_label = generic_label_for(site, lang)

      fragment.css("div.highlighter-rouge").each do |wrapper|
        decorate(wrapper, language_for(wrapper), generic_label)
      end

      fragment.css("pre > code").to_a.each do |code|
        next if code.ancestors.any? { |ancestor| class_names(ancestor).include?("uw-code-block") }

        wrap_standalone(code, generic_label)
      end

      fragment.to_html
    end

    def detect_lang(doc)
      configured = doc.data["lang"].to_s
      return normalize_lang(configured) unless configured.empty?

      relative_path = doc.respond_to?(:relative_path) ? doc.relative_path.to_s : ""
      path_lang = relative_path.tr("\\", "/").split("/")[1].to_s
      fallback = doc.site.config["default_lang"] || doc.site.config["lang"] || "en"
      normalize_lang(path_lang.empty? ? fallback : path_lang)
    end

    def generic_label_for(site, lang)
      normalized_lang = normalize_lang(lang)
      default_lang = normalize_lang(site.config["default_lang"] || site.config["lang"] || "en")
      i18n = site.data["i18n"] || {}
      configured = i18n.dig(normalized_lang, "code_blocks", "label") ||
                   i18n.dig(default_lang, "code_blocks", "label")
      configured.to_s.empty? ? (DEFAULT_LABELS[normalized_lang] || DEFAULT_LABELS[default_lang] || DEFAULT_LABELS.fetch("en")) : configured.to_s
    end

    def normalize_lang(lang)
      lang.to_s.downcase.split("-").first.to_s.then { |value| value.empty? ? "en" : value }
    end

    def decorate(wrapper, language, generic_label)
      normalized_language = language.to_s.downcase
      normalized_language = "text" if normalized_language.empty?
      label = display_label(normalized_language, generic_label)

      add_classes(wrapper, "uw-code-block", "language-#{normalized_language}")
      wrapper["data-code-language"] = normalized_language
      wrapper["role"] = "group"
      wrapper["aria-label"] = label
      add_header(wrapper, label)
      ensure_line_numbers(wrapper)
    end

    def wrap_standalone(code, generic_label)
      source_pre = code.parent
      language = language_for(code) || language_for(source_pre) || "text"
      wrapper = node("div", code.document)
      highlight = node("div", code.document)

      wrapper["class"] = "highlighter-rouge"
      highlight["class"] = "highlight"
      source_pre.replace(wrapper)
      wrapper.add_child(highlight)
      highlight.add_child(source_pre)
      decorate(wrapper, language, generic_label)
    end

    def add_header(wrapper, label)
      return if wrapper.element_children.any? { |child| class_names(child).include?("uw-code-header") }

      header = node("div", wrapper.document)
      language = node("span", wrapper.document)
      header["class"] = "uw-code-header"
      language["class"] = "uw-code-language"
      language.content = label
      header.add_child(language)
      wrapper.prepend_child(header)
    end

    def ensure_line_numbers(wrapper)
      if (table = wrapper.at_css("table.rouge-table"))
        mark_line_number_table(table)
        return
      end

      code = wrapper.at_css(".highlight pre > code") || wrapper.at_css("pre > code")
      return unless code

      source_pre = code.parent
      line_count = code.text.delete_suffix("\n").count("\n") + 1
      table = line_number_table(code.document, line_count, source_pre, code)
      source_pre.replace(table)
    end

    def line_number_table(document, line_count, source_pre, code)
      table = node("table", document)
      body = node("tbody", document)
      row = node("tr", document)
      gutter = node("td", document)
      gutter_pre = node("pre", document)
      code_cell = node("td", document)
      code_pre = node("pre", document)

      table["class"] = "rouge-table"
      gutter["class"] = "rouge-gutter gl"
      gutter_pre["class"] = "lineno"
      gutter_pre.content = (1..line_count).to_a.join("\n") + "\n"
      code_cell["class"] = "rouge-code"
      code_pre["class"] = source_pre["class"].to_s

      code.unlink
      code_pre.add_child(code)
      gutter.add_child(gutter_pre)
      code_cell.add_child(code_pre)
      row.add_child(gutter)
      row.add_child(code_cell)
      body.add_child(row)
      table.add_child(body)
      mark_line_number_table(table)
      table
    end

    def mark_line_number_table(table)
      table["role"] = "presentation"
      table.css(".rouge-gutter, pre.lineno").each { |node| node["aria-hidden"] = "true" }
    end

    def display_label(language, generic_label)
      return generic_label if GENERIC_LANGUAGES.include?(language)

      LANGUAGE_LABELS[language] || language.split(/[-_]/).reject(&:empty?).map(&:capitalize).join(" ")
    end

    def language_for(node)
      return nil unless node

      language_class = class_names(node).find { |name| name.start_with?("language-") }
      language_class&.delete_prefix("language-")
    end

    def class_names(node)
      node["class"].to_s.split
    end

    def add_classes(node, *classes)
      node["class"] = (class_names(node) + classes).uniq.join(" ")
    end

    def node(name, document)
      Nokogiri::XML::Node.new(name, document)
    end
  end
end

Jekyll::Hooks.register %i[documents pages], :post_convert do |doc|
  lang = Unaltraweb::CodeBlocks.detect_lang(doc)
  doc.content = Unaltraweb::CodeBlocks.transform_html(doc.content, site: doc.site, lang: lang)
end

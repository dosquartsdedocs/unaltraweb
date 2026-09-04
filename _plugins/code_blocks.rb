# frozen_string_literal: true

require "nokogiri"
require "rouge"

module Unaltraweb
  module CodeLexers
    class Url < Rouge::RegexLexer
      title "URL"
      desc "URLs and decomposed query parameters"
      tag "url"

      state :root do
        rule %r{https?://}, Keyword
        rule %r{#[^\n]*}, Comment::Single
        rule %r{[?&]}, Punctuation
        rule %r{[A-Za-z_][\w.-]*(?==)}, Name::Attribute
        rule %r{=}, Operator
        rule %r{\b\d+(?:\.\d+)*\b}, Num
        rule %r{[^#?&=\d]+}, Text
        rule %r{.}, Text
      end
    end

    class Spreadsheet < Rouge::RegexLexer
      title "Spreadsheet formula"
      desc "Spreadsheet formulas and cell references"
      tag "spreadsheet"

      state :root do
        rule %r/\s+/, Text
        rule %r/"(?:[^"]|"")*"/, Str
        rule %r/\b(?:AND|AVERAGE|COUNTIF|DATEDIF|DATE|DAY|HEX2DEC|HLOOKUP|IF|ISBLANK|ISNUMBER|ISTEXT|LEFT|MID|MONTH|NA|NETWORKDAYS|ROUND|SI|SUM|SUMA|SUMIFS|TODAY|TRIM|VLOOKUP|WEEKDAY|XLOOKUP|YEAR)\b(?=\()/i, Name::Builtin
        rule %r/[A-Za-z_][\w.-]*(?=!)/, Name::Namespace
        rule %r/\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?/i, Name::Variable
        rule %r/\d+(?:[.,]\d+)?/, Num
        rule %r/[+\-*\/>=<&,:;!]/, Operator
        rule %r/[()]/, Punctuation
        rule %r/./, Text
      end
    end

    class FileTree < Rouge::RegexLexer
      title "File tree"
      desc "Directory and file listings"
      tag "filetree"

      state :root do
        rule %r/^(\s*)(.+?)(\/)(?=\n?$)/ do
          groups Text, Name::Namespace, Punctuation
        end
        rule %r/^(\s*)(.+?)(\.[A-Za-z0-9]+)(?=\n?$)/ do
          groups Text, Name::Variable, Name::Attribute
        end
        rule %r/\s+/, Text
        rule %r/./, Text
      end
    end
  end

  module CodeBlocks
    module_function

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
    SEMANTIC_LABELS = {
      "url" => { "ca" => "URL", "es" => "URL", "en" => "URL" },
      "spreadsheet" => { "ca" => "Fórmula", "es" => "Fórmula", "en" => "Formula" },
      "filetree" => { "ca" => "Fitxers", "es" => "Archivos", "en" => "Files" }
    }.freeze

    def transform_html(html, site:, lang:)
      source = html.to_s
      return source unless source.match?(/<pre(?:\s|>)/i)

      fragment = Nokogiri::HTML::DocumentFragment.parse(source)
      fragment.css("div.highlighter-rouge").each do |wrapper|
        decorate(wrapper, language_for(wrapper), lang)
      end

      fragment.css("pre > code").to_a.each do |code|
        next if code.ancestors.any? { |ancestor| class_names(ancestor).include?("uw-code-block") }

        wrap_standalone(code, lang)
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

    def normalize_lang(lang)
      lang.to_s.downcase.split("-").first.to_s.then { |value| value.empty? ? "en" : value }
    end

    def decorate(wrapper, language, lang)
      normalized_language = language.to_s.downcase
      normalized_language = "text" if normalized_language.empty?

      add_classes(wrapper, "uw-code-block", "language-#{normalized_language}")
      wrapper["data-code-language"] = normalized_language
      if LANGUAGE_LABELS.key?(normalized_language) || SEMANTIC_LABELS.key?(normalized_language)
        label = display_label(normalized_language, lang)
        replace_class(wrapper, "uw-code-verbatim", "uw-code-highlighted")
        wrapper["role"] = "group"
        wrapper["aria-label"] = label
        add_header(wrapper, label)
        ensure_line_numbers(wrapper)
      else
        replace_class(wrapper, "uw-code-highlighted", "uw-code-verbatim")
        wrapper.remove_attribute("role")
        wrapper.remove_attribute("aria-label")
        wrapper.element_children.select { |child| class_names(child).include?("uw-code-header") }.each(&:remove)
        remove_line_numbers(wrapper)
      end
    end

    def wrap_standalone(code, lang)
      source_pre = code.parent
      language = language_for(code) || language_for(source_pre) || "text"
      wrapper = node("div", code.document)
      highlight = node("div", code.document)

      wrapper["class"] = "highlighter-rouge"
      highlight["class"] = "highlight"
      source_pre.replace(wrapper)
      wrapper.add_child(highlight)
      highlight.add_child(source_pre)
      decorate(wrapper, language, lang)
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

    def remove_line_numbers(wrapper)
      table = wrapper.at_css("table.rouge-table")
      return unless table

      source_pre = table.at_css("td.rouge-code > pre")
      return unless source_pre

      source_pre.unlink
      table.replace(source_pre)
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

    def language_for(node)
      return nil unless node

      language_class = class_names(node).find { |name| name.start_with?("language-") }
      language_class&.delete_prefix("language-")
    end

    def display_label(language, lang)
      labels = SEMANTIC_LABELS[language]
      return labels[normalize_lang(lang)] || labels.fetch("en") if labels

      LANGUAGE_LABELS.fetch(language)
    end

    def class_names(node)
      node["class"].to_s.split
    end

    def add_classes(node, *classes)
      node["class"] = (class_names(node) + classes).uniq.join(" ")
    end

    def replace_class(node, old_class, new_class)
      node["class"] = ((class_names(node) - [old_class]) + [new_class]).uniq.join(" ")
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

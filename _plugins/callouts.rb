# frozen_string_literal: true

require "nokogiri"

module Unaltraweb
  module Callouts
    module_function

    TYPES = %w[info example warning objectives danger].freeze
    DEFAULT_LABELS = {
      "ca" => {
        "info" => "NOTA",
        "example" => "EXEMPLE",
        "warning" => "ADVERTÈNCIA",
        "objectives" => "OBJECTIUS D'APRENENTATGE",
        "danger" => "ATENCIÓ"
      },
      "es" => {
        "info" => "NOTA",
        "example" => "EJEMPLO",
        "warning" => "ADVERTENCIA",
        "objectives" => "OBJETIVOS DE APRENDIZAJE",
        "danger" => "ATENCIÓN"
      },
      "en" => {
        "info" => "NOTE",
        "example" => "EXAMPLE",
        "warning" => "WARNING",
        "objectives" => "LEARNING OBJECTIVES",
        "danger" => "CAUTION"
      }
    }.freeze

    def transform_html(html, site:, lang:)
      source = html.to_s
      return source unless source.match?(/<blockquote(?:\s|>)/i)

      fragment = Nokogiri::HTML::DocumentFragment.parse(source)
      labels = labels_for(site, lang)

      fragment.css("blockquote").each do |blockquote|
        if blockquote.element_children.any? { |child| child.name == "blockquote" }
          add_classes(blockquote, "uw-callout-wrapper")
          next
        end

        depth = blockquote.ancestors("blockquote").length
        next if depth.zero?

        type = TYPES[[depth, TYPES.length].min - 1]
        add_classes(blockquote, "uw-callout", "uw-callout-#{type}")
        blockquote["data-callout"] = type
        add_title(blockquote, labels.fetch(type))
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

    def labels_for(site, lang)
      normalized_lang = normalize_lang(lang)
      default_lang = normalize_lang(site.config["default_lang"] || site.config["lang"] || "en")
      i18n = site.data["i18n"] || {}
      configured = i18n.dig(normalized_lang, "callouts") || i18n.dig(default_lang, "callouts") || {}
      defaults = DEFAULT_LABELS[normalized_lang] || DEFAULT_LABELS[default_lang] || DEFAULT_LABELS.fetch("en")

      defaults.merge(configured.transform_keys(&:to_s).transform_values(&:to_s))
    end

    def normalize_lang(lang)
      lang.to_s.downcase.split("-").first.to_s.then { |value| value.empty? ? "en" : value }
    end

    def add_classes(node, *classes)
      current = node["class"].to_s.split
      node["class"] = (current + classes).uniq.join(" ")
    end

    def add_title(blockquote, label)
      existing = blockquote.element_children.first
      return if existing && existing["class"].to_s.split.include?("uw-callout-title")

      title = Nokogiri::XML::Node.new("p", blockquote.document)
      title["class"] = "uw-callout-title"
      title["data-unaltraweb-callout-title"] = "true"
      title.content = label
      blockquote.prepend_child(title)
    end
  end
end

Jekyll::Hooks.register %i[documents pages], :post_convert do |doc|
  lang = Unaltraweb::Callouts.detect_lang(doc)
  doc.content = Unaltraweb::Callouts.transform_html(doc.content, site: doc.site, lang: lang)
end

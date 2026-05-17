# frozen_string_literal: true

# Rewrites Markdown and HTML image references from .mmd sources to generated SVGs.
# If an edited SVG exists next to the Mermaid source, it wins over the generated one.
module Unaltraweb
  module MermaidMmdImages
    module_function

    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_PATH_PREFIX = %r{\A(?:[a-z]+:)?//}i.freeze

    def rewrite(content, site_source:)
      return content if content.nil? || content.empty?

      out = content.dup

      out.gsub!(/!\[([^\]]*)\]\(([^)]*?\.mmd)(\s+"[^"]*")?\)/i) do
        alt = Regexp.last_match(1)
        path = svg_path_for(Regexp.last_match(2), site_source)
        title = Regexp.last_match(3).to_s
        "![#{alt}](#{path}#{title})"
      end

      out.gsub!(/(<img\b[^>]*\bsrc=)(["'])([^"']+?\.mmd)\2/i) do
        prefix = Regexp.last_match(1)
        quote = Regexp.last_match(2)
        path = svg_path_for(Regexp.last_match(3), site_source)
        "#{prefix}#{quote}#{path}#{quote}"
      end

      out
    end

    def svg_path_for(mmd_path, site_source)
      edited = "#{mmd_path}.edited.svg"
      return edited if local_asset_exists?(edited, site_source)

      "#{mmd_path}.svg"
    end

    def local_asset_exists?(asset_path, site_source)
      local_path = asset_path
        .sub(BASEURL_PREFIX, "")
        .split(/[?#]/, 2)
        .first.to_s
        .sub(%r{\A/+}, "")

      return false if local_path.empty? || local_path.match?(REMOTE_PATH_PREFIX)

      File.exist?(File.expand_path(local_path, site_source))
    end
  end
end

Jekyll::Hooks.register [:documents, :pages], :pre_render do |doc|
  next unless doc.respond_to?(:content) && doc.content

  doc.content = Unaltraweb::MermaidMmdImages.rewrite(doc.content, site_source: doc.site.source)
end
